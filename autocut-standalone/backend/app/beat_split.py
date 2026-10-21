"""Split reviewed coverage at a timed word boundary, preserving other curation."""
from copy import deepcopy
from uuid import uuid4
from .atomic_io import write_json
from .editorial_import import read, digest, active_retrieval_root, transcript_package, validate_import
from .transcript_intents import planning_chunks_for_coverage, load_phrase_intents


def split_preview(run, beat_id):
    plan = read(run / 'visual-plan.json')
    beat = next((b for b in plan['visual_beats'] if b['id'] == beat_id), None)
    if not beat or beat['action'] != 'BROLL':
        raise ValueError('Seleziona una scena B-roll')
    chunks = planning_chunks_for_coverage(run)
    covered = [c for c in chunks if c['id'] in beat['covered_chunk_ids']]
    words = [w for c in covered for w in c.get('words', [])]
    if len(words) < 2 or ' '.join(w['text'].strip() for w in words) != ' '.join(beat['original_text'].split()):
        raise ValueError('La frase non ha tempi parola verificabili: impossibile dividerla senza perdere precisione')
    return {'text': beat['original_text'], 'words': words, 'revision': digest(plan)}


def split_beat(run, beat_id, cut, revision):
    preview = split_preview(run, beat_id)
    if revision != preview['revision']:
        raise ValueError('Il piano è cambiato. Riapri Dividi frase')
    if not 0 < cut < len(preview['words']):
        raise ValueError('Scegli un punto interno alla frase')
    plan = read(run / 'visual-plan.json')
    old_root = active_retrieval_root(run)
    if old_root.parent != run / 'editorial':
        raise ValueError('Il piano deve essere valido prima della divisione')
    chunks = planning_chunks_for_coverage(run)
    beat = next(b for b in plan['visual_beats'] if b['id'] == beat_id)
    suffix = uuid4().hex[:8]
    left_ids, right_ids, replacement = [], [], []
    seen = 0
    for row in chunks:
        if row['id'] not in beat['covered_chunk_ids']:
            replacement.append(row)
            continue
        size = len(row['words'])
        local_cut = max(0, min(size, cut - seen))
        for is_left, start, end in [(True, 0, local_cut), (False, local_cut, size)]:
            if start == end:
                continue
            part = deepcopy(row)
            words = row['words'][start:end]
            part.update(id=row['id'] + ('_a_' if is_left else '_b_') + suffix,
                        words=words, text=' '.join(w['text'].strip() for w in words),
                        start=words[0]['start'], end=words[-1]['end'], coverage_selected=True,
                        source_word_start_index=row.get('source_word_start_index', 0) + start,
                        source_word_end_index=row.get('source_word_start_index', 0) + end - 1)
            replacement.append(part)
            (left_ids if is_left else right_ids).append(part['id'])
        seen += size
    # Reviewed coverage uses one planning chunk per beat; refuse ambiguous legacy grouping.
    if len(left_ids) != 1 or len(right_ids) != 1:
        raise ValueError('Questa scena comprende più segmenti: rigenera il piano prima di dividerla')
    first, second = deepcopy(beat), deepcopy(beat)
    second['id'] = beat_id + '_split_' + suffix
    for item, ids in [(first, left_ids), (second, right_ids)]:
        rows = [c for c in replacement if c['id'] in ids]
        item.update(covered_chunk_ids=ids, start=rows[0]['start'], end=rows[-1]['end'],
                    original_text=' '.join(c['text'] for c in rows))
    for shot in second['shots']:
        shot['shot_id'] += '_split_' + suffix
    index = plan['visual_beats'].index(beat)
    plan['visual_beats'][index:index+1] = [first, second]
    intents = load_phrase_intents(run)
    snapshot = {'transcript_signature': intents['transcript_signature'],
                'selection_digest': digest(intents['phrases']), 'chunks': replacement}
    paths = [run/'coverage-timing-snapshot.json', run/'visual-plan.json',
             run/'editorial-location.json', old_root/'imported-plan.json']
    before = {p: p.read_bytes() if p.exists() else None for p in paths}
    backup = run/'split-backups'/suffix
    backup.mkdir(parents=True)
    for p, data in before.items():
        if data is not None:
            (backup/p.name).write_bytes(data)
    try:
        write_json(paths[0], snapshot)
        package = transcript_package(run, plan['project_id'], max(c['end'] for c in replacement))
        validate_import(plan, package)
        write_json(paths[2], {'plan_digest': digest(plan), 'directory': old_root.name})
        write_json(paths[1], plan)
        write_json(paths[3], plan)
    except Exception:
        for p, data in before.items():
            if data is None: p.unlink(missing_ok=True)
            else: p.write_bytes(data)
        raise
    return {'beat_ids': [first['id'], second['id']], 'backup': str(backup)}
