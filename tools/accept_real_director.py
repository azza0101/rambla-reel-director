"""Run real offline Director acceptance; fixtures are never production routing."""
import argparse
import json
import os
from pathlib import Path
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kura-chunks', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--model-root', type=Path, default=Path('Z:/APP REEL TEST/qwen-embedding-smoke/models'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.path.insert(0, os.environ.get('RAMBLA_DIRECTOR_DEPS', str(args.model_root.parent / 'director-deps')))
    from backend.app.qwen_stack import LocalQwenDirectorGenerator, QwenConfig, offline_model_environment
    from backend.app.visual_planner import load_or_create_visual_plan
    from backend.app.atomic_io import write_json

    with offline_model_environment(args.model_root):
        generator = LocalQwenDirectorGenerator(QwenConfig(args.model_root))
        started = time.perf_counter()
        generator.load()
        load_seconds = time.perf_counter() - started
        print(json.dumps({'model_load_seconds': load_seconds}), flush=True)
        for domain in ('cybersecurity', 'cooking', 'personal_finance', 'kura'):
            source = args.kura_chunks if domain == 'kura' else root / 'tests/fixtures/visual_planner' / (domain + '.json')
            chunks = json.loads(source.read_text(encoding='utf-8'))
            folder = args.output_dir / domain
            folder.mkdir(parents=True, exist_ok=True)
            calls = []

            def generate(prompt):
                begin = time.perf_counter()
                raw = generator(prompt)
                calls.append({'seconds': time.perf_counter() - begin, 'characters': len(raw)})
                (folder / f'raw-{len(calls)}.json').write_text(raw, encoding='utf-8')
                return raw

            begin = time.perf_counter()
            plan = load_or_create_visual_plan(chunks, {}, folder, generate=generate)
            report = {'domain': domain, 'load_seconds': load_seconds, 'planning_seconds': time.perf_counter() - begin,
                      'chunks': len(chunks), 'calls': calls, 'real_generation_this_run': bool(calls)}
            write_json(folder / 'timings.json', report)
            print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
