"""Portable selected-media package independent of Resolve scripting.

Only packages actual files beneath the project's own folder. Missing media
are represented by metadata, not invented clip assets.
"""
from __future__ import annotations

import json
import hashlib
import re
import zipfile
from pathlib import Path
from typing import Any

from .broll_timeline_export import render_fcp7_xml


def safe_name(value: Any, *, fallback: str = "asset", limit: int = 52) -> str:
    value = re.sub(r"[^a-zA-Z0-9À-ÿ._-]+", "_", str(value or "")).strip("._-")
    return (value[:limit].rstrip("._-") or fallback)


def _inside(source: Path, root: Path) -> bool:
    try:
        return source.resolve().is_relative_to(root.resolve()) and source.is_file()
    except OSError:
        return False


def create_media_pack(
    target: Path,
    *,
    project_id: str,
    project_name: str,
    project_root: Path,
    timeline: dict[str, Any],
    generic_rows: list[dict[str, Any]] | None = None,
    selected_generics: list[str] | None = None,
    selected_images: list[dict[str, Any]] | None = None,
    captions_srt: str = "",
    titles: list[dict[str, Any]] | None = None,
    source_video_path: str = "",
) -> dict[str, Any]:
    """Write ZIP grouped by beat/location; report files that were not available.

    The FCP7 XML preserves local source path URLs for immediate import on the
    same PC. For a different PC Resolve will ask to relink the media.
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    project_root = Path(project_root).resolve()
    rows: list[dict[str, Any]] = []
    missed: list[dict[str, str]] = []
    unique: set[str] = set()
    archive_sources: dict[str, Path] = {}
    safe_timeline_clips: list[dict[str, Any]] = []
    path_map: dict[str, str] = {}
    safe_generics: list[dict[str, Any]] = []

    def add(z: zipfile.ZipFile, source_value: Any, arcname: str, *, label: str, source_page: str = "", beat_id: str = "") -> str | None:
        source = Path(str(source_value or ""))
        if not source_value or not _inside(source, project_root):
            missed.append({"label": label, "beat_id": beat_id, "source_page": source_page, "reason": "File non disponibile nella cartella del progetto"})
            return
        if arcname in unique:
            if archive_sources[arcname] == source.resolve():
                path_map[str(source_value)] = arcname
                return arcname
            path = Path(arcname)
            suffix = hashlib.sha256(str(source.resolve()).encode('utf-8')).hexdigest()[:12]
            arcname = str(path.with_name(path.stem + '_' + suffix + path.suffix)).replace('\\', '/')
        unique.add(arcname)
        archive_sources[arcname] = source.resolve()
        z.write(source, arcname, compress_type=zipfile.ZIP_STORED)
        rows.append({"path": arcname, "source_path": str(source), "beat_id": beat_id, "title": label, "source_page": source_page})
        path_map[str(source_value)] = arcname
        return arcname

    with zipfile.ZipFile(target, "w", allowZip64=True) as z:
        if source_video_path:
            source_suffix=Path(source_video_path).suffix.lower()
            add(z, source_video_path, '00_VIDEO_ORIGINALE/video_originale'+source_suffix,
                label='Video originale')
        for row in timeline.get("clips", []):
            beat = safe_name(row.get("beat_id"), fallback="frase")
            asset = safe_name(row.get("asset_id"), fallback="clip")
            source = str(row.get("media_path") or "")
            suffix = Path(source).suffix.lower()
            if suffix not in {".mp4", ".mov", ".mkv", ".webm", ".jpg", ".jpeg", ".png", ".webp"}:
                suffix = ".mp4"
            destination = f"01_FRASI/{beat}/{asset}{suffix}"
            added = add(z, source, destination, label=str(row.get("title") or asset),
                beat_id=str(row.get("beat_id") or ""), source_page=str(row.get("source_page") or ""))
            if added:
                safe_timeline_clips.append(row)

        # Include selected high-resolution images even if the timeline planner
        # could not place them (e.g. a missing target time range).
        for row in selected_images or []:
            beat = safe_name(row.get("beat_id"), fallback="frase")
            asset = safe_name(row.get("asset_id"), fallback="immagine")
            source = str(row.get("media_path") or "")
            suffix = Path(source).suffix.lower()
            if suffix not in {".png", ".jpeg", ".jpg", ".webp"}:
                continue
            destination = f"01_FRASI/{beat}/{asset}{suffix}"
            add(z, source, destination, label=str(row.get("title") or asset),
                beat_id=str(row.get("beat_id") or ""), source_page=str(row.get("source_page") or ""))

        chosen = set(map(str, selected_generics or []))
        for row in generic_rows or []:
            provider_id = str(row.get("provider_id") or "")
            if provider_id not in chosen:
                continue
            location = safe_name(row.get("place"), fallback="TEMA_GENERALE")
            provider = safe_name(row.get('provider'),fallback='pexels')
            source = Path(str(row.get('media_path') or project_root / 'run' / 'resolve-media' / 'pexels' / f'pexels_{provider_id}.mp4'))
            arc = f"02_LUOGHI_E_GENERICI/{location}/{provider}_{safe_name(provider_id)}{source.suffix or '.mp4'}"
            add(z, str(source), arc, label=str(row.get("title") or provider_id),
                beat_id="generic:" + provider_id, source_page=str(row.get("source_page") or ""))
            safe_generics.append({**row, 'media_path':str(source), 'role':'generic'})

        for entry in timeline.get("unavailable", []):
            missed.append({"label": str(entry.get("asset_id") or ""), "beat_id": str(entry.get("beat_id") or ""),
                           "source_page": "", "reason": str(entry.get("reason") or "Media non disponibile")})

        # The XML is generated using the authoritative time ranges; it may
        # require Resolve's Relink Media after moving this ZIP to another PC.
        xml_plan = {**timeline, "clips": safe_timeline_clips}
        xml = render_fcp7_xml(xml_plan, sequence_name=project_name + " - BROLL")
        z.writestr("03_RESOLVE/timeline.xml", xml)
        z.writestr("03_RESOLVE/sottotitoli.srt", captions_srt)
        z.writestr("03_RESOLVE/titoli_e_testi.json", json.dumps(titles or [], ensure_ascii=False, indent=2))
        from .omnicut_handoff import build_handoff
        context = build_handoff({'project_id':project_id,'project_name':project_name,'fps':timeline.get('fps'),
            'duration_seconds': (float(timeline.get('duration_frames') or 0) / float(timeline.get('fps') or 1)),
            'broll_clips':safe_timeline_clips,'generic_broll_clips':safe_generics,'titles':titles or [],
            'unplaced_images':selected_images or [],
            'broll_unavailable':timeline.get('unavailable') or [],'original_video':{'source_path':source_video_path}},
            project_root=project_root,path_map=path_map)
        z.writestr('04_OMNICUT/progetto.json',json.dumps(context,ensure_ascii=False,indent=2))
        manifest = {
            "version": 1, "project_id": project_id, "project_name": project_name,
            "media": rows, "missing": missed, "subtitle_format": "srt",
            "timeline_format": "fcpxml-v5", "resolve_drp_included": False,
        }
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        readme = (
            "RMBL B ROLL - Media Pack\n\n"
            "01_FRASI: B-roll e immagini disponibili suddivisi per frase.\n"
            "02_LUOGHI_E_GENERICI: video Pexels selezionati, organizzati per luogo.\n"
            "03_RESOLVE/timeline.xml: timeline FCP7 XML importabile in DaVinci Resolve.\n"
            "03_RESOLVE/sottotitoli.srt: sottotitoli importabili direttamente.\n"
            "03_RESOLVE/titoli_e_testi.json: posizioni e testi delle evidenziazioni,\n"
            "04_OMNICUT/progetto.json: contesto e tempi selezionati per una futura integrazione OmniCut.\n"
            "non equivalgono a titoli Fusion gia' ricostruiti nella timeline.\n"
            "Se muovi il pacchetto, in Resolve usa RELINK MEDIA verso le cartelle estratte.\n"
            "Il file .DRP non e' generabile indipendentemente dalle API Resolve.\n"
            "I media assenti non bloccano il pacchetto: consulta manifest.json.\n"
            "L'archivio non contiene font, chiavi API o cookie.\n"
        )
        z.writestr("LEGGIMI.txt", readme)
    return {"archive": str(target), "media_count": len(rows), "missing_count": len(missed)}
