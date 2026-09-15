"""Bounded real-model quality gate. Never imports/calls a provider or ASR stage."""
import argparse
import json
import os
from pathlib import Path
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--chunks', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--scope-first', type=int, default=8, choices=range(1, 9))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    model_root = Path('Z:/APP REEL TEST/qwen-embedding-smoke/models')
    sys.path.insert(0, str(model_root.parent/'director-deps'))
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    from backend.app.qwen_stack import LocalQwenDirectorGenerator, QwenConfig, offline_model_environment
    from backend.app.visual_planner import load_or_create_visual_plan
    from backend.app.atomic_io import write_json
    chunks = json.loads(args.chunks.read_text(encoding='utf-8'))[:args.scope_first]
    scope = [c['id'] for c in chunks[:args.scope_first]]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with offline_model_environment(model_root):
        generator = LocalQwenDirectorGenerator(QwenConfig(model_root))
        print('MODEL_LOAD_START', flush=True)
        start = time.perf_counter(); generator.load(); load_seconds = time.perf_counter()-start
        print('MODEL_LOAD_SECONDS', load_seconds, flush=True)
        native = generator.model.generate
        class Progress:
            def __init__(self): self.count = 0
            def put(self, tokens):
                self.count += 1
                if self.count % 200 == 0: print('GENERATED_TOKEN_STEPS', self.count, flush=True)
            def end(self): print('GENERATION_END', self.count, flush=True)
        def monitored(**kwargs):
            return native(**kwargs, streamer=Progress())
        generator.model.generate = monitored
        try:
            plan = load_or_create_visual_plan(chunks, {}, args.output_dir, generate=generator, scope_chunk_ids=scope,
                                             event_callback=lambda s,p,m,**d: print(m, json.dumps(d), flush=True))
            assert plan['scope_chunk_ids'] == scope and set(plan['chunks']) == set(scope)
            error = None
        except Exception as exc:
            artifact = args.output_dir/'visual-plan.json'
            plan = json.loads(artifact.read_text(encoding='utf-8')) if artifact.exists() else {}
            error = f'{type(exc).__name__}: {exc}'
        report = {'status': 'AWAITING_USER_QUALITY_REVIEW' if error is None else 'QUALITY_GATE_REJECTED',
                  'scope_chunk_ids': scope, 'source_chunks': chunks[:args.scope_first], 'model_load_seconds': load_seconds,
                  'providers_called': 0, 'asr_calls': 0, 'error': error, 'plan': plan}
        calls = plan.get('calls', [])
        report['generation_seconds'] = round(sum(c['seconds'] for c in calls), 4)
        report['input_tokens'] = sum(c.get('metrics', {}).get('input_tokens', 0) for c in calls)
        report['output_tokens'] = sum(c.get('metrics', {}).get('output_tokens', 0) for c in calls)
        report['model_calls'] = len(calls)
        write_json(root/'real-director-beat-review.json', report)
        summary = {k:v for k,v in report.items() if k not in {'plan','source_chunks'}}
        readable = '# Real visual-beat quality gate\n\n```json\n'+json.dumps(summary,ensure_ascii=False,indent=2)+'\n```\n'
        readable += '\n## Original scoped speech\n\n```json\n'+json.dumps([{'id':c['id'],'text':c['text']} for c in chunks[:args.scope_first]],ensure_ascii=False,indent=2)+'\n```\n'
        readable += '\n## Final visual beats\n\n```json\n'+json.dumps(plan.get('visual_beats',[]),ensure_ascii=False,indent=2)+'\n```\n'
        readable += '\n## Chunk actions\n\n```json\n'+json.dumps(plan.get('chunks',{}),ensure_ascii=False,indent=2)+'\n```\n'
        for i, call in enumerate(calls,1):
            readable += f'\n## Actual Qwen response {i}: {call["stage"]}\n\n```json\n{call["raw_response"]}\n```\n'
        (root/'real-director-beat-review.md').write_text(readable,encoding='utf-8')
        print(json.dumps(summary),flush=True)


if __name__ == '__main__': main()
