"""Automatic word selections and bounded batches of the existing Director."""
from copy import deepcopy
from pathlib import Path
import json

from .api_first_director import director_schema, build_director_prompt, compile_director_decisions
from .editorial_import import normalized_chunks, transcript_package, import_plan
from .transcript_intents import load_phrase_intents, save_phrase_intents
from .geographic_context import places_in, beat_places, anchor_queries, conflicting_place
from .magic_store import fingerprint


# These phrases only connect two ideas.  Treating them as B-roll produces
# calendars, generic phones or other filler that makes the cut less precise.
_TRANSITION_ONLY_COVERAGE = (
    ('poi', 'un', 'giorno'),
    ('e', 'quindi'),
    ('ma', 'in', 'che', 'senso'),
    ('e', 'poi'),
    ('a', 'questo', 'punto'),
)


def _remove_transition_coverage(words, selected):
    """Keep AI coverage on what is shown, never on connective filler."""
    clean = [str(word).casefold().strip('.,;:!?…') for word in words]
    chosen = set(selected)
    for phrase in _TRANSITION_ONLY_COVERAGE:
        width = len(phrase)
        for start in range(len(clean)-width+1):
            indexes = set(range(start, start+width))
            if tuple(clean[start:start+width]) == phrase and indexes.issubset(chosen):
                chosen.difference_update(indexes)
    return sorted(chosen)


def _valid_window_indices(values, allowed):
    """Keep a usable provider response when it cites a neighbouring window.

    The model sees global word numbers and can occasionally include the first
    word from the adjacent 80-word window.  That must not discard the whole
    editorial pass: use the indices which unambiguously belong to this window
    and expose the dropped count in the run warnings.
    """
    if not isinstance(values, list):
        raise ValueError('Selezione AI non valida: atteso un elenco di parole')
    allowed = set(allowed)
    valid = [index for index in values if type(index) is int and index in allowed]
    return sorted(set(valid)), len(values) - len(valid)


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
        words = [str(word.get('text') or word.get('word') or '') if isinstance(word, dict) else str(word)
                 for word in (chunk.get('words') or str(chunk['text']).split())]
        result['coverage_word_indices'] = _remove_transition_coverage(words, result['coverage_word_indices'])
        length = 0
        previous = -2
        for index in result['highlighted_word_indices']:
            length = length+1 if index == previous+1 else 1
            if length > 3:
                raise ValueError('Parole evidenziate: massimo tre parole consecutive')
            previous = index
        output[str(chunk['id'])] = result
    from .highlight_phrases import expanded_highlight_indices
    completed = expanded_highlight_indices(chunks,output)
    for cid,indices in completed.items():output[cid]['highlighted_word_indices']=indices
    return output


def _selection_schema():
    indices = {'type':'array','items':{'type':'integer','minimum':0}}
    row = {'type':'object','additionalProperties':False,
           'properties':{'unit_id':{'type':'string'},
               'coverage_word_indices':{**indices,'description':'Exact numbered words of complete passages to cover with B-roll, including all words between the selected IN and OUT.'},
               'highlighted_word_indices':{**indices,'description':'Exact numbered words of important concepts to emphasize as titles. Reflective and abstract concepts are valid. Usually 1-3 words per concept.'}},
           'required':['unit_id','coverage_word_indices','highlighted_word_indices']}
    return {'type':'object','additionalProperties':False,'properties':{
        'global_topic':{'type':'string'},'choices':{'type':'array','items':row}},'required':['global_topic','choices']}


def compact_director_batches(chunks):
    from .cut_cloud import pack_items
    compact = [{key: chunk[key] for key in ('id','start','end','text')} for chunk in chunks]
    # The director also sees a compact global context.  These conservative
    # bounds stay under the provider's complete-request token ceiling.
    return pack_items(compact, max_chars=2000, max_items=6)


def _magic_director_schema(count):
    schema = deepcopy(director_schema(count))
    # Groq can expand a list despite an exact item limit, then reject its own
    # otherwise usable JSON before we can retain the requested rows.
    beats = schema['properties']['beats']
    beats.pop('minItems', None)
    beats.pop('maxItems', None)
    beats['description'] = f'Exactly {count} decisions for, and only for, the supplied transcript chunk IDs.'
    properties = schema['properties']['beats']['items']['properties']
    # Providers sometimes append a KEEP_TALKING_HEAD duplicate after a valid
    # B-roll row.  Accept that harmless spillover so we can retain the B-roll
    # decision below instead of losing the complete batch at schema validation.
    properties['action']['enum'] = ['BROLL', 'KEEP_TALKING_HEAD']
    # The final compacting step always publishes one scene.  Accept the other
    # base-schema modes first so an irrelevant duplicate cannot make Groq
    # reject the entire JSON response before it reaches our parser.
    properties['visual_mode']['enum'] = ['single', 'sequence', 'juxtaposition']
    return schema


def _requested_director_rows(reply, batch):
    """Return one decision per requested chunk, ignoring provider spillover."""
    rows = reply.get('beats')
    if not isinstance(rows, list):
        raise ValueError('Director MAGICO non ha restituito le decisioni')
    expected = {str(chunk['id']) for chunk in batch}
    selected, extras = {}, 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Director MAGICO ha restituito una decisione non valida')
        chunk_id = str(row.get('chunk_id') or '')
        if chunk_id not in expected:
            extras += 1
            continue
        previous = selected.get(chunk_id)
        if previous is not None:
            # A valid B-roll decision is more useful than the redundant
            # talking-head fallback emitted by a few providers.  Any other
            # duplicate remains ambiguous and therefore fails safely.
            actions = {str(previous.get('action') or ''), str(row.get('action') or '')}
            if actions == {'BROLL', 'KEEP_TALKING_HEAD'}:
                selected[chunk_id] = previous if previous.get('action') == 'BROLL' else row
                extras += 1
                continue
            raise ValueError('Director MAGICO ha duplicato una frase richiesta')
        selected[chunk_id] = row
    missing = expected-set(selected)
    if missing:
        raise ValueError('Director MAGICO non ha coperto tutte le frasi richieste')
    return [selected[str(chunk['id'])] for chunk in batch], extras


def _compact_magic_decision(raw):
    """Make a permissive provider reply fit MAGICO's one-scene budget."""
    decision = deepcopy(raw)
    shots = decision.get('shots')
    if not isinstance(shots, list) or not shots:
        raise ValueError('Director MAGICO non ha proposto una scena per la frase richiesta')
    dropped = max(0, len(shots)-1)
    decision['shots'] = shots[:1]
    decision['visual_mode'] = 'single'
    for field in ('image_queries','video_queries'):
        values = decision['shots'][0].get(field)
        if not isinstance(values, list) or not values:
            raise ValueError('Director MAGICO non ha proposto query utilizzabili')
        dropped += max(0, len(values)-2)
        decision['shots'][0][field] = values[:2]
    return decision, dropped


def _geographically_safe_queries(queries, expected_places, fallback_text):
    """Preserve the beat when a provider invents a conflicting location."""
    valid = [query for query in queries if not conflicting_place(query,expected_places)]
    if valid:
        return anchor_queries(valid,expected_places), False
    words = str(fallback_text or '').split()
    # A short semantic phrase searches better than the invented place name.
    fallback = ' '.join(words[:8]) or 'travel documentary scene'
    return anchor_queries([fallback],expected_places), True


def _deduplicate_plan_queries(decisions, chunks):
    """Avoid sending the same stock-search query to two different beats."""
    # The compiler permits the same wording once for images and once for video.
    # Deduplicate only inside each provider lane.
    seen, repairs = {'image_queries': set(), 'video_queries': set()}, 0
    for chunk in chunks:
        decision = decisions[str(chunk['id'])]
        for shot in decision['shots']:
            for field in ('image_queries','video_queries'):
                used = seen[field]
                unique = []
                for query in shot[field]:
                    key = ' '.join(str(query).casefold().split())
                    if key not in used:
                        used.add(key)
                        unique.append(query)
                    else:
                        repairs += 1
                if unique:
                    shot[field] = unique
                    continue
                words = [word.strip('.,;:!?') for word in str(chunk['text']).split()]
                fallback = ' '.join(word for word in words if word)[:120]
                fallback = ' '.join(fallback.split()[:10]) or 'documentary travel scene'
                candidate = fallback
                suffix = 2
                while ' '.join(candidate.casefold().split()) in used:
                    candidate = ' '.join((fallback.split()[:8] + [f'scene{suffix}']))
                    suffix += 1
                used.add(' '.join(candidate.casefold().split()))
                shot[field] = [candidate]
    return repairs


def run_magic_editorial(run, project_id, duration, report, *, query=None):
    from .cut_cloud import cloud_context, query_json, pack_items, word_windows
    run = Path(run)
    if query is None:
        # Keep the adapter signature compatible with both the selection and
        # director passes, which may use different bounded output budgets.
        query = lambda prompt,schema,label,**kwargs: query_json(
            prompt, schema, label,
            max_output_tokens=kwargs.get('max_output_tokens', 2600),
            thinking_level=kwargs.get('thinking_level', 'low'),
        )
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
    topic, dropped_indices, extra_director_rows, compacted_director_items, geography_repairs = '', 0, 0, 0, 0
    with cloud_context(run/'magic-editorial-cache', lambda message:report(0,0,message)):
        for index, batch in enumerate(batches):
            prompt = ('Sei il montatore di un reel e devi PRODURRE le selezioni editoriali, non solo classificare il tema. '
                'Compila coverage_word_indices e highlighted_word_indices usando i numeri davanti alle parole. '
                'Evidenzia espressioni complete: nomi propri, marchi, luoghi e concetti composti sono indivisibili. '
                'Per esempio National Geographic, Steve McCurry e polizia turistica: seleziona tutte le parole del concetto, mai solo il cognome o l’aggettivo. '
                'coverage_word_indices: seleziona passaggi completi che descrivono oggetti, luoghi, persone, azioni o fatti '
                'mostrabili con video o immagini. Includi tutte le parole del passaggio, non solo il nome del soggetto. '
                'Alterna volto e coperture: in un testo adatto circa 20-45% del parlato, senza forzare una quota o inventare immagini. '
                'Non usare coperture per connettivi, ripetizioni, frasi di transizione o concetti che possono restare più chiari sul volto. '
                'Introduzione, CTA e riflessioni personali possono restare sul volto. '
                'highlighted_word_indices: scegli i concetti più importanti anche quando sono astratti o riflessivi '
                '(esempio: libertà, privilegio, responsabilità), oltre a nomi e fatti chiave. Non lasciare tutti gli highlight '
                'vuoti solo perché il testo è riflessivo. In genere 5-10 concetti al minuto, massimo tre parole consecutive '
                'per concetto e poche evidenziazioni per frase. Non evidenziare intere frasi. '
                'Esempio con parole 0:Il 1:passaporto 2:non 3:è 4:uguale 5:per 6:tutti: '
                'highlighted_word_indices può essere [1], coverage_word_indices può essere [0,1,2,3,4,5,6]. '
                'Liste vuote solo per unità che non richiedono davvero quel trattamento. Non cambiare testo o unire significati distinti. '
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
                    valid, dropped = _valid_window_indices(row[field],unit['allowed'])
                    dropped_indices += dropped
                    choices[unit['chunk_id']][field].extend(valid)
            report(index+1,len(batches)*2,'Parole chiave e passaggi da coprire identificati')
        changes = selection_changes(chunks,list(choices.values()))
        if sum(len(c['text'].split()) for c in chunks) >= 40 and not any(
                row['coverage_word_indices'] or row['highlighted_word_indices'] for row in changes.values()):
            from .magic_services import MagicWaitingInput
            raise MagicWaitingInput('L’AI non ha proposto né coperture né parole chiave: risultato incompleto. Il CUT è conservato; verifica le selezioni prima di continuare.')
        if fingerprint(normalized_chunks(run)) != input_signature:
            raise ValueError('Il testo è cambiato durante MAGICO: selezioni non sovrascritte')
        intents = load_phrase_intents(run)
        save_phrase_intents(run,changes,intents['transcript_signature'])
        package = transcript_package(run,project_id,duration)
        package_signature = fingerprint(package['chunks'])
        selected = set(package.get('coverage_selected_chunk_ids') or [])
        director_batches = compact_director_batches([c for c in package['chunks'] if c['id'] in selected])
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
            prompt += '\nPer ciascun passaggio selezionato proponi una sola inquadratura concreta, con una o due query semplici per mezzo. Mantieni concise le spiegazioni. Non inventare un paese, una città o un aeroporto specifico se il passaggio non lo nomina: in quel caso la query deve restare geografically neutral.'
            prompt += '\nRestituisci esclusivamente le decisioni per gli ID in TRANSCRIPT_CHUNKS di questo blocco: non ripetere o aggiungere frasi dal contesto completo.'
            # The Groq window includes the schema and the generated answer.
            # 2400 output tokens keep a six-chunk request below its 7.5k cap.
            reply = query(prompt,_magic_director_schema(len(batch)),
                          f'Piano visuale · blocco {index+1}/{len(director_batches)}',
                          max_output_tokens=2400)
            rows, extras = _requested_director_rows(reply,batch)
            extra_director_rows += extras
            for raw,chunk in zip(rows,batch):
                raw, dropped = _compact_magic_decision(raw)
                compacted_director_items += dropped
                expected_places = beat_places(chunk['text'],context,prior_context[chunk['id']])
                for shot in raw['shots']:
                    for field in ('image_queries','video_queries'):
                        shot[field], repaired = _geographically_safe_queries(
                            shot[field], expected_places, raw.get('core_meaning') or chunk['text'])
                        geography_repairs += int(repaired)
                decisions[chunk['id']] = raw
            report(len(director_batches)+index+1,2*len(director_batches),'Piano visuale contestuale verificato')
        duplicate_query_repairs = _deduplicate_plan_queries(decisions,package['chunks'])
        plan = compile_director_decisions(package,{'global_topic':topic or context,'beats':[decisions[c['id']] for c in package['chunks']]})
        if fingerprint(transcript_package(run,project_id,duration)['chunks']) != package_signature:
            raise ValueError('Le selezioni sono cambiate durante il piano: pubblicazione sospesa')
        editorial_root = import_plan(run,plan,package)
        warnings = []
        if dropped_indices:
            warnings.append(f'Selezione AI corretta: ignorati {dropped_indices} indici fuori dalla frase, senza modificare il testo')
        if extra_director_rows:
            warnings.append(f'Piano visuale corretto: ignorate {extra_director_rows} frasi fuori dal blocco richiesto')
        if compacted_director_items:
            warnings.append(f'Piano visuale corretto: limitate {compacted_director_items} scene o query oltre il budget MAGICO')
        if geography_repairs:
            warnings.append(f'Piano visuale corretto: riscritte {geography_repairs} query con luogo incoerente')
        if duplicate_query_repairs:
            warnings.append(f'Piano visuale corretto: rimosse {duplicate_query_repairs} query duplicate tra beat diversi')
        return {'editorial_root':str(editorial_root),'beat_count':len(plan['visual_beats']),
                'coverage_count':sum(b['action']=='BROLL' for b in plan['visual_beats']),
                'global_topic':plan['global_topic'],'plan_signature':fingerprint(plan), 'warnings':warnings}

