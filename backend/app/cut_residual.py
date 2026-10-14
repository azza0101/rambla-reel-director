"""Second editing pass catches partial restarts missed by initial take grouping."""
import json
import os
import re
from .cut_pass import words_of,prepare_suggestions,build_cut_plan


def repetition_hints(transcript,plan,limit=50):
    """Candidate repeats include small verbal changes; they are never auto-deleted."""
    words=words_of(transcript);removed=set(plan['removed_word_indices']);occupied=set()
    for group in plan['groups']:
        for a,b in group['takes']:occupied.update(range(a,b+1))
    for d in plan.get('discards',[]):occupied.update(range(d['range'][0],d['range'][1]+1))
    aliases={'bisogna':'dovere','dobbiamo':'dovere','devo':'dovere','dovremmo':'dovere'}
    tokens=[aliases.get(re.sub(r'[^\w]', '',w['text'].casefold()),re.sub(r'[^\w]', '',w['text'].casefold())) for w in words]
    hints=[];covered=set()
    for n in range(12,3,-1):
        phrases={}
        for a in range(len(words)-n+1):
            b=a+n-1
            if any(i in removed or i in occupied for i in range(a,b+1)):continue
            if any(re.search(r'[.!?]$',words[i]['text']) for i in range(a,b)):continue
            phrases.setdefault(tuple(tokens[a:b+1]),[]).append([a,b])
        for phrase,ranges in phrases.items():
            nonoverlap=[]
            for pair in ranges:
                if not nonoverlap or pair[0]>nonoverlap[-1][1]:nonoverlap.append(pair)
            if len(nonoverlap)<2 or all(tuple(pair) in covered for pair in nonoverlap):continue
            if all(any(a==pair[0] and pair[1]<=b for h in hints for a,b in h['takes']) for pair in nonoverlap):continue
            hints.append({'takes':nonoverlap,'text':' '.join(phrase)})
            covered.update(tuple(pair) for pair in nonoverlap)
    hints.sort(key=lambda h:(-len(h['takes']),-len(h['text'].split())))
    return hints[:limit] if limit else hints


def reconcile_question_takes(transcript,plan):
    """Extend an existing short-question group when a later complete take was missed."""
    words=words_of(transcript)
    probe={**plan,'groups':[],'removed_word_indices':plan.get('excluded_word_indices',[])}
    hints=repetition_hints(transcript,probe,limit=None)
    groups=[dict(g) for g in plan['groups']];discards=[dict(d) for d in plan.get('discards',[])]
    other_occupied=[set(i for a,b in g['takes'] for i in range(a,b+1)) for g in groups]
    for gi,g in enumerate(groups):
        starts={a for a,b in g['takes']}
        for hint in hints:
            ranges=hint['takes']
            if len(ranges)<=len(g['takes']) or not starts.issubset({a for a,b in ranges}):continue
            if not words[ranges[-1][1]]['text'].endswith('?'):continue
            others=set().union(*(o for i,o in enumerate(other_occupied) if i!=gi))
            if any(others.intersection(range(a,b+1)) for a,b in ranges):continue
            old_choice=g.get('selected_take',-1)
            g['takes']=ranges
            g['selected_take']=old_choice if g.get('user_selected_take') or old_choice<0 else len(ranges)-1
            g['reason']='Ripetizioni della stessa domanda; ultima versione completa seguita dalla risposta.'
            g['boundaries_reviewed']=True
            existing=set(i for d in discards for i in range(d['range'][0],d['range'][1]+1))
            cues={'no','esatto','sì','si','perfetto','ok','vai','bene'}
            for (_,b),(a,_) in zip(ranges,ranges[1:]):
                indexes=[i for i in range(b+1,a) if i not in existing]
                if indexes and all(re.sub(r'[^\w]', '',words[i]['text'].casefold()) in cues for i in indexes):
                    blocks=[]
                    for i in indexes:
                        if blocks and i==blocks[-1][1]+1:blocks[-1][1]=i
                        else:blocks.append([i,i])
                    for pair in blocks:discards.append({'range':pair,'reason':'Conferme e regia fra take della stessa domanda','confidence':.99,'keep':False})
            break
    new=build_cut_plan(transcript,duration=plan['source_duration_frames']/float(__import__('fractions').Fraction(plan['fps'])),fps=plan['fps'],signature=plan['source_signature'],groups=groups,discards=discards,pause_threshold=plan['pause_threshold'],breathing=plan['breathing'],excluded_word_indices=plan.get('excluded_word_indices',[]),tight_pauses=plan.get('tight_pauses',False),pause_mode=plan.get('pause_mode','soft'),silence_intervals=plan.get('silence_intervals',[]))
    new['warnings']=plan.get('warnings',[])
    return new


def merge_residual_suggestions(transcript,plan,suggestion):
    groups,discards,warnings=prepare_suggestions(suggestion)
    words=words_of(transcript)
    stop={'a','e','che','di','da','in','il','lo','la','le','i','gli','un','una','mi','io','si','ci','per','con','ma','poi','più','come','è','sono','noi'}
    normalize=lambda text:re.sub(r'[^\w]', '',text.casefold())
    stem=lambda text:normalize(text)[:4] if len(normalize(text))>4 else normalize(text)
    for group in groups:
        takes=[list(t) for t in group['takes']]
        for ti,(a,b) in enumerate(takes):
            original=[normalize(w['text']) for w in words[a:b+1]]
            for oi,(oa,ob) in enumerate(takes):
                if ti==oi:continue
                other=[normalize(w['text']) for w in words[oa:ob+1]]
                if original[:3]==other[:3]:continue
                content=[stem(w['text']) for w in words[oa:ob+1] if normalize(w['text']) not in stop]
                if not content:continue
                matches=[i for i,w in enumerate(words[a:b+1]) if normalize(w['text']) not in stop and stem(w['text'])==content[0]]
                if not matches or matches[0]<4:continue
                offset=matches[0]
                common={stem(w['text']) for w in words[a+offset:b+1] if normalize(w['text']) not in stop}.intersection(content)
                if len(common)<2:continue
                start=a+offset
                if start>a and normalize(words[start-1]['text']) in {'mi','ci','si','ti','vi'}:start-=1
                takes[ti]=[start,b]
                warnings.append('Premessa unica conservata fuori dalla ripartenza parziale.')
                break
        group['takes']=takes
    occupied=set()
    for g in plan['groups']:
        for a,b in g['takes']:occupied.update(range(a,b+1))
    for d in plan.get('discards',[]):occupied.update(range(d['range'][0],d['range'][1]+1))
    accepted=[]
    for g in groups:
        indexes=set(i for a,b in g['takes'] for i in range(a,b+1))
        if occupied.intersection(indexes):
            warnings.append('Proposta ripetuta fra blocchi ignorata: scelte esistenti conservate.')
            continue
        occupied.update(indexes);accepted.append(g)
        if float(g.get('confidence',0))<.85:g['selected_take']=-1
    groups=accepted;accepted_discards=[]
    protected=set(i for g in plan['groups'] if g.get('user_selected_take') and g.get('selected_take',-1)>=0
                  for a,b in [g['takes'][g['selected_take']]] for i in range(a,b+1))
    for d in discards:
        a,b=d['range']
        if protected.intersection(range(a,b+1)):
            warnings.append('Scarto sovrapposto a una take scelta manualmente ignorato.')
            continue
        pending=[i for i in range(a,b+1) if i not in occupied]
        if len(pending)!=b-a+1:warnings.append('Scarto fra blocchi limitato alle parole non già gestite.')
        blocks=[]
        for i in pending:
            if blocks and i==blocks[-1][1]+1:blocks[-1][1]=i
            else:blocks.append([i,i])
        for pair in blocks:
            accepted_discards.append({**d,'range':pair});occupied.update(range(pair[0],pair[1]+1))
    discards=accepted_discards
    new=build_cut_plan(transcript,duration=plan['source_duration_frames']/float(__import__('fractions').Fraction(plan['fps'])),
        fps=plan['fps'],signature=plan['source_signature'],groups=plan['groups']+groups,
        discards=plan.get('discards',[])+discards,pause_threshold=plan['pause_threshold'],breathing=plan['breathing'],
        excluded_word_indices=plan.get('excluded_word_indices',[]),tight_pauses=plan.get('tight_pauses',False),pause_mode=plan.get('pause_mode','soft'),silence_intervals=plan.get('silence_intervals',[]))
    new['warnings']=plan.get('warnings',[])+warnings
    new['residual_reviewed']=True
    return new


def review_residual_takes(transcript,plan):
    from .groq_api import GroqDirectorClient
    words=words_of(transcript)
    occupied=set()
    for g in plan['groups']:
        for a,b in g['takes']:occupied.update(range(a,b+1))
    for d in plan.get('discards',[]):occupied.update(range(d['range'][0],d['range'][1]+1))
    removed=set(plan['removed_word_indices'])
    text=' '.join(f"{w['index']}:{w['text']}" for w in words if w['index'] not in removed)
    hints=repetition_hints(transcript,plan)
    anomalies=[{'index':w['index'],'text':w['text'],'start':w['start'],'end':w['end']} for w in words if w['index'] not in removed and w['end']-w['start']>1.8]
    prompt="""Sei il revisore finale di un CUT di parlato registrato con errori e ripartenze.
Esamina TUTTO il testo mantenuto. Cerca ripetizioni e tentativi INTERROTTI seguiti da una correzione,
anche se il parlante ripete SOLO la fine di una frase, cambia verbo o parole.
Esempio: 'trovarmi in paesi esotici MI AIUTANO A FAR CREDERE CHE IN MOLT...'
poi 'AIUTA A FARMI CREDERE DI AVERE molta più libertà...': le due parti in maiuscolo
sono ripartenze dello stesso predicato; preserva 'trovarmi in paesi esotici' come premessa unica.
Crea groups con takes [prima,ultima] inclusivi, selected_take (indice zero dell'ultima versione
COMPLETA), reason e confidence. Non includere premesse uniche né nuovi concetti nei range.
Un frammento interrotto è una take precedente; NON deve restare nel testo finale se ha una correzione.
Cerca anche frasi quasi identiche ripetute dopo altre frasi. Le vecchie take vanno SOLO in groups, MAI in discards: devono restare disponibili come alternative.
Solo la regia e le sporcature senza versione alternativa vanno in discards.
Niente riassunti: conserva ogni concetto utile, non tagliare solo per accorciare.
Gli indici GIA GESTITI elencati sotto sono intoccabili: non possono essere inclusi nei nuovi range.
Se una ripetizione estesa termina in un pezzo già gestito, fermati PRIMA di quel pezzo.
Controlla TUTTI i CANDIDATI RIPETUTI sotto, comprese domande brevi formulate con bisogna/dobbiamo.
Una domanda ripetuta deve lasciare una sola versione buona, quella seguita dalla risposta recitata.
'no esatto sì sì', conferme di regia fra tentativi e il parlante in ascolto sono fuori scena.
Le ANOMALIE TEMPORALI sono parole il cui timestamp ingloba attese e voci di regia;
se il testo è una conferma/regia (esatto, perfetto, sì sì) proponila negli scarti, non nel racconto.
I candidati sono suggerimenti da verificare semanticamente, non tagli obbligatori.
Le take nuove non si sovrappongono fra loro né agli scarti. Confidence < .85 conserva per revisione.
Restituisci soltanto aggiunte certe; [] se non ne trovi.
TESTO MANTENUTO:\n"""+text+'\nINDICI GIA GESTITI:\n'+json.dumps(sorted(occupied))+'\nCANDIDATI RIPETUTI:\n'+json.dumps(hints,ensure_ascii=False)+'\nANOMALIE TEMPORALI:\n'+json.dumps(anomalies,ensure_ascii=False)
    schema={'type':'object','additionalProperties':False,'required':['groups','discards'],'properties':{
        'groups':{'type':'array','items':{'type':'object','additionalProperties':False,
            'required':['takes','selected_take','reason','confidence'],'properties':{
                'takes':{'type':'array','minItems':2,'items':{'type':'array','minItems':2,'maxItems':2,'items':{'type':'integer'}}},
                'selected_take':{'type':'integer'},'reason':{'type':'string'},'confidence':{'type':'number'}}}},
        'discards':{'type':'array','items':{'type':'object','additionalProperties':False,
            'required':['range','reason','confidence'],'properties':{'range':{'type':'array','minItems':2,'maxItems':2,'items':{'type':'integer'}},'reason':{'type':'string'},'confidence':{'type':'number'}}}}}}
    from .cut_cloud import word_windows,query_json,merge_suggestions,compact_indices
    windows=word_windows([w for w in words if w['index'] not in removed],max_words=220,max_chars=2400)
    header=prompt.split('TESTO MANTENUTO:')[0]
    replies=[]
    for i,window in enumerate(windows):
        a,b=window[0]['index'],window[-1]['index']
        nearby=[h for h in hints if any(a<=x<=b or a<=y<=b for x,y in h['takes'])][:4]
        nearby_anomalies=[x for x in anomalies if a<=x['index']<=b]
        local=header+'\nTESTO MANTENUTO (indici originali):\n'+' '.join(f"{w['index']}:{w['text']}" for w in window)
        local+='\nINDICI GIA GESTITI:\n'+compact_indices(occupied)+'\nCANDIDATI:\n'+json.dumps(nearby,ensure_ascii=False)+'\nANOMALIE:\n'+json.dumps(nearby_anomalies,ensure_ascii=False)
        replies.append(query_json(local,schema,f'Verifico ripartenze · blocco {i+1}/{len(windows)}'))
    return reconcile_question_takes(transcript,merge_residual_suggestions(transcript,plan,merge_suggestions(replies)))


