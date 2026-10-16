"""Durable bounded searches through the product's existing research callback."""
import json
from pathlib import Path
from .atomic_io import write_json
from .magic_coverage import research_queries
from .magic_store import fingerprint
from .magic_usage import check_current
from .magic_services import MagicBudgetReached, MagicWaitingInput


async def research_beats(beats, options, directory, research, report):
    path = Path(directory) / 'research-journal.json'
    journal = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    priority = {'pexels': 0, 'envato': 1, 'youtube_shorts': 2, 'youtube': 3, 'tiktok': 4, 'instagram': 5, 'google_images': 6}
    jobs = [(beat, provider, query) for beat in beats
        for provider in sorted(options.providers, key=lambda p: priority[p])
        for query in research_queries(beat.get('image_queries' if provider == 'google_images' else 'queries', beat.get('queries', [])),
                                      beat.get('places', []), limit=options.queries_per_provider)]
    warnings, blocked = [], set()
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
