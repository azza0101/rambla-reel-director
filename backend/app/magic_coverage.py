"""Conservative media gates for MAGICO; metadata is never visual evidence."""
from .geographic_context import anchor_queries, conflicting_place, missing_subject
from .magic_models import CoverageDecision
import math


def research_queries(queries, places, *, limit=2):
    if not 1 <= limit <= 4:
        raise ValueError('Limite query non valido')
    clean = [' '.join(str(q).split()) for q in queries if str(q).strip()]
    return anchor_queries(list(dict.fromkeys(clean)), places)[:limit]


def shortlist_candidates(candidates, target, places, *, limit=6):
    if not 1 <= limit <= 12:
        raise ValueError('Limite candidati non valido')
    output, identities, sources = [], set(), set()
    for row in candidates:
        identity = row.get('asset_id')
        source = str(row.get('source_page') or '').strip().rstrip('/')
        metadata = ' '.join(str(row.get(k) or '') for k in ('title', 'description'))
        if not identity or identity in identities or (source and source in sources):
            continue
        if conflicting_place(metadata, places) or missing_subject(target, metadata):
            continue
        identities.add(identity)
        if source:
            sources.add(source)
        output.append(dict(row))
        if len(output) == limit:
            break
    return output


def validated_verdicts(candidates, response):
    """Require an exact reply and actual frame evidence before active selection."""
    by_id = {row['asset_id']: row for row in candidates}
    if len(by_id) != len(candidates):
        raise ValueError('Candidati duplicati')
    if response is None:
        return {key: dict(verdict='uncertain', reason='Verifica visiva non disponibile') for key in by_id}
    replies = response.get('verdicts')
    if not isinstance(replies, list):
        raise ValueError('Risposta visiva incompleta')
    result = {}
    for reply in replies:
        identity = reply.get('asset_id')
        if identity not in by_id or identity in result:
            raise ValueError('Identificativo visivo sconosciuto o duplicato')
        coherent, confidence = reply.get('coherent'), reply.get('confidence')
        reason = str(reply.get('reason') or '').strip()
        if type(coherent) is not bool or type(confidence) is not int or not 0 <= confidence <= 100 or not reason:
            raise ValueError('Giudizio visivo non valido')
        row = by_id[identity]
        evidence = len(set(row.get('sampled_frames') or [])) >= (3 if row.get('kind') == 'video' else 1)
        verdict = 'rejected' if not coherent else 'verified' if confidence >= 85 and evidence else 'uncertain'
        result[identity] = dict(verdict=verdict, reason=reason if evidence else 'Campioni visivi insufficienti: ' + reason)
    if result.keys() != by_id.keys():
        raise ValueError('Giudizi visivi mancanti')
    return result


def schedule_coverage(beat_id, candidate, verdict, *, start, end, total_frames, fps, role=None):
    """All frame intervals are half-open in the clean timeline's time base."""
    if not math.isfinite(float(fps)) or fps <= 0:
        raise ValueError('FPS non validi')
    if verdict['verdict'] != 'verified' or not candidate.get('local_available', True):
        return None
    start = max(0, int(start))
    end = min(int(end), int(total_frames))
    minimum = math.ceil(1.5 * fps)
    duration = min(end - start, round(4 * fps))
    image = candidate.get('kind') == 'image'
    source_start = max(0, int(candidate.get('source_in_frame') or 0))
    if not image:
        duration = min(duration, int(candidate.get('duration_frames') or 0) - source_start)
    if duration < minimum:
        return None
    return CoverageDecision(beat_id=beat_id, asset_id=candidate['asset_id'], provider=candidate['provider'],
        role='image_coverage' if image else (role or 'coverage'), enabled=True,
        edited_in_frame=start, edited_out_frame=start+duration, source_in_frame=source_start,
        source_out_frame=source_start+duration, verdict=verdict['verdict'], reason=verdict['reason'])


def choose_coverage(beat_id, candidates, verdicts, **interval):
    # Editorially matched clips are preferred. A verified still is real
    # coverage when video is unavailable; a topic-level generic is last.
    # Generic footage must never eclipse a matching passport/document photo.
    tiers = (
        lambda row: row.get('kind') == 'video' and row.get('role') != 'generic',
        lambda row: row.get('kind') == 'image',
        lambda row: row.get('kind') == 'video' and row.get('role') == 'generic',
    )
    for eligible in tiers:
        for row in candidates:
            if not eligible(row) or not row.get('local_available'):
                continue
            result = schedule_coverage(beat_id, row,
                verdicts.get(row['asset_id'], dict(verdict='uncertain', reason='Non verificato')), **interval,
                role=row.get('role'))
            if result is not None:
                return result
    return None
