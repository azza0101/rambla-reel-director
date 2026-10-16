"""Automatic word selections and bounded batches of the existing Director."""
from copy import deepcopy
from pathlib import Path
import json

from .api_first_director import director_schema, build_director_prompt, compile_director_decisions
from .editorial_import import normalized_chunks, transcript_package, import_plan
from .transcript_intents import load_phrase_intents, save_phrase_intents
from .geographic_context import places_in, beat_places, anchor_queries, conflicting_place
from .magic_store import fingerprint


def editorial_context(text):
    text = str(text)
    excerpt = text if len(text) <= 2000 else text[:1100] + ' … ' + text[len(text)//2-200:len(text)//2+200] + ' … ' + text[-450:]
    return 'Luoghi citati nel testo completo: ' + ', '.join(places_in(text)) + '\nContesto: ' + excerpt


def selection_changes(chunks, rows):
    by_id = {str(row['chunk_id']): row for row in rows}
    if len(by_id) != len(rows) or set(by_id) != {str(c['id']) for c in chunks}:
        raise ValueError('Le selezioni MAGICO devono coprire ogni frase esattamente una volta')
    output = {}
    for chunk in chunks:
        count = len(chunk.get('words') or str(chunk['text']).split())
        row = by_id[str(chunk['id'])]
        result = {}
        for key in ('coverage_word_indices', 'highlighted_word_indices'):
            values = row[key]
            if not isinstance(values, list) or any(type(i) is not int or not 0 <= i < count for i in values):
                raise ValueError('Indice parola MAGICO fuori dalla trascrizione')
            result[key] = sorted(set(values))
        length = 0
        previous = -2
        for index in result['highlighted_word_indices']:
            length = length+1 if index == previous+1 else 1
            if length > 3:
                raise ValueError('Parole evidenziate: massimo tre parole consecutive')
            previous = index
        output[str(chunk['id'])] = result
    return output


def _selection_schema():
    indices = {'type':'array','items':{'type':'integer','minimum':0}}
    row = {'type':'object','additionalProperties':False,
           'properties':{'unit_id':{'type':'string'},'coverage_word_indices':indices,'highlighted_word_indices':indices},
           'required':['unit_id','coverage_word_indices','highlighted_word_indices']}
    return {'type':'object','additionalProperties':False,'properties':{
        'global_topic':{'type':'string'},'choices':{'type':'array','items':row}},'required':['global_topic','choices']}


def run_magic_editorial(run, project_id, duration, report, *, query=None):
    from .cut_cloud import cloud_context, query_json, pack_items, word_windows
    run = Path(run)
    if query is None:
        query = lambda prompt,schema,label:query_json(prompt,schema,label,max_output_tokens=1800)
    chunks = normalized_chunks(run)
    if not chunks:
        raise ValueError('La trascrizione del CUT è vuota')
    input_signature = fingerprint(chunks)
    context = editorial_context(' '.join(c['text'] for c in chunks))
    units = []
    for chunk in chunks:
        words = chunk.get('words') or [{'text':w} for w in chunk['text'].split()]
        indexed = [{'index':i,'text':str(w.get('text') or w.get('word') or '')} for i,w in enumerate(words)]
        for window in word_windows(indexed,max_words=80,overlap=0,max_chars=1800):
            units.append({'unit_id':f"{chunk['id']}@{window[0]['index']}", 'chunk_id':str(chunk['id']),
                          'words':' '.join(f"{w['index']}:{w['text']}" for w in window),
                          'allowed':[w['index'] for w in window]})
    batches = pack_items(units,max_chars=2800,max_items=8)
    choices = {str(c['id']):dict(chunk_id=str(c['id']),coverage_word_indices=[],highlighted_word_indices=[]) for c in chunks}
    topic = ''
    with cloud_context(run/'magic-editorial-cache', lambda message:report(0,0,message)):
        for index, batch in enumerate(batches):
            prompt = ('Sei il montatore di un reel. Seleziona soltanto gli indici delle parole realmente presenti. '
                'Coperture: scegli descrizioni concrete che una ripresa possa mostrare, senza coprire necessariamente introduzione, '
                'CTA e interpretazione della persona. Parole evidenziate: pochi concetti forti, massimo tre parole consecutive; '
                'non evidenziare intere frasi. Puoi scegliere liste vuote. Non cambiare testo o unire significati distinti. '
                'Ogni unit_id deve comparire una volta; gli indici sono quelli originali indicati, non ricominciano da zero.\n'
                +context+'\nUNITA='+json.dumps([{k:v for k,v in u.items() if k!='allowed'} for u in batch],ensure_ascii=False))
            reply = query(prompt,_selection_schema(),f'Selezioni automatiche · blocco {index+1}/{len(batches)}')
            rows = reply['choices']
            expected = {u['unit_id']:u for u in batch}
            if len(rows) != len(expected) or {r['unit_id'] for r in rows} != set(expected):
                raise ValueError('Risposta selezioni incompleta: nessuna frase verrà saltata silenziosamente')
            topic = topic or str(reply['global_topic']).strip()
            for row in rows:
                unit = expected[row['unit_id']]
                for field in ('coverage_word_indices','highlighted_word_indices'):
                    if any(type(i) is not int or i not in unit['allowed'] for i in row[field]):
                        raise ValueError('Selezione AI fuori dalla finestra di parole')
                    choices[unit['chunk_id']][field].extend(row[field])
            report(index+1,len(batches)*2,'Parole chiave e passaggi da coprire identificati')
        changes = selection_changes(chunks,list(choices.values()))
        if fingerprint(normalized_chunks(run)) != input_signature:
            raise ValueError('Il testo è cambiato durante MAGICO: selezioni non sovrascritte')
        intents = load_phrase_intents(run)
        save_phrase_intents(run,changes,intents['transcript_signature'])
        package = transcript_package(run,project_id,duration)
        package_signature = fingerprint(package['chunks'])
        selected = set(package.get('coverage_selected_chunk_ids') or [])
        director_batches = pack_items([c for c in package['chunks'] if c['id'] in selected],max_chars=2000,max_items=3)
        decisions = {c['id']:dict(chunk_id=c['id'],action='KEEP_TALKING_HEAD',
            editorial_function='Conserva il parlato senza copertura',core_meaning=c['text'],subtext='',
            visual_mode='single',avoid=[],shots=[]) for c in package['chunks']}
        preceding = ''
        prior_context = {}
        for chunk in package['chunks']:
            prior_context[chunk['id']] = preceding
            preceding += ' '+chunk['text']
        for index,batch in enumerate(director_batches):
            local = {**package,'chunks':batch,'coverage_selected_chunk_ids':[c['id'] for c in batch if c['id'] in selected]}
            prompt = build_director_prompt(local)+'\nCONTESTO COMPLETO COMPATTO:\n'+context
            prompt += '\nSe il testo parla esplicitamente di un evento storico o violenza, rappresenta quel significato: '
            prompt += 'non sostituirlo automaticamente con una strada tranquilla. Non inventare attribuzioni archivistiche o geografiche.'
            reply = query(prompt,director_schema(len(batch)),f'Piano visuale · blocco {index+1}/{len(director_batches)}')
            if len(reply.get('beats',[])) != len(batch):
                raise ValueError('Director MAGICO non ha coperto tutte le frasi')
            for raw,chunk in zip(reply['beats'],batch):
                if raw['chunk_id'] != chunk['id']:
                    raise ValueError('Ordine delle frasi Director diverso dalla trascrizione')
                expected_places = beat_places(chunk['text'],context,prior_context[chunk['id']])
                raw = deepcopy(raw)
                for shot in raw['shots']:
                    for field in ('image_queries','video_queries'):
                        queries = [q for q in shot[field] if not conflicting_place(q,expected_places)]
                        if not queries:
                            raise ValueError('Query fuori contesto geografico: correzione necessaria')
                        shot[field] = anchor_queries(queries,expected_places)
                decisions[chunk['id']] = raw
            report(len(director_batches)+index+1,2*len(director_batches),'Piano visuale contestuale verificato')
        plan = compile_director_decisions(package,{'global_topic':topic or context,'beats':[decisions[c['id']] for c in package['chunks']]})
        if fingerprint(transcript_package(run,project_id,duration)['chunks']) != package_signature:
            raise ValueError('Le selezioni sono cambiate durante il piano: pubblicazione sospesa')
        editorial_root = import_plan(run,plan,package)
        return {'editorial_root':str(editorial_root),'beat_count':len(plan['visual_beats']),
                'coverage_count':sum(b['action']=='BROLL' for b in plan['visual_beats']),
                'global_topic':plan['global_topic'],'plan_signature':fingerprint(plan)}
