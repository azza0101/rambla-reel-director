"""Runtime-mode decisions shared by the desktop and hosted products."""
from __future__ import annotations

import os


def current_mode() -> str:
    return os.environ.get("RAMBLA_RUNTIME_MODE", "local").casefold().strip() or "local"


def uses_api_runtime() -> bool:
    return current_mode() in {"cloud", "desktop_api"}


def is_hosted_cloud() -> bool:
    return current_mode() == "cloud"
