"""Import the video uploaded before analysis as a full, uncut Resolve base.

This is independent from AutoCut: the input is never trimmed or transcoded.
Resolve receives the original file (and its embedded audio, when present).
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import math
from pathlib import Path
from typing import Any


def load_original_video(project: Any) -> dict[str, Any]:
    source = getattr(project, "source_video", None)
    if source is None:
        raise ValueError("Carica un video nel progetto prima di esportare il video originale")
    path = Path(str(source.path)).resolve()
    if not path.is_file():
        raise ValueError("Il video caricato non e piu disponibile sul disco")
    stat = path.stat()
    actual = hashlib.sha256(
        f"{path}|{stat.st_size}|{stat.st_mtime_ns}".encode()
    ).hexdigest()
    if actual != source.signature:
        raise ValueError("Il video caricato e cambiato: registralo nuovamente prima di inviarlo a Resolve")
    if not math.isfinite(source.duration) or source.duration <= 0:
        raise ValueError("Durata del video originale non valida")
    if not math.isfinite(source.fps) or source.fps <= 0:
        raise ValueError("FPS del video originale non validi")
    if source.width <= 0 or source.height <= 0:
        raise ValueError("Dimensioni del video originale non valide")
    rate = Fraction(str(source.fps)).limit_denominator(1001)
    if abs(float(rate) - source.fps) > .003:
        raise ValueError("FPS del video originale non rappresentabili con precisione in Resolve")
    frames = int(round(source.duration * float(rate)))
    if frames < 1:
        raise ValueError("Il video originale non contiene fotogrammi utilizzabili")
    return {
        "source_path": str(path),
        "source_identity": {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns},
        "source_signature": source.signature,
        "fps": str(rate),
        "width": int(source.width),
        "height": int(source.height),
        "duration_frames": frames,
        "duration_seconds": float(source.duration),
        "has_audio": bool(source.has_audio),
    }


def uncut_native_contract(original: dict[str, Any]) -> dict[str, Any]:
    """Reuse the verified native Resolve A/V append with exactly one full segment.

    This is not a CUT plan: it has no take selection, trimming or re-encoding.
    """
    n = int(original["duration_frames"])
    if n <= 0:
        raise ValueError("Video originale senza fotogrammi")
    return {
        "source_path": original["source_path"],
        "source_identity": dict(original["source_identity"]),
        "fps": original["fps"],
        "width": int(original["width"]),
        "height": int(original["height"]),
        "source_duration_frames": n,
        "duration_frames": n,
        "segments": [{
            "source_in_frame": 0, "source_out_frame": n,
            "edited_in_frame": 0, "edited_out_frame": n,
        }],
        "alternatives": [],
        "revision": "original-uncut",
        "source_has_audio": bool(original.get("has_audio", True)),
    }
