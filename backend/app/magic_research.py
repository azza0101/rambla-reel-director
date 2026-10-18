"""Durable bounded searches through the product's existing research callback."""
import json
from pathlib import Path
from .atomic_io import write_json
from .magic_coverage import research_queries
from .magic_store import fingerprint
from .magic_usage import check_current
from .magic_services import MagicBudgetReached, MagicWaitingInput

# MAGICO must return an editable first cut in minutes. Searching every provider
# twice for every editorial beat turns a reel into hundreds of serial requests.
AUTOMATIC_RESEARCH_JOB_BUDGET = 48


def _visual_priority(beat):
    """Prefer concrete, place-aware shots while retaining chronological spread."""
    text = ' '.join([
        str(beat.get('text', '')),
        str(beat.get('editorial_function', '')),
        ' '.join(beat.get('queries', [])),
    ]).lower()
    concrete = ('passport', 'camera', 'school', 'market', 'beach', 'street',
                'train', 'airport', 'hotel', 'map', 'food', 'child', 'family',
                'phone', 'photo', 'luggage')
    return (4 if beat.get('places') else 0) + sum(term in text for term in concrete)


def _automatic_beats(beats, limit):
    """Return a deterministic, timeline-wide set of beats within the job budget."""
    if len(beats) <= limit:
        return list(beats)
    anchors = {round(index * (len(beats) - 1) / (limit - 1)) for index in range(limit)}
    selected = set(anchors)
    ranked = sorted(range(len(beats)), key=lambda i: (-_visual_priority(beats[i]), i))
    for index in ranked:
        if index in selected:
            continue
        weakest = min(selected, key=lambda i: (_visual_priority(beats[i]), -i))
        if _visual_priority(beats[index]) <= _visual_priority(beats[weakest]):
            break
        selected.remove(weakest)
        selected.add(index)
    return [beats[index] for index in sorted(selected)]


async def research_beats(beats, options, directory, research, report):
    path = Path(directory) / 'research-journal.json'
    journal = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    priority = {'pexels': 0, 'envato': 1, 'youtube_shorts': 2, 'youtube': 3, 'tiktok': 4, 'instagram': 5, 'google_images': 6}
    providers = sorted(options.providers, key=lambda p: priority[p])
    # One query per provider is enough for the automatic first pass. Its role is
    # to create a usable edit quickly; manual per-beat search retains full depth.
    full_job_count = len(beats) * len(providers) * options.queries_per_provider
    query_limit = options.queries_per_provider if full_job_count <= AUTOMATIC_RESEARCH_JOB_BUDGET else 1
    beat_limit = max(1, AUTOMATIC_RESEARCH_JOB_BUDGET // max(1, len(providers) * query_limit))
    selected_beats = _automatic_beats(beats, beat_limit)
    jobs = [(beat, provider, query) for beat in selected_beats
        for provider in providers
        for query in research_queries(beat.get('image_queries' if provider == 'google_images' else 'queries', beat.get('queries', [])),
                                      beat.get('places', []), limit=query_limit)]
    warnings, blocked = [], set()
    if len(selected_beats) < len(beats):
        warnings.append(
            f'MAGICO rapido: ricercate {len(selected_beats)}/{len(beats)} coperture prioritarie; '
            'le altre restano disponibili per la ricerca manuale.')
    for index, (beat, provider, query) in enumerate(jobs):
        check_current()
        key = fingerprint([beat['id'], provider, query])
        if (beat['id'], provider) in blocked:
            report(index+1, len(jobs), f'{provider}: richiesta verifica manuale')
            continue
        old = journal.get(key)
        if old and old['status'] in {'started', 'failed'}:
            warnings.append(old.get('error') or f'{provider}: ricerca interrotta; nessun nuovo tentativo automatico')
            blocked.add((beat['id'], provider))
            report(index+1, len(jobs), f'{provider}: controlla la fonte')
            continue
        if not old:
            journal[key] = dict(status='started', beat_id=beat['id'], provider=provider, query=query)
            write_json(path, journal)
            report(index, len(jobs), f'Cerco {provider} · {query}')
            try:
                result = await research(beat['id'], provider, query)
                check_current()
                if result.get('errors'):
                    raise RuntimeError(str(result['errors']))
                journal[key].update(status='completed', result=result)
            except (MagicBudgetReached, MagicWaitingInput):
                raise
            except Exception as exc:
                message = f"{beat['id']} · {provider}: {getattr(exc, 'detail', exc)}"
                journal[key].update(status='failed', error=message)
                warnings.append(message)
                blocked.add((beat['id'], provider))
            write_json(path, journal)
        report(index+1, len(jobs), f'Fonti cercate: {index+1}/{len(jobs)}')
    return dict(searched=len(jobs), warnings=warnings, partial=bool(warnings))
