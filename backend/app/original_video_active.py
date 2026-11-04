"""Safely place or reuse an uncut uploaded source in the active Resolve timeline.

A source-video export can target the existing timeline without duplicating the
video or touching a different editor's footage. The caller owns a BCK snapshot
before any append and restores it on failure.
"""
from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

from .resolve_native_cut import (
    append_exact_segment, verify_native_cut_base, verify_source_identity,
)


def _all_timeline_items(timeline: Any, kind: str) -> list[tuple[int, Any]]:
    return [
        (track, item)
        for track in range(1, int(timeline.GetTrackCount(kind) or 0) + 1)
        for item in (timeline.GetItemListInTrack(kind, track) or [])
    ]


def _matches_source(item: Any, source: dict[str, Any], base_frame: int) -> bool:
    media_getter = getattr(item, "GetMediaPoolItem", None)
    media = media_getter() if callable(media_getter) else None
    prop = getattr(media, "GetClipProperty", None)
    if not callable(prop):
        return False
    actual_path = str(prop("File Path") or "")
    try:
        same_path = Path(actual_path).resolve() == Path(source["source_path"]).resolve()
    except (OSError, ValueError):
        return False
    return (
        same_path
        and int(item.GetStart()) == int(base_frame)
        and int(item.GetEnd()) == int(base_frame) + int(source["duration_frames"])
    )


def inspect_active_original_timeline(timeline: Any, source: dict[str, Any]) -> str:
    """Return import/reuse, or reject mismatched footage before any mutation."""
    verify_source_identity(source)
    from_rate = float(Fraction(str(source["fps"])))
    timeline_rate = float(timeline.GetSetting("timelineFrameRate") or 0)
    if abs(from_rate - timeline_rate) > .003:
        raise ValueError(
            f"FPS della timeline attiva ({timeline_rate:g}) diversi dal video caricato "
            f"({from_rate:g}): crea una nuova timeline o disattiva Video originale."
        )
    base_frame = int(timeline.GetStartFrame())
    videos = _all_timeline_items(timeline, "video")
    audios = _all_timeline_items(timeline, "audio")
    if not videos:
        if audios:
            raise ValueError(
                "La timeline ha audio ma non video: impossibile importare il video "
                "originale senza rischiare di sovrapporre audio esistente. "
                "Usa una timeline vuota oppure deseleziona Video originale."
            )
        return "import"
    main = [item for track, item in videos if track == 1]
    if len(main) != 1 or not _matches_source(main[0], source, base_frame):
        raise ValueError(
            "La timeline attiva contiene un montaggio video differente. "
            "Per preservarlo, deseleziona Video originale e applica solo subs/B-roll, "
            "oppure scegli Crea nuova timeline."
        )
    if source.get("source_has_audio", True):
        audio_main = [item for track, item in audios if track == 1]
        if len(audio_main) != 1 or not _matches_source(audio_main[0], source, base_frame):
            raise ValueError(
                "L'audio A1 non corrisponde al video originale caricato. "
                "Nessuna modifica eseguita: scegli Crea nuova timeline "
                "oppure deseleziona Video originale."
            )
    return "reuse"


def append_active_original_video(
    media_pool: Any,
    timeline: Any,
    source: dict[str, Any],
    state: str,
) -> dict[str, int | str]:
    base_frame = int(timeline.GetStartFrame())
    if state == "import":
        path = verify_source_identity(source)
        imported = media_pool.ImportMedia([str(path)]) or []
        if len(imported) != 1:
            raise RuntimeError("Resolve non ha importato il video caricato")
        kinds = (1, 2) if source.get("source_has_audio", True) else (1,)
        clips, _ = append_exact_segment(
            media_pool, timeline, imported[0], source["segments"][0],
            base_frame, media_types=kinds,
        )
        if len(clips) > 1:
            linker = getattr(timeline, "SetClipsLinked", None)
            if callable(linker) and linker(clips, True) is False:
                raise RuntimeError("Resolve non ha collegato il video originale e il suo audio")
    elif state != "reuse":
        raise ValueError("Stato video originale non valido")
    verified = verify_native_cut_base(timeline, source, base_frame)
    return {**verified, "source_mode": state, "base_frame": base_frame}
