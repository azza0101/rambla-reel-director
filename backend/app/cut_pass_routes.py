"""Project-scoped asynchronous CUT analysis and review. Never calls Resolve."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
import subprocess
import uuid
import time

from fastapi import HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from .atomic_io import write_json
from .cut_pass import build_cut_plan, clean_transcript, words_of, prepare_suggestions, review_words


class CutReview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: str
    selected_takes: dict[str, int] = Field(default_factory=dict, max_length=1000)
    keep_discards: dict[str, bool] = Field(default_factory=dict, max_length=1000)
    tight_pauses: bool | None = None
    pause_mode: str | None = Field(default=None, pattern="^(soft|medium|strong)$")
    excluded_word_indices: list[int] | None = Field(default=None, max_length=100000)
    pause_threshold: float = Field(default=1.2, ge=.5, le=5)
    breathing: float = Field(default=.18, ge=.05, le=.5)
    end_margin_ms: int | None = Field(default=None, ge=0, le=400)


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
    from .cut_cloud import word_windows,query_json,merge_suggestions
    windows=word_windows(words)
    header=prompt.split('Trascrizione:')[0]+'Trascrizione con INDICI ORIGINALI: non rinumerare.\n'
    replies=[]
    for i,window in enumerate(windows):
        text=' '.join(f"{w['index']}:{w['text']}" for w in window)
        replies.append(query_json(header+text,schema,f'Riconosco take · blocco {i+1}/{len(windows)}'))
    return merge_suggestions(replies)


def choose_complete_takes(transcript,groups):
    """A separate editorial check chooses the last *valid* take, not the last fragment."""
    from .groq_api import GroqDirectorClient
    from .cut_boundaries import review_take_boundaries
    groups=review_take_boundaries(transcript,groups)
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
    from .cut_cloud import pack_items,query_json
    batches=pack_items(candidates,max_chars=3000,max_items=5)
    header=prompt.split('CONTESTO INTEGRALE:')[0]
    choices=[]
    for i,batch in enumerate(batches):
        relevant=[]
        for item in batch:
            for a,b in groups[item['group']]['takes']:
                relevant.extend(w['text'] for w in words[max(0,a-8):min(len(words),b+9)])
        local=' '.join(relevant)[:1600]
        data=query_json(header+'\nCONTESTO LOCALE:\n'+local+'\nGRUPPI:\n'+json.dumps(batch,ensure_ascii=False),schema,f'Scelgo take complete · blocco {i+1}/{len(batches)}')
        choices.extend(data['choices'])
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


def verify_cut_render(target, plan):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
        'stream=codec_type,nb_frames', '-of', 'json', str(target)],
        check=True, capture_output=True, text=True, timeout=30)
    streams = json.loads(probe.stdout).get('streams') or []
    video = next((s for s in streams if s.get('codec_type') == 'video'), {})
    if int(video.get('nb_frames') or 0) != plan['duration_frames'] or not any(s.get('codec_type') == 'audio' for s in streams):
        raise ValueError('MP4 CUT incompleto o di una revisione diversa: rigenera il download')


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
    temporary = target.with_name(target.stem + '-' + uuid.uuid4().hex + '.partial.mp4')
    try:
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),'-filter_complex_script',str(graph),
            '-map','[v]','-map','[a]','-r',plan['fps'],'-fps_mode','cfr','-c:v','libx264','-preset','veryfast','-crf','23' if preview else '18',
            '-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(temporary)],
            check=True,capture_output=True,timeout=900)
        verify_cut_render(temporary, plan)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def install_cut_routes(app,store,root,load_project,active_run):
    jobs={}; tasks=set()

    def paths(pid):
        p=load_project(pid)
        if not p.source_video or not p.source_video.has_audio:
            raise HTTPException(422,'CUT richiede un video con audio')
        folder=root/pid/'cut'; folder.mkdir(parents=True,exist_ok=True)
        return p,folder

    def read(path): return json.loads(path.read_text(encoding='utf-8'))

    def timing_read(folder):
        aligned=folder/'transcript-aligned.json'
        signature=folder/'alignment-signature.json'
        if aligned.is_file() and signature.is_file() and (folder/'source-signature.json').is_file():
            if read(signature)==read(folder/'source-signature.json'):return read(aligned)
        return read(folder/'transcript-original.json')

    def align_plan(p,folder,plan,progress):
        from .cut_alignment import refine_cut_timing
        aligned,warnings=refine_cut_timing(read(folder/'transcript-original.json'),plan,
            Path(p.source_video.path),folder,progress=lambda done,total:progress(2+.8*done/max(1,total),f'Riallineo parole e fine frase · take {done+1}/{total}'))
        write_json(folder/'transcript-aligned.json',aligned)
        write_json(folder/'alignment-signature.json',{'signature':p.analysis_signature})
        adjusted=build_cut_plan(aligned,duration=p.source_video.duration,fps=p.source_video.fps,
            signature=p.analysis_signature,groups=plan['groups'],discards=plan.get('discards',[]),
            pause_threshold=plan['pause_threshold'],breathing=plan['breathing'],excluded_word_indices=plan.get('excluded_word_indices',[]),tight_pauses=plan.get('tight_pauses',False),pause_mode=plan.get('pause_mode','soft'),silence_intervals=plan.get('silence_intervals',[]),end_margin_ms=plan.get('end_margin_ms',0))
        adjusted['warnings']=list(dict.fromkeys([w for w in plan.get('warnings',[]) if not w.startswith('Take ')]+warnings))
        return adjusted

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
        job={'id':uuid.uuid4().hex,'kind':kind,'status':'running','completed':0,'total':4,'message':'Avvio CUT',
            'started_at':time.time(),'updated_at':time.time(),'history':[], 'source_signature':p.analysis_signature}
        jobs[pid]=job; write_json(folder/'job.json',job)
        def progress(done,message):
            from .magic_usage import check_current
            check_current()
            stamp=time.time()
            job.update(completed=max(job['completed'],done),message=message,updated_at=stamp)
            job['history'].append({'completed':done,'message':message,'at':stamp})
            job['history']=job['history'][-30:]
            write_json(folder/'job.json',dict(job))
        async def run():
            try:
                def work():
                    from .cut_cloud import cloud_context
                    with cloud_context(folder,lambda message:progress(job['completed'],message)):
                        return operation(p,folder,progress)
                result=await asyncio.to_thread(work)
                job.update(status='succeeded',completed=4,message='Operazione CUT completata',result=result,finished_at=time.time())
            except Exception as exc:
                message=str(exc)
                if isinstance(exc,subprocess.CalledProcessError):
                    message=(exc.stderr or b'').decode('utf-8',errors='replace')[-1800:]
                job.update(status='failed',message=message,error_type=type(exc).__name__,finished_at=time.time())
            write_json(folder/'job.json',dict(job))
        task=asyncio.create_task(run());tasks.add(task);task.add_done_callback(tasks.discard)
        return dict(job)

    @app.get('/api/curation/projects/{pid}/cut')
    async def get_cut(pid:str):
        p,folder=paths(pid)
        payload={'job':state(pid),'plan':None}
        origin=root/pid/'cut-origin.json'
        if origin.is_file() and Path(p.source_video.path).resolve()==(root/pid/'source'/'clean.mp4').resolve():
            payload['confirmed_preview_url']=f'/api/curation/projects/{pid}/media/source-video/source'
            saved_origin=read(origin)
            payload['cut_parent_project_id']=saved_origin['project_id']
            payload['confirmed_duration_seconds']=p.source_video.duration
            payload['original_duration_seconds']=saved_origin['plan']['source_duration_frames']/float(__import__('fractions').Fraction(saved_origin['plan']['fps']))
        review_pid, review_folder = pid, folder
        if origin.is_file() and Path(p.source_video.path).resolve()==(root/pid/'source'/'clean.mp4').resolve():
            saved_origin = read(origin)
            review_pid = str(saved_origin['project_id'])
            review_folder = root/review_pid/'cut'
        if (review_folder/'plan.json').is_file():
            try:
                _,_,plan=current(review_pid)
            except HTTPException as exc:
                if exc.status_code!=409:raise
                payload['source_changed']=True
                return payload
            timing = timing_read(review_folder)
            payload['plan']=plan; payload['text']=clean_transcript(timing,plan)['text']
            payload['words']=review_words(timing,plan)
        return payload

    @app.post('/api/curation/projects/{pid}/cut/analyze')
    async def analyze_cut(pid:str):
        def operation(p,folder,progress):
            from .cloud_analyze_cli import transcribe_groq
            from .cut_analysis_service import analyze_cut_project
            return analyze_cut_project(p,folder,progress,transcribe=transcribe_groq,
                propose=propose_groups,choose=choose_complete_takes,align=align_plan)
        return await launch(pid,'analyze',operation)

    @app.get('/api/curation/projects/{pid}/cut/words')
    async def original_words(pid:str):
        _,folder,_=current(pid)
        return {'words':words_of(timing_read(folder))}

    @app.post('/api/curation/projects/{pid}/cut/realign')
    async def realign_cut(pid:str):
        _,_,plan=current(pid)
        def operation(p,folder,progress):
            adjusted=align_plan(p,folder,plan,progress)
            write_json(folder/'plan.json',adjusted)
            return {'revision':adjusted['revision']}
        return await launch(pid,'realign',operation)

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

    @app.post('/api/curation/projects/{pid}/cut/residual')
    async def repair_residual(pid:str):
        def operation(p,folder,progress):
            from .cut_residual import review_residual_takes
            _,_,old=current(pid)
            progress(1,'Cerco frasi interrotte e ripartenze nel testo mantenuto…')
            new=review_residual_takes(timing_read(folder),old)
            progress(3,'Ripartenze verificate · conservo scelte e tempi originali…')
            write_json(folder/('plan-backup-residual-'+str(time.time_ns())+'.json'),old)
            write_json(folder/'plan.json',new)
            return {'revision':new['revision']}
        return await launch(pid,'residual',operation)

    @app.post('/api/curation/projects/{pid}/cut/boundaries')
    async def repair_boundaries(pid:str):
        def operation(p,folder,progress):
            from .cut_boundaries import review_take_boundaries
            _,_,old=current(pid)
            raw=timing_read(folder)
            progress(1,'Verifico i confini semantici delle take…')
            groups=review_take_boundaries(raw,old['groups'])
            progress(3,'Separo le frasi indipendenti e conservo le scelte…')
            new=build_cut_plan(raw,duration=p.source_video.duration,fps=p.source_video.fps,
                signature=p.analysis_signature,groups=groups,discards=old.get('discards',[]),
                pause_threshold=old['pause_threshold'],breathing=old['breathing'],
                excluded_word_indices=old.get('excluded_word_indices',[]),tight_pauses=old.get('tight_pauses',False),pause_mode=old.get('pause_mode','soft'),silence_intervals=old.get('silence_intervals',[]),end_margin_ms=old.get('end_margin_ms',0))
            new['warnings']=old.get('warnings',[])
            write_json(folder/('plan-backup-boundaries-'+str(time.time_ns())+'.json'),old)
            write_json(folder/'boundary-review.json',{'source_signature':p.analysis_signature,'groups':groups})
            write_json(folder/'plan.json',new)
            return {'revision':new['revision']}
        return await launch(pid,'boundaries',operation)

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
                groups[index]['user_selected_take']=True
            for key,keep in request.keep_discards.items():
                index=int(key)
                if not 0<=index<len(discards):raise ValueError('Scarto non valido')
                discards[index]['keep']=keep
            silences=plan.get('silence_intervals',[])
            if request.tight_pauses is True and not silences:
                from .cut_silence import detect_silences
                silences=await asyncio.to_thread(detect_silences,Path(p.source_video.path),p.source_video.duration)
            new=build_cut_plan(timing_read(folder),duration=p.source_video.duration,
                fps=p.source_video.fps,signature=p.analysis_signature,groups=groups,discards=discards,
                pause_threshold=request.pause_threshold,breathing=request.breathing,
                excluded_word_indices=plan.get("excluded_word_indices",[]) if request.excluded_word_indices is None else request.excluded_word_indices,
                tight_pauses=plan.get("tight_pauses",False) if request.tight_pauses is None else request.tight_pauses,
                pause_mode=request.pause_mode or plan.get("pause_mode","soft"),silence_intervals=silences,end_margin_ms=request.end_margin_ms if request.end_margin_ms is not None else plan.get('end_margin_ms',0))
        except (ValueError,IndexError,KeyError) as exc: raise HTTPException(422,str(exc)) from exc
        new['warnings']=plan.get('warnings',[])
        write_json(folder/'plan.json',new)
        return {'plan':new,'text':clean_transcript(timing_read(folder),new)['text'],'words':review_words(timing_read(folder),new)}

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

    def download_source(pid):
        origin_path = root / pid / 'cut-origin.json'
        if origin_path.is_file():
            origin = read(origin_path)
            plan = origin['plan']
            # The confirmed child's source is its own full-resolution CUT render.
            p, folder = paths(pid)
            return plan, Path(p.source_video.path), folder, True
        p, folder, plan = current(pid)
        return plan, Path(p.source_video.path), folder, False

    @app.post('/api/curation/projects/{pid}/cut/download')
    async def download_cut(pid: str):
        plan, source, _, confirmed = download_source(pid)
        def operation(p, folder, progress):
            target = source if confirmed else folder / ('clean-' + plan['revision'] + '.mp4')
            progress(1, 'Preparo MP4 CUT alla risoluzione originale…')
            ready = False
            if target.is_file():
                try:
                    verify_cut_render(target, plan)
                    ready = True
                except (ValueError, subprocess.SubprocessError):
                    pass
            if not ready:
                if confirmed:
                    raise ValueError('Video CUT confermato non disponibile')
                render_cut(source, target, plan)
            if not confirmed and store.load(pid).analysis_signature != plan['source_signature']:
                raise ValueError('Sorgente modificata durante il render: ricalcola CUT')
            progress(3, 'MP4 CUT pronto da scaricare')
            return {'download_url': f'/api/curation/projects/{pid}/cut/download/{plan["revision"]}'}
        return await launch(pid, 'download', operation)

    @app.get('/api/curation/projects/{pid}/cut/download/{revision}')
    async def download_cut_file(pid: str, revision: str):
        plan, source, folder, confirmed = download_source(pid)
        if revision != plan['revision']:
            raise HTTPException(409, 'CUT modificato: genera il download aggiornato')
        target = source if confirmed else folder / ('clean-' + revision + '.mp4')
        if not target.is_file():
            raise HTTPException(404, 'Genera prima il download MP4 CUT')
        try:
            verify_cut_render(target, plan)
        except (ValueError, subprocess.SubprocessError) as exc:
            raise HTTPException(409, 'MP4 CUT incompleto: rigenera il download') from exc
        return FileResponse(target, media_type='video/mp4', filename=f'RMBL-CUT-{pid}-{revision}.mp4')

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
            raw=clean_transcript(timing_read(folder),plan)
            outline,chunks=build_short_outline(raw)
            write_json(run/'transcript-raw.json',raw);write_json(run/'semantic-chunks.json',chunks)
            write_json(run/'semantic-beats.json',outline)
            write_json(run/'run-input.json',analysis_input_signature(Path(child.source_video.path),Path(child.guide_audio.path)))
            write_json(run/'analysis-signature.json',{'analysis_signature':child.analysis_signature})
            source_stat = Path(p.source_video.path).stat()
            write_json(root/child.project_id/'cut-origin.json',{'project_id':pid,'plan':plan,'source_path':p.source_video.path,
                'source_signature': p.source_video.signature,
                'source_identity': {'size': source_stat.st_size, 'mtime_ns': source_stat.st_mtime_ns}})
            progress(3,'Testo pulito e tempi salvati · progetto originale conservato')
            plan.update(status='confirmed',clean_project_id=child.project_id)
            write_json(folder/'plan.json',plan)
            return {'project_id':child.project_id}
        return await launch(pid,'confirm',operation)

    from .cut_analysis_service import CutEngine
    engine = CutEngine({'analyze':analyze_cut, 'boundaries':repair_boundaries,
        'residual':repair_residual, 'review':review_cut, 'confirm':confirm_cut}, state, current)
    app.state.cut_engine = engine
    return engine
