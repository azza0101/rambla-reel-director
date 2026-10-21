"""Pull-only Issue #2 watcher when Codex CLI cannot run in this Windows sandbox.

This process never invokes a model or mutates Resolve. It records actionable
comments and requests a user decision once per comment, rather than silently
pretending that background Codex execution is available.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ISSUE = "repos/azza0101/rambla-reel-director/issues/2/comments"
BRANCH = "feat/foundation-safe-resolve-slice"
CLI_ERROR = (
    "codex-cli 0.153.4 exec --ephemeral --skip-git-repo-check --sandbox read-only "
    "fails before model startup: state_5.sqlite is readonly; "
    "in-process app-server client: Accesso negato (os error 5). "
    "The same failure persisted after scoped .codex write permission."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def gh_json(*args: str) -> object:
    result = subprocess.run(
        ["gh", "api", *args], capture_output=True, text=True, check=True, timeout=30
    )
    return json.loads(result.stdout)


def load_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {
            "last_processed_comment_id": 0,
            "current_stage": "ORCHESTRATION_FIX",
            "last_codex_exit": "NOT_RUN_CLI_UNAVAILABLE",
            "retry_count": 0,
        }
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def actionable(comment: dict[str, object]) -> bool:
    body = str(comment.get("body", "")).lstrip()
    if body.startswith("HANDOFF"):
        return False
    if body.startswith("REVIEW"):
        return "verdict: APPROVED" in body or "verdict: FIX" in body
    return bool(body.strip())


def poll_once(state_path: Path, heartbeat_path: Path) -> dict[str, object]:
    state = load_state(state_path)
    comments = gh_json("--paginate", ISSUE)
    if not isinstance(comments, list):
        raise RuntimeError("Issue #2 comments response is not a list")
    new = [
        comment for comment in comments
        if isinstance(comment, dict)
        and int(comment["id"]) > int(state["last_processed_comment_id"])
    ]
    pending = [comment for comment in new if actionable(comment)]
    if new:
        state["last_processed_comment_id"] = max(int(comment["id"]) for comment in new)
    state["current_stage"] = "USER_DECISION_CLI_UNAVAILABLE" if pending else state["current_stage"]
    state["last_codex_exit"] = "NOT_RUN_CLI_UNAVAILABLE"
    state["retry_count"] = 0
    state["last_poll_at"] = utc_now()
    if pending:
        state["pending_comment_id"] = int(pending[-1]["id"])
        state["pending_comment_excerpt"] = str(pending[-1].get("body", ""))[:300]
    save_json(state_path, state)
    heartbeat = {
        "status": "WATCHER_GREEN_EXECUTOR_BLOCKED",
        "at": state["last_poll_at"],
        "last_processed_comment_id": state["last_processed_comment_id"],
        "pending_comment_id": state.get("pending_comment_id"),
        "cli_error": CLI_ERROR,
    }
    save_json(heartbeat_path, heartbeat)
    return heartbeat


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--heartbeat", type=Path, required=True)
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.interval < 30:
        parser.error("poll interval must be at least 30 seconds")
    while True:
        try:
            print(json.dumps(poll_once(args.state, args.heartbeat), ensure_ascii=False), flush=True)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            save_json(args.heartbeat, {"status": "WATCHER_ERROR", "at": utc_now(), "error": str(exc)})
            if args.once:
                raise
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
