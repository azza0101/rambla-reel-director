"""Stage-specific dependencies; releases Director GPU memory before ranking."""
import argparse
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    for name in ("chunks", "outline", "output-dir", "model-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--editorial-input", type=Path, help="Export completed experimental output as the neutral contract; import separately")
    parser.add_argument("--model", default="Qwen3.5-4B")
    parser.add_argument("--scope-first", type=int)
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()
    # User-approved project-local overlay, isolated to this Director subprocess.
    deps = os.environ.get("RAMBLA_DIRECTOR_DEPS", str(args.model_root.parent / "director-deps"))
    if deps and Path(deps).is_dir():
        sys.path.insert(0, deps)
    from .qwen_stack import LocalQwenDirectorGenerator, QwenConfig, offline_model_environment
    from .visual_planner import load_or_create_visual_plan
    from .debug_run_cli import _event
    with offline_model_environment(args.model_root):
        generator = LocalQwenDirectorGenerator(QwenConfig(args.model_root, director_model=args.model))
        chunks = json.loads(args.chunks.read_text(encoding="utf-8"))
        scope = [c["id"] for c in chunks[:args.scope_first]] if args.scope_first else None
        plan = load_or_create_visual_plan(chunks, json.loads(args.outline.read_text(encoding="utf-8")), args.output_dir, generate=generator, model_name=args.model, event_callback=_event, scope_chunk_ids=scope, batch_size=args.batch_size)
        from .atomic_io import write_json
        if args.editorial_input:
            from .editorial_import import export_local_producer
            package = json.loads(args.editorial_input.read_text(encoding='utf-8'))
            write_json(args.output_dir / 'external-visual-plan.json', export_local_producer(plan, package))
        write_json(args.output_dir / "director-timings.json", {"model_load_seconds": getattr(generator, "load_seconds", 0), "planning_seconds": plan["planning_seconds"], "model_calls": plan["model_call_count"], "calls": [{k:v for k,v in call.items() if k not in {"prompt","raw_response"}} for call in plan["calls"]]})


if __name__ == "__main__":
    main()
