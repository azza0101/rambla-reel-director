"""Stable DaVinci Resolve launcher for the standalone RAMBLA bridge."""
from pathlib import Path
import ctypes
import json
import os
import subprocess


def discover_app_root():
    config = Path(os.environ.get("LOCALAPPDATA", "")) / "RMBL B ROLL" / "install.json"
    if config.is_file():
        try:
            configured = Path(json.loads(config.read_text(encoding="utf-8-sig"))["app_root"])
            if (configured / "launch_local_v5.py").is_file():
                return configured
        except (OSError, KeyError, ValueError, TypeError):
            pass
    return Path(r"Z:\APP REEL TEST\qwen-embedding-smoke\api-first-v5-cloud")


APP_ROOT = discover_app_root()
PYTHONW = APP_ROOT / ".venv" / "Scripts" / "pythonw.exe"
if not PYTHONW.is_file():
    PYTHONW = APP_ROOT.parent / "editorial-intelligence-worktree" / ".venv" / "Scripts" / "pythonw.exe"
BRIDGE = APP_ROOT / "tools" / "resolve_bridge" / "standalone_bridge.py"


def show_error(message):
    try:
        ctypes.windll.user32.MessageBoxW(None, str(message), "RAMBLA · B-ROLL", 0x10)
    except Exception:
        pass


def launch():
    if not PYTHONW.is_file():
        raise RuntimeError("Python RAMBLA non trovato: " + str(PYTHONW))
    if not BRIDGE.is_file():
        raise RuntimeError("Bridge RAMBLA non trovato: " + str(BRIDGE))
    subprocess.Popen(
        [str(PYTHONW), str(BRIDGE)],
        cwd=str(APP_ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=0x08000000,
    )


try:
    launch()
except Exception as exc:
    show_error(exc)
