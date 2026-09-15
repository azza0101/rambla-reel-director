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
    parser.add_argument("--model", default="Qwen3.5-4B")
    args = parser.parse_args()
    # Dependency overlay is opt-in, never discovered or installed implicitly.
    deps = os.environ.get("RAMBLA_DIRECTOR_DEPS")
    if deps and Path(deps).is_dir():
        sys.path.insert(0, deps)
    from .qwen_stack import LocalQwenDirectorGenerator, QwenConfig, offline_model_environment
    from .visual_planner import load_or_create_visual_plan
    from .debug_run_cli import _event
    with offline_model_environment(args.model_root):
        generator = LocalQwenDirectorGenerator(QwenConfig(args.model_root, director_model=args.model))
        load_or_create_visual_plan(json.loads(args.chunks.read_text(encoding="utf-8")), json.loads(args.outline.read_text(encoding="utf-8")), args.output_dir, generate=generator, model_name=args.model, event_callback=_event)


if __name__ == "__main__":
    main()
