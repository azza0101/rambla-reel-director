"""Read-only media audit of an existing imported-plan retrieval run. No ASR/search."""
import argparse
import html
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.video_preview import probe_preview


def audit(root):
    videos = json.loads((root / 'online-candidates.json').read_text(encoding='utf-8'))
    images = json.loads((root / 'image-candidates.json').read_text(encoding='utf-8'))
    clips = [r for beat in videos for r in beat.get('candidates', [])]
    verification = []
    for row in clips:
        facts = probe_preview(row.get('preview_path'))
        start, end = row.get('source_start_seconds'), row.get('source_end_seconds')
        valid = facts['playable'] and start is not None and end is not None and 2.5 <= end-start <= 4.05
        verification.append({'id': row['id'], 'valid': valid, 'probe': facts})
    return {'videos': videos, 'images': images, 'playback_checks': verification,
            'all_clips_playable': all(r['valid'] for r in verification),
            'semantic_acceptance': 'Requires human inspection; scores are not probabilities.',
            'resolve_calls': 0, 'asr_runs': 0}


def render(report):
    esc = html.escape
    sections = []
    for beat in report['videos']:
        cards = []
        for row in beat.get('candidates', []):
            path = Path(row['preview_path']).resolve().as_uri()
            cards.append(f'<article><video controls muted preload="metadata" src="{esc(path)}"></video>'
                         f'<h3>{esc(row.get("title",row["id"]))}</h3>'
                         f'<details><summary>Provider / query / score / source range</summary>'
                         f'<pre>{esc(json.dumps(row,ensure_ascii=False,indent=2))}</pre></details></article>')
        sections.append(f'<section><h2>{esc(beat["beat_id"])}</h2><div class="cards">'+''.join(cards)+
                        '</div><details><summary>All retrieval diagnostics</summary><pre>'+
                        esc(json.dumps(beat,ensure_ascii=False,indent=2))+'</pre></details></section>')
    for bid, beat in report['images'].get('chunks', {}).items():
        cards = []
        for row in beat.get('candidates', []):
            path = Path(row['preview_path']).resolve().as_uri()
            cards.append(f'<article><img src="{esc(path)}"><details><summary>Image details</summary>'
                         f'<pre>{esc(json.dumps(row,ensure_ascii=False,indent=2))}</pre></details></article>')
        sections.append(f'<section><h2>{esc(bid)} — images</h2><div class="cards">'+''.join(cards)+'</div></section>')
    return '<!doctype html><meta charset="utf-8"><title>Imported retrieval review</title><style>body{background:#121819;color:#eee;font:16px system-ui;margin:24px}.cards{display:flex;flex-wrap:wrap;gap:16px}article{width:360px}video,img{width:100%;height:240px;object-fit:contain}pre{white-space:pre-wrap;overflow-wrap:anywhere}section{border-top:1px solid #567;margin-top:24px}</style><h1>Actual imported-plan retrieval</h1><p>Local previews and complete diagnostics. Semantic quality remains subject to review.</p>'+''.join(sections)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retrieval-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.retrieval_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    args.output.with_suffix('.html').write_text(render(report),encoding='utf-8')
    print(json.dumps({'clips':len(report['playback_checks']),'all_clips_playable':report['all_clips_playable']}))
