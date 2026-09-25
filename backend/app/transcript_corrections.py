"""Manual transcript corrections, preserving timing and existing curation assets."""
from copy import deepcopy
import re
from .atomic_io import write_json
from .editorial_import import read, digest, normalized_chunks, transcript_package, active_retrieval_root, validate_import


def needs_editorial_refresh(run):
    marker=run/'transcript-corrections.json'
    if not marker.is_file() or not (run/'visual-plan.json').is_file(): return False
    return read(marker).get('stale_plan_digest')==digest(read(run/'visual-plan.json'))


def require_current_editorial(run):
    if needs_editorial_refresh(run):
        raise ValueError('Trascrizione corretta: rigenera o importa il piano editoriale prima di nuove ricerche.')


def correct_phrase(run, beat_id, changes, expected_text):
    plan=read(run/'visual-plan.json');old_root=active_retrieval_root(run)
    beat=next((b for b in plan['visual_beats'] if b['id']==beat_id),None)
    if beat is None: raise ValueError('Frase non trovata')
    if beat['original_text']!=expected_text: raise ValueError('La frase è cambiata: ricarica prima di salvare')
    if set(changes)!=set(beat['covered_chunk_ids']): raise ValueError('Invia tutti e solo i segmenti della frase')
    clean={k:' '.join(str(v).split()) for k,v in changes.items()}
    if any(not v or len(v)>10000 for v in clean.values()): raise ValueError('Il testo deve contenere da 1 a 10000 caratteri')
    rows=read(run/'semantic-chunks.json');new_rows=deepcopy(rows)
    changed=[r['id'] for r in rows if r['id'] in clean and r['text']!=clean[r['id']]]
    if not changed:return {'changed':False}
    for row in new_rows:
        if row['id'] in changed:
            row['text']=clean[row['id']]
            row.pop('words',None) # Original ASR word alignment is not valid for edited words.
    marker_path=run/'transcript-corrections.json'
    marker=read(marker_path) if marker_path.exists() else {'original_chunks':rows,'history':[]}
    marker['history'].append({'beat_id':beat_id,'before':expected_text,'chunks':clean})
    # All writes are atomic individually, with rollback on any synchronous failure.
    paths=[run/'semantic-chunks.json',run/'visual-plan.json',marker_path,run/'editorial-location.json',old_root/'imported-plan.json']
    snapshot={p:p.read_bytes() if p.exists() else None for p in paths}
    try:
        write_json(run/'semantic-chunks.json',new_rows)
        package=transcript_package(run,plan['project_id'],max(c['end'] for c in normalized_chunks(run)))
        corrected={c['id']:c['text'] for c in package['chunks']}
        for b in plan['visual_beats']: b['original_text']=' '.join(corrected[c] for c in b['covered_chunk_ids'])
        plan['transcript_signature']=package['transcript_signature']
        validate_import(plan,package)
        plan_hash=digest(plan)
        if old_root.parent != run/'editorial' or not re.fullmatch('[a-f0-9]{64}',old_root.name):raise ValueError('Invalid retrieval root')
        write_json(run/'editorial-location.json',{'plan_digest':plan_hash,'directory':old_root.name})
        write_json(run/'visual-plan.json',plan)
        write_json(old_root/'imported-plan.json',plan)
        marker['stale_plan_digest']=plan_hash
        write_json(marker_path,marker)
    except Exception:
        for path,content in snapshot.items():
            if content is None:path.unlink(missing_ok=True)
            else:path.write_bytes(content)
        raise
    return {'changed':True,'editorial_refresh_required':True}
