"""Validate that alternative takes cover one shared meaning, preserving outside text."""
from __future__ import annotations
import json
import os
import re
from .cut_pass import words_of


def apply_boundary_review(transcript, groups, decisions):
    words=words_of(transcript)
    expected={(gi,ti) for gi,g in enumerate(groups) for ti in range(len(g['takes']))}
    received=[(d['group'],d['take']) for d in decisions]
    if len(received)!=len(set(received)) or set(received)!=expected:
        raise ValueError('Revisione confini take incompleta')
    lookup={(d['group'],d['take']):d for d in decisions}
    result=[]
    for gi,g in enumerate(groups):
        takes=[];mapping={};separated=[]
        for ti,(a,b) in enumerate(g['takes']):
            d=lookup[gi,ti]
            if type(d['equivalent']) is not bool:raise ValueError('Equivalenza take non valida')
            start,end=d['start'],d['end']
            if any(type(i) is not int for i in (start,end)) or not a<=start<=end<=b:
                raise ValueError('Confini take fuori intervallo originale')
            # Never reduce a complete version to the common prefix of an unfinished take.
            # Relative clauses, appositions and prepositional complements complete that meaning.
            if d['equivalent'] and end<b:
                following=re.sub(r'[^\w]', '', words[end+1]['text'].casefold())
                if following in {'a','ad','al','alla','alle','ai','allo','agli','di','del','della','delle','dei','degli','dello','da','dal','dalla','dalle','con','che','cui','per','tra','fra'}:
                    end=b
            if not d['equivalent']:
                separated.append({'range':[a,b],'reason':d['reason']})
                continue
            mapping[ti]=len(takes);takes.append([start,end])
            if start>a:separated.append({'range':[a,start-1],'reason':d['reason']})
            if end<b:separated.append({'range':[end+1,b],'reason':d['reason']})
        if len(takes)<2:
            # Nothing is removed when there is no verified alternative.
            continue
        chosen=g.get('selected_take',len(g['takes'])-1)
        chosen=mapping.get(chosen,-1) if chosen>=0 else chosen
        result.append({**g,'takes':takes,'selected_take':chosen,'boundaries_reviewed':True,
                       'separated_passages':separated})
    return result


def review_take_boundaries(transcript,groups):
    if not groups:return []
    from .groq_api import GroqDirectorClient
    words=words_of(transcript)
    candidates=[{'group':gi,'take':ti,'range':[a,b],
                'words':' '.join(f"{w['index']}:{w['text']}" for w in words[a:b+1]),
                'reference':' '.join(w['text'] for w in words[groups[gi]['takes'][0][0]:groups[gi]['takes'][0][1]+1])[:350]}
                for gi,g in enumerate(groups) for ti,(a,b) in enumerate(g['takes'])]
    prompt="""Verifica i confini SEMANTICI delle take alternative di un parlato grezzo.
Una take deve esprimere SOLO la stessa frase/concetto delle altre del suo gruppo.
Se contiene una nuova frase, un nuovo soggetto o concetto successivo, separalo:
restituisci start/end solo della frase equivalente, all'interno del range originale.
Esempio: 'come mi sentirei con una foto in salotto NOI quando creiamo itinerari
cerchiamo rispetto' termina a 'salotto'; gli itinerari sono una frase indipendente.
Non basarti solo sulla punteggiatura ASR: spesso non segna i confini reali.
Non tagliare invece completamenti, aggettivi o dettagli che completano la stessa frase.
Se una take è incompleta, NON ridurre quella completa alle sole parole in comune.
'...delle scene, a delle immagini impattanti che vorrei condividere' è UN SOLO concetto.
Un frammento come 'scattato scattato' NON è una take autonoma equivalente: equivalent=false.
Se non sei sicuro dell'equivalenza, equivalent=false; il testo sarà conservato.
Per OGNI take originale restituisci group,take,start,end,equivalent,reason in italiano.
Non inventare indici, non espandere i range. Il testo separato resta nel racconto.
CONTESTO COMPLETO:\n"""+' '.join(w['text'] for w in words)+'\nTAKE INDICIZZATE:\n'+json.dumps(candidates,ensure_ascii=False)
    schema={'type':'object','additionalProperties':False,'required':['decisions'],'properties':{
        'decisions':{'type':'array','items':{'type':'object','additionalProperties':False,
            'required':['group','take','start','end','equivalent','reason'],'properties':{
                'group':{'type':'integer'},'take':{'type':'integer'},'start':{'type':'integer'},
                'end':{'type':'integer'},'equivalent':{'type':'boolean'},'reason':{'type':'string'}}}}}}
    from .cut_cloud import pack_items,query_json
    batches=pack_items(candidates,max_chars=4200,max_items=10)
    header=prompt.split('CONTESTO COMPLETO:')[0]
    decisions=[]
    for i,batch in enumerate(batches):
        data=query_json(header+'\nTAKE INDICIZZATE (indici originali):\n'+json.dumps(batch,ensure_ascii=False,separators=(',',':')),schema,f'Verifico confini · blocco {i+1}/{len(batches)}')
        decisions.extend(data['decisions'])
    return apply_boundary_review(transcript,groups,decisions)
