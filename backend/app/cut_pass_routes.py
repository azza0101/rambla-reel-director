"""Project-scoped asynchronous CUT analysis and review. Never calls Resolve."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
import subprocess
import uuid

from fastapi import HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from .atomic_io import write_json
from .cut_pass import build_cut_plan, clean_transcript, words_of, prepare_suggestions


class CutReview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: str
    selected_takes: dict[str, int] = Field(default_factory=dict, max_length=1000)
    keep_discards: dict[str, bool] = Field(default_factory=dict, max_length=1000)
    pause_threshold: float = Field(default=1.2, ge=.5, le=5)
    breathing: float = Field(default=.18, ge=.05, le=.5)


def propose_groups(transcript):
    from .groq_api import GroqDirectorClient
    words=words_of(transcript)
    prompt='''Monta il parlato di una registrazione grezza con riprese ripetute e conversazioni
tra autore e regista. Il risultato è SOLO il testo realmente recitato, con l'ultima
take completa per ciascuna frase e senza conversazioni sul come recitarlo.
Devi esaminare TUTTE le parole dalla prima all'ultima: non lasciare regia o errori
prima, fra o dopo le take. Battute come "vai", "allora vai", "più piano", "molto
meglio", "non va bene", "puoi fare un'altra versione", "fammelo con...", discussioni
sulla formulazione e commenti a chi registra vanno in discards quando il contesto
dimostra che sono fuori scena. Domande alternative abbandonate e frammenti non
completati vanno in discards. Non accorciare la versione valida arbitrariamente.
Trova ripartenze e tentativi della STESSA frase: il parlante prova, sbaglia e ripete.
Non tagliare ripetizioni intenzionali, enfasi o frasi con informazioni nuove realmente recitate.
Le indicazioni di regia fra le riprese NON interrompono un gruppo: includi TUTTE
le esecuzioni della stessa frase e scegli l'ultima completa, anche se cambia una
parola ('ora parto' / 'adesso parto'). Ogni take è un intervallo di indici parola
inclusivi [prima,ultima]. Includi tutte le parole della take, anche quelle sbagliate,
senza inglobare frasi uniche. Take e gruppi non possono sovrapporsi. L'ultima take
deve essere completa. Se l'ultimo tentativo è incompleto, lascia come ultima take
quello completo precedente e proponi il frammento successivo in discards.
Proponi anche discards per battute fuori scena, indicazioni di regia, commenti
sull'esecuzione, tentativi abbandonati senza sostituto e sporcature inequivocabili.
Non scartare testo utile al racconto, presentazioni o altre frasi complete perché
sono un argomento diverso: conservare l'ultima versione completa di OGNI frase.
Un gruppo deve contenere almeno DUE take; una frase detta una sola volta resta.
Non mettere in discards le vecchie take: le rappresenti solo nei gruppi.
Ogni scarto ha range [prima,ultima], reason e confidence.
Gli scarti non possono sovrapporsi alle take o ad altri scarti.
La confidenza misura se è davvero una correzione: sotto .85
richiede revisione. Non inventare parole né tempi. Non eliminare parti solo perché
suonano informali. Restituisci groups con takes, reason in italiano e confidence.
Trascrizione: indice:parola, [PAUSA] indica una pausa superiore a 1.2 secondi.\n'''+ ' '.join(
        ('[PAUSA] ' if i and w['start']-words[i-1]['end']>1.2 else '')+f"{w['index']}:{w['text']}"
        for i,w in enumerate(words))
    prompt+='\nCHECK FINALE OBBLIGATORIO: simula il testo risultante dopo i tuoi tagli. Deve essere una recitazione pulita coerente. Se rimangono regia, commenti o versioni precedenti della stessa frase, correggi groups/discards prima di rispondere. Conserva le presentazioni valide del parlante.'
    schema={'type':'object','additionalProperties':False,'required':['groups','discards'],'properties':{
        'discards':{'type':'array','items':{'type':'object','additionalProperties':False,
            'required':['range','reason','confidence'],'properties':{
                'range':{'type':'array','items':{'type':'integer'}},'reason':{'type':'string'},'confidence':{'type':'number'}}}},
        'groups':{'type':'array','items':{'type':'object','additionalProperties':False,
            'required':['takes','reason','confidence'],'properties':{
                'takes':{'type':'array','minItems':2,'items':{'type':'array','minItems':2,'maxItems':2,'items':{'type':'integer'}}},
                'reason':{'type':'string'},'confidence':{'type':'number'}}}}}}
    reply=GroqDirectorClient(os.environ.get('GROQ_API_KEY',''),model='openai/gpt-oss-120b',
        fallback_models=(),thinking_level='high',max_retries_per_model=0).generate_json(prompt,schema)
    return reply.data


def choose_complete_takes(transcript,groups):
    """A separate editorial check chooses the last *valid* take, not the last fragment."""
    from .groq_api import GroqDirectorClient
    words=words_of(transcript)
    context=' '.join(w['text'] for w in words)
    candidates=[{'group':i,'takes':[' '.join(w['text'] for w in words[a:b+1]) for a,b in g['takes']]} for i,g in enumerate(groups)]
    prompt='''Controlla un montaggio di registrazione grezza. Per OGNI gruppo scegli
l'ULTIMA TAKE COMPLETA e grammaticalmente recitata, non semplicemente l'ultima:
un frammento, una ripartenza, una frase mescolata a commenti di regia o due versioni
incollate NON sono validi. Se l'ultima è sbagliata torna all'ultima corretta precedente.
Se il contesto mostra che quel gruppo è una domanda/formulazione proposta e poi
abbandonata (ad esempio il regista rifiuta due domande e sceglie un'altra frase),
selected_take=-2 scarta l'intero gruppo. -1 significa incerto: conserva tutte per revisione.
Mai scartare una presentazione valida. Indici take da zero, separati per gruppo.
Restituisci esattamente una scelta per ciascun gruppo, reason e confidence.
Scrivi reason in italiano.
CONTESTO INTEGRALE:\n'''+context+'\nGRUPPI:\n'+json.dumps(candidates,ensure_ascii=False)
    schema={'type':'object','additionalProperties':False,'required':['choices'],'properties':{
        'choices':{'type':'array','items':{'type':'object','additionalProperties':False,
        'required':['group','selected_take','reason','confidence'],'properties':{
            'group':{'type':'integer'},'selected_take':{'type':'integer'},
            'reason':{'type':'string'},'confidence':{'type':'number'}}}}}}
    if not groups:return groups
    reply=GroqDirectorClient(os.environ.get('GROQ_API_KEY',''),model='openai/gpt-oss-120b',
        fallback_models=(),thinking_level='high',max_retries_per_model=0).generate_json(prompt,schema)
    choices=reply.data['choices']
    if len(choices)!=len(groups) or {c['group'] for c in choices}!=set(range(len(groups))):
        raise ValueError('Revisione delle take incompleta')
    result=[dict(g) for g in groups]
    for c in choices:
        i=c['group'];selected=c['selected_take']
        if type(selected) is not int or not -2<=selected<len(result[i]['takes']):
            raise ValueError('Scelta della take fuori intervallo')
        result[i]['selected_take']=selected if c['confidence']>=.85 else -1
        result[i]['selection_reason']=c['reason']
        result[i]['confidence']=min(result[i]['confidence'],c['confidence'])
    return result


def render_cut(source, target, plan, *, preview=False):
    from fractions import Fraction
    rate=float(Fraction(plan['fps']))
    selected='+'.join(f"gte(n,{s['source_in_frame']})*lt(n,{s['source_out_frame']})" for s in plan['segments'])
    # fps establishes a 1/fps timebase: integer N avoids floating point losing a tick.
    video=f"[0:v]fps={plan['fps']},select='{selected}',setpts=N"
    if preview:video+=',scale=-2:540'
    filters=[video+'[v]']; inputs=[]
    for i,s in enumerate(plan['segments']):
        a,b=s['source_in_frame'],s['source_out_frame']
        filters.append(f'[0:a]atrim=start={a/rate:.9f}:end={b/rate:.9f},asetpts=PTS-STARTPTS,apad=whole_dur={(b-a)/rate:.9f},atrim=duration={(b-a)/rate:.9f}[a{i}]')
        inputs.append(f'[a{i}]')
    filters.append(''.join(inputs)+f'concat=n={len(inputs)}:v=0:a=1[a]')
    graph=target.with_suffix('.fffilter'); graph.write_text(';\n'.join(filters),encoding='utf-8')
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),'-filter_complex_script',str(graph),
        '-map','[v]','-map','[a]','-r',plan['fps'],'-fps_mode','cfr','-c:v','libx264','-preset','veryfast','-crf','23' if preview else '18',
        '-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(target)],
        check=True,capture_output=True,timeout=900)


def install_cut_routes(app,store,root,load_project,active_run):
    jobs={}; tasks=set()

    def paths(pid):
        p=load_project(pid)
        if not p.source_video or not p.source_video.has_audio:
            raise HTTPException(422,'CUT richiede un video con audio')
        folder=root/pid/'cut'; folder.mkdir(parents=True,exist_ok=True)
        return p,folder

    def read(path): return json.loads(path.read_text(encoding='utf-8'))

    def current(pid):
        p,folder=paths(pid)
        if not (folder/'plan.json').is_file(): raise HTTPException(404,'Nessuna proposta CUT')
        plan=read(folder/'plan.json')
        if plan['source_signature']!=p.analysis_signature:
            raise HTTPException(409,'La sorgente è cambiata: rianalizza CUT')
        return p,folder,plan

    def state(pid):
        _,folder=paths(pid)
        job=jobs.get(pid)
        if job: return dict(job)
        saved=read(folder/'job.json') if (folder/'job.json').is_file() else {'status':'idle'}
        if saved.get('status')=='running':
            saved={'status':'failed','message':'Operazione interrotta dal riavvio. Rilancia CUT.','completed':0,'total':4}
        return saved

    async def launch(pid,kind,operation):
        p,folder=paths(pid)
        if jobs.get(pid,{}).get('status')=='running' or active_run(root/pid/'run'):
            raise HTTPException(409,'Attendi la fine dell’operazione in corso')
        job={'id':uuid.uuid4().hex,'kind':kind,'status':'running','completed':0,'total':4,'message':'Avvio CUT'}
        jobs[pid]=job; write_json(folder/'job.json',job)
        def progress(done,message):
            job.update(completed=done,message=message);write_json(folder/'job.json',dict(job))
        async def run():
            try:
                result=await asyncio.to_thread(operation,p,folder,progress)
                job.update(status='succeeded',completed=4,message='Operazione CUT completata',result=result)
            except Exception as exc:
                message=str(exc)
                if isinstance(exc,subprocess.CalledProcessError):
                    message=(exc.stderr or b'').decode('utf-8',errors='replace')[-1800:]
                job.update(status='failed',message=message,error_type=type(exc).__name__)
            write_json(folder/'job.json',dict(job))
        task=asyncio.create_task(run());tasks.add(task);task.add_done_callback(tasks.discard)
        return dict(job)

    @app.get('/api/curation/projects/{pid}/cut')
    async def get_cut(pid:str):
        _,folder=paths(pid)
        payload={'job':state(pid),'plan':None}
        if (folder/'plan.json').is_file():
            _,_,plan=current(pid)
            payload['plan']=plan; payload['text']=clean_transcript(read(folder/'transcript-original.json'),plan)['text']
        return payload

    @app.post('/api/curation/projects/{pid}/cut/analyze')
    async def analyze_cut(pid:str):
        def operation(p,folder,progress):
            from .cloud_analyze_cli import transcribe_groq
            cached=folder/'transcript-original.json'; signature=folder/'source-signature.json'
            progress(0,'Trascrizione integrale con tempi per parola…')
            if cached.is_file() and signature.is_file() and read(signature).get('signature')==p.analysis_signature:
                raw=read(cached)
            else:
                raw=transcribe_groq(Path(p.source_video.path),folder)
                write_json(cached,raw);write_json(signature,{'signature':p.analysis_signature})
            progress(1,'Trascrizione pronta · riconosco ripartenze e take…')
            suggestion=propose_groups(raw)
            if not isinstance(suggestion,dict):suggestion={'groups':suggestion,'discards':[]}
            write_json(folder/'suggestions.json',suggestion)
            groups,discards,warnings=prepare_suggestions(suggestion)
            progress(2,'Verifico l’ultima take completa di ciascuna frase…')
            groups=choose_complete_takes(raw,groups)
            write_json(folder/'reviewed-suggestions.json',{'groups':groups,'discards':discards})
            progress(2,'Take verificate · calcolo tagli e tempi del montaggio…')
            plan=build_cut_plan(raw,duration=p.source_video.duration,fps=p.source_video.fps,
                signature=p.analysis_signature,groups=groups,discards=discards)
            plan['warnings']=warnings
            write_json(folder/'plan.json',plan)
            progress(3,'Proposta salvata · preparo la revisione')
            return {'revision':plan['revision'],'groups':len(plan['groups'])}
        return await launch(pid,'analyze',operation)

    @app.get('/api/curation/projects/{pid}/cut/words')
    async def original_words(pid:str):
        _,folder,_=current(pid)
        return {'words':words_of(read(folder/'transcript-original.json'))}

    @app.post('/api/curation/projects/{pid}/cut/rebuild')
    async def rebuild_cut(pid:str):
        def operation(p,folder,progress):
            if read(folder/'source-signature.json').get('signature')!=p.analysis_signature:
                raise ValueError('La sorgente è cambiata: rianalizza CUT')
            progress(1,'Ricalcolo della proposta salvata · nessuna nuova trascrizione')
            raw=read(folder/'transcript-original.json')
            groups,discards,warnings=prepare_suggestions(read(folder/'suggestions.json'))
            if (folder/'reviewed-suggestions.json').is_file():
                progress(2,'Riutilizzo la revisione delle take salvata…')
                groups,discards,warnings=prepare_suggestions(read(folder/'reviewed-suggestions.json'))
            else:
                progress(2,'Verifico le take complete nella proposta salvata…')
                groups=choose_complete_takes(raw,groups)
                write_json(folder/'reviewed-suggestions.json',{'groups':groups,'discards':discards})
            plan=build_cut_plan(raw,duration=p.source_video.duration,fps=p.source_video.fps,
                signature=p.analysis_signature,groups=groups,discards=discards)
            plan['warnings']=warnings
            write_json(folder/'plan.json',plan)
            progress(3,'Proposta ricostruita')
            return {'revision':plan['revision']}
        return await launch(pid,'rebuild',operation)

    @app.put('/api/curation/projects/{pid}/cut')
    async def review_cut(pid:str,request:CutReview):
        p,folder,plan=current(pid)
        if state(pid).get('status')=='running': raise HTTPException(409,'CUT sta lavorando')
        if request.revision!=plan['revision']: raise HTTPException(409,'Proposta modificata: ricarica')
        groups=[dict(g) for g in plan['groups']]
        discards=[dict(d) for d in plan.get('discards',[])]
        try:
            for key,selected in request.selected_takes.items():
                index=int(key)
                if not 0<=index<len(groups): raise ValueError('Gruppo non valido')
                groups[index]['selected_take']=selected
            for key,keep in request.keep_discards.items():
                index=int(key)
                if not 0<=index<len(discards):raise ValueError('Scarto non valido')
                discards[index]['keep']=keep
            new=build_cut_plan(read(folder/'transcript-original.json'),duration=p.source_video.duration,
                fps=p.source_video.fps,signature=p.analysis_signature,groups=groups,discards=discards,
                pause_threshold=request.pause_threshold,breathing=request.breathing)
        except (ValueError,IndexError,KeyError) as exc: raise HTTPException(422,str(exc)) from exc
        write_json(folder/'plan.json',new)
        return {'plan':new,'text':clean_transcript(read(folder/'transcript-original.json'),new)['text']}

    @app.post('/api/curation/projects/{pid}/cut/preview')
    async def preview_cut(pid:str):
        _,_,plan=current(pid)
        def operation(p,folder,progress):
            progress(1,'Creo l’anteprima del montaggio CUT…')
            target=folder/('preview-'+plan['revision']+'.mp4')
            if not target.is_file(): render_cut(Path(p.source_video.path),target,plan,preview=True)
            progress(3,'Anteprima pronta')
            return {'url':f'/api/curation/projects/{pid}/cut/preview/{plan["revision"]}'}
        return await launch(pid,'preview',operation)

    @app.get('/api/curation/projects/{pid}/cut/preview/{revision}')
    async def preview_file(pid:str,revision:str):
        _,folder,plan=current(pid)
        if revision!=plan['revision']: raise HTTPException(409,'Anteprima non aggiornata')
        target=folder/('preview-'+plan['revision']+'.mp4')
        if not target.is_file(): raise HTTPException(404,'Genera prima l’anteprima')
        return FileResponse(target,media_type='video/mp4')

    @app.post('/api/curation/projects/{pid}/cut/confirm')
    async def confirm_cut(pid:str,request:CutReview):
        _,_,plan=current(pid)
        if request.revision!=plan['revision']: raise HTTPException(409,'Proposta modificata: ricarica')
        def operation(p,folder,progress):
            from .debug_run_cli import build_short_outline,analysis_input_signature
            if plan.get('clean_project_id'):
                existing=store.load(plan['clean_project_id'])
                return {'project_id':existing.project_id}
            progress(0,'Creo il video pulito alla risoluzione originale…')
            target=folder/('clean-'+plan['revision']+'.mp4')
            if not target.is_file(): render_cut(Path(p.source_video.path),target,plan)
            if store.load(pid).analysis_signature!=p.analysis_signature:
                raise ValueError('La sorgente è cambiata durante il render: rianalizza CUT')
            progress(1,'Video pronto · preparo la versione CUT del progetto…')
            child=store.create(p.name+' · CUT')
            own_source=root/child.project_id/'source'/'clean.mp4'
            own_source.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(target,own_source)
            child=store.register_local_video(child.project_id,own_source)
            store.extract_source_audio(child.project_id)
            child=store.load(child.project_id)
            run=root/child.project_id/'run';run.mkdir(parents=True,exist_ok=True)
            raw=clean_transcript(read(folder/'transcript-original.json'),plan)
            outline,chunks=build_short_outline(raw)
            write_json(run/'transcript-raw.json',raw);write_json(run/'semantic-chunks.json',chunks)
            write_json(run/'semantic-beats.json',outline)
            write_json(run/'run-input.json',analysis_input_signature(Path(child.source_video.path),Path(child.guide_audio.path)))
            write_json(run/'analysis-signature.json',{'analysis_signature':child.analysis_signature})
            write_json(root/child.project_id/'cut-origin.json',{'project_id':pid,'plan':plan,'source_path':p.source_video.path})
            progress(3,'Testo pulito e tempi salvati · progetto originale conservato')
            plan.update(status='confirmed',clean_project_id=child.project_id)
            write_json(folder/'plan.json',plan)
            return {'project_id':child.project_id}
        return await launch(pid,'confirm',operation)
