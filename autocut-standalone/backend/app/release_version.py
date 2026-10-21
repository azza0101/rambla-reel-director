"""Single source of truth for the user-visible RAMBLA release number."""
from pathlib import Path


_VERSION_FILE = Path(__file__).resolve().parents[2] / "RAMBLA_VERSION"
RELEASE_VERSION = _VERSION_FILE.read_text(encoding="utf-8").strip()

if len(RELEASE_VERSION) != 5 or not RELEASE_VERSION.startswith("v") or not RELEASE_VERSION[1:].isdigit():
    raise RuntimeError("RAMBLA_VERSION must use the v0000 format")
