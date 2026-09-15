from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

DEFAULT_MODEL_CACHE = Path(
    r"Z:\APP REEL TEST\qwen-embedding-smoke\models\asr\faster-whisper"
)
DEFAULT_MODEL = DEFAULT_MODEL_CACHE / "large-v3-turbo"
DEFAULT_MODEL_ROOT = Path(r"Z:\APP REEL TEST\qwen-embedding-smoke\models")
DEFAULT_EMBEDDING_CODE = Path(r"Z:\APP REEL TEST\qwen-embedding-smoke\official-code")
DEFAULT_PIPELINE_PYTHON = Path(r"Z:\APP REEL TEST\qwen-embedding-smoke\venv\Scripts\python.exe")


def _event(stage: str, progress: float, message: str, **data: Any) -> None:
    print(
        "RAMBLA_EVENT "
        + json.dumps(
            {"stage": stage, "progress": progress, "message": message, "data": data},
            ensure_ascii=False,
        ),
        flush=True,
    )


def _write_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _probe(video: Path) -> tuple[float, int]:
    completed = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=avg_frame_rate:format=duration",
            "-of", "json", str(video),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    duration = float(payload["format"]["duration"])
    numerator, denominator = payload["streams"][0]["avg_frame_rate"].split("/", 1)
    fps = float(numerator) / float(denominator)
    return duration, max(1, round(duration * fps))


def _input_signature(video: Path) -> dict[str, Any]:
    stat = video.stat()
    return {"video": str(video.resolve()), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def analysis_input_signature(video: Path, guide_audio: Path | None) -> dict[str, Any]:
    return {"source": _input_signature(video.resolve()), "guide": _input_signature((guide_audio or video).resolve())}


def persist_analysis_signature(output: Path, signature: str) -> None:
    required = (output / "semantic-chunks.json", output / "review.html", output / "edit-plan.json")
    if signature and all(path.is_file() for path in required):
        _write_json(output / "analysis-signature.json", {"analysis_signature": signature})


def editorial_artifacts_match(output_dir: Path, analysis_signature: str) -> bool:
    marker = output_dir / "analysis-signature.json"
    if not marker.is_file():
        return False
    try:
        recorded = json.loads(marker.read_text(encoding="utf-8")).get("analysis_signature")
    except (OSError, json.JSONDecodeError):
        return False
    return recorded == analysis_signature and has_editorial_artifacts(output_dir)


def invalidate_stale_analysis_outputs(output_dir: Path, analysis_signature: str) -> None:
    if editorial_artifacts_match(output_dir, analysis_signature):
        return
    for name in ("online-candidates.json", "image-candidates.json", "video-sourcing.json", "image-sourcing.json", "video-sourcing-diagnostics.json", "edit-plan.json", "review.html", "analysis-signature.json"):
        path = output_dir / name
        if path.is_file():
            path.unlink()


def has_editorial_artifacts(output_dir: Path) -> bool:
    return all((output_dir / name).is_file() for name in (
        "online-candidates.json", "edit-plan.json", "review.html",
    ))


def discover_image_candidates(
    chunks: list[dict[str, Any]], output_dir: Path, *, sources: list[Any] | None = None
) -> dict[str, Any]:
    """Persist lightweight image discovery once; subsequent runner calls reuse it."""
    artifact = output_dir / "image-candidates.json"
    if artifact.is_file():
        cached = json.loads(artifact.read_text(encoding="utf-8"))
        if any(row.get("candidates") for row in cached.get("chunks", {}).values()):
            return cached

    from .image_sources import PexelsPhotoSource, WikimediaImageSource, search_image_candidates

    active_sources = sources if sources is not None else [WikimediaImageSource()]
    if sources is None and os.environ.get("PEXELS_API_KEY", "").strip():
        active_sources.append(PexelsPhotoSource(os.environ["PEXELS_API_KEY"]))

    async def collect() -> dict[str, Any]:
        result: dict[str, Any] = {"schema_version": "curation-images-0.1", "chunks": {}, "errors": []}
        for chunk in chunks:
            variants = semantic_query_variants(str(chunk.get("text") or "").strip())
            query = variants[0] if variants else str(chunk.get("text") or "").strip()
            rows, errors = await search_image_candidates(query, sources=active_sources)
            result["chunks"][str(chunk["id"])] = {
                "query": query,
                "candidates": [asdict(row) for row in rows],
            }
            result["errors"].extend({"chunk_id": str(chunk["id"]), **error} for error in errors)
        return result

    payload = asyncio.run(collect())
    _write_json(artifact, payload)
    return payload


def run_asr_stage(
    video: Path,
    *,
    model_factory: Callable[..., Any] | None = None,
    model_name: str = "turbo",
    cache_dir: Path,
    timeline_fps: int | None = None,
    progress_callback: Callable[[dict[str, Any], float], None] | None = None,
) -> tuple[dict[str, Any], str]:
    if model_factory is None:
        from faster_whisper import WhisperModel

        model_factory = WhisperModel
    try:
        model = model_factory(
            model_size_or_path=model_name,
            device="cuda",
            compute_type="float16",
            download_root=str(cache_dir),
        )
        mode = "cuda/float16"
        segments, info = model.transcribe(
            str(video), language="it", word_timestamps=True, vad_filter=True
        )
        rows = _consume_segments(segments, info, timeline_fps, progress_callback)
    except Exception:
        model = model_factory(
            model_size_or_path=model_name,
            device="cpu",
            compute_type="int8",
            download_root=str(cache_dir),
        )
        mode = "cpu/int8"
        segments, info = model.transcribe(
            str(video), language="it", word_timestamps=True, vad_filter=True
        )
        rows = _consume_segments(segments, info, timeline_fps, progress_callback)
    transcript = normalize_faster_whisper(
            rows,
            language=str(getattr(info, "language", "it") or "it"),
            duration_seconds=float(getattr(info, "duration", rows[-1].end if rows else 0.0)),
        )
    if timeline_fps is not None:
        transcript["timeline_fps"] = int(timeline_fps)
    return transcript, mode


def _consume_segments(segments: Any, info: Any, timeline_fps: int | None, callback: Callable[[dict[str, Any], float], None] | None) -> list[Any]:
    rows = []
    duration = max(0.001, float(getattr(info, "duration", 0.0) or 0.0))
    for segment in segments:
        rows.append(segment)
        if callback:
            partial = normalize_faster_whisper(rows, language=str(getattr(info, "language", "it") or "it"), duration_seconds=duration)
            if timeline_fps is not None: partial["timeline_fps"] = int(timeline_fps)
            callback(partial, min(99.0, 100.0 * float(segment.end) / duration))
    return rows


def normalize_faster_whisper(
    segments: Any, *, language: str, duration_seconds: float
) -> dict[str, Any]:
    normalized = []
    for segment in segments:
        normalized.append(
            {
                "start": float(segment.start),
                "end": float(segment.end),
                "text": str(segment.text).strip(),
                "words": [
                    {
                        "start": float(word.start),
                        "end": float(word.end),
                        "text": str(word.word).strip(),
                    }
                    for word in (segment.words or [])
                    if word.start is not None and word.end is not None
                ],
            }
        )
    return {
        "language": language,
        "duration": float(duration_seconds),
        "segments": normalized,
    }


def build_short_outline(
    transcript: dict[str, Any], *, max_chunk_seconds: float = 4.0
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build deterministic idea-first chunks with time only as a safety bound."""
    words = [
        dict(word)
        for segment in transcript.get("segments", [])
        for word in segment.get("words", [])
    ]
    chunks: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    contrast_starters = {"ma", "però", "pero", "invece", "quindi", "mentre", "tuttavia", "perché", "perche"}
    for word in words:
        token = str(word.get("text", "")).strip()
        if current and token.casefold().strip(".,;:!?") in contrast_starters and len(current) >= 3:
            chunks.append(_chunk(current, len(chunks))); current = []
        if current and float(word["end"]) - float(current[0]["start"]) > max_chunk_seconds:
            chunks.append(_chunk(current, len(chunks)))
            current = []
        current.append(word)
        if len(current) >= 4 and token.endswith((".", "!", "?", ";")):
            chunks.append(_chunk(current, len(chunks))); current = []
    if current:
        chunks.append(_chunk(current, len(chunks)))

    beats = []
    for row in chunks:
        text = row["text"]
        tokens = text.split()
        has_named_subject = any(
            any(char.isupper() for char in token[1:])
            for token in tokens
        )
        beats.append(
            {
                "id": row["id"],
                "start_seconds": row["start"],
                "end_seconds": row["end"],
                "intent": text,
                "broll_queries": semantic_query_variants(text) if has_named_subject or len(tokens) >= 5 else [],
            }
        )
    return {"schema_version": "content-sprint-0.1", "beats": beats}, chunks


def semantic_query_variants(text: str) -> list[str]:
    stop = {"il", "lo", "la", "i", "gli", "le", "un", "una", "e", "di", "a", "da", "in", "con", "su", "per", "che", "si", "sono"}
    tokens = [token.strip(".,;:!?()\"") for token in text.split()]
    concrete = [token for token in tokens if token and token.casefold() not in stop]
    literal = " ".join(concrete[:8])
    context = " ".join(concrete[-6:])
    return list(dict.fromkeys(query for query in (literal, context) if len(query.split()) >= 2))[:2]


def build_video_diagnostics(results: list[dict[str, Any]]) -> dict[str, Any]:
    chunks = []
    for row in results:
        candidates = list(row.get("candidates") or [])
        rejected = list(row.get("rejected_candidates") or [])
        errors = list(row.get("errors") or row.get("sourcing_errors") or [])
        chunks.append({
            "chunk_id": row.get("parent_beat_id") or row.get("beat_id"),
            "queries": row.get("queries") or ([row["query"]] if row.get("query") else []),
            "providers": sorted({str(item.get("source") or item.get("provider")) for item in candidates if item.get("source") or item.get("provider")}),
            "raw_results": int(row.get("raw_result_count") or len(candidates) + len(rejected)),
            "rejected": len(rejected),
            "rejection_reasons": sorted({str(item.get("reason") or item.get("rejection_reason")) for item in rejected}),
            "ranked": [{"asset_id": item.get("id"), "score": item.get("qwen_score", item.get("score")), "preview": "ready" if item.get("preview_path") else "failed"} for item in candidates],
            "errors": errors,
        })
    return {"schema_version": "video-sourcing-diagnostics-0.1", "chunks": chunks}


def persist_video_diagnostics(output: Path) -> None:
    path = output / "online-candidates.json"
    rows = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    _write_json(output / "video-sourcing-diagnostics.json", build_video_diagnostics(rows if isinstance(rows, list) else []))


def _chunk(words: list[dict[str, Any]], index: int) -> dict[str, Any]:
    start = float(words[0]["start"])
    end = float(words[-1]["end"])
    return {
        "id": f"chunk-{index + 1}",
        "start": start,
        "end": end,
        "duration": end - start,
        "text": " ".join(str(word["text"]).strip() for word in words),
        "words": words,
    }


def _video_sourcing_command(output: Path, transcript_path: Path, outline_path: Path, client_id: str, source_frames: int) -> list[str]:
    return [
        str(DEFAULT_PIPELINE_PYTHON if DEFAULT_PIPELINE_PYTHON.is_file() else Path(sys.executable)),
        "-m", "backend.app.online_sourcing_cli", "--transcript", str(transcript_path),
        "--outline", str(outline_path), "--output-dir", str(output), "--client-id", client_id,
        "--source-frames", str(source_frames), "--model-root", str(DEFAULT_MODEL_ROOT),
        "--embedding-code-root", str(DEFAULT_EMBEDDING_CODE),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the existing RAMBLA editorial smoke from a raw video")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--guide-audio", type=Path)
    parser.add_argument("--analysis-signature", default="")
    parser.add_argument("--stage", choices=("analyze", "videos", "images", "all"), default="all")
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--model-cache", type=Path, default=DEFAULT_MODEL_CACHE)
    parser.add_argument("--client-id", default="debug-kura")
    args = parser.parse_args()

    video = args.video.resolve()
    output = args.output_dir.resolve()
    if not video.is_file():
        raise SystemExit(f"video not found: {video}")
    guide_audio = args.guide_audio.resolve() if args.guide_audio else video
    if not guide_audio.is_file():
        raise SystemExit(f"guide audio not found: {guide_audio}")
    output.mkdir(parents=True, exist_ok=True)
    args.model_cache.mkdir(parents=True, exist_ok=True)
    duration, source_frames = _probe(video)
    timeline_fps = max(1, round(source_frames / duration))
    signature = analysis_input_signature(video, guide_audio)
    analysis_signature = args.analysis_signature or hashlib.sha256(
        json.dumps(signature, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    transcript_path = output / "transcript-raw.json"
    outline_path = output / "semantic-beats.json"
    chunks_path = output / "semantic-chunks.json"
    if args.stage in {"videos", "images"}:
        if not chunks_path.is_file() or not transcript_path.is_file() or not outline_path.is_file():
            raise SystemExit("analysis required before sourcing")
        chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
        if args.stage == "images":
            _event("image_search", 1, "Image sourcing avviato", items=len(chunks))
            images = discover_image_candidates(chunks, output)
            _write_json(output / "image-sourcing.json", {"status": "complete", "chunks": len(chunks)})
            _event("image_search", 100, "Image sourcing completato", chunks=len(images.get("chunks", {})))
            return
        _event("online_search", 1, "Video sourcing avviato", items=len(chunks))
        subprocess.run(_video_sourcing_command(output, transcript_path, outline_path, args.client_id, source_frames), check=True)
        persist_video_diagnostics(output)
        _write_json(output / "video-sourcing.json", {"status": "complete", "chunks": len(chunks)})
        _event("online_search", 100, "Video sourcing completato", chunks=len(chunks))
        return
    invalidate_stale_analysis_outputs(output, analysis_signature)
    signature_path = output / "run-input.json"
    cached = False
    if signature_path.is_file() and transcript_path.is_file():
        cached = json.loads(signature_path.read_text(encoding="utf-8")) == signature

    _event("prepare", 100, "Input verificato", video=str(video), duration=duration)
    if cached:
        transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
        if transcript.get("timeline_fps") != timeline_fps:
            transcript["timeline_fps"] = timeline_fps
            _write_json(transcript_path, transcript)
        mode = "cache"
        _event("asr", 100, "Transcript ASR riusato dalla cache", artifact=str(transcript_path))
    else:
        _event("asr", 1, "Avvio faster-whisper", model=args.model)
        transcript, mode = run_asr_stage(
            guide_audio,
            model_name=args.model,
            cache_dir=args.model_cache,
            timeline_fps=timeline_fps,
            progress_callback=lambda partial, progress: (
                _write_json(transcript_path, partial),
                _event("asr", progress, "Trascrizione in corso", segments=len(partial["segments"])),
            ),
        )
        _write_json(transcript_path, transcript)
        _write_json(signature_path, signature)
        _event(
            "asr", 100, "Trascrizione completata", mode=mode,
            segments=len(transcript["segments"]),
            words=sum(len(row["words"]) for row in transcript["segments"]),
            artifact=str(transcript_path),
        )

    outline, chunks = build_short_outline(transcript)
    _write_json(outline_path, outline)
    _write_json(chunks_path, chunks)
    _event("semantic_chunking", 100, "Chunk e outline pronti", chunks=len(chunks))

    _write_json(output / "analysis-signature.json", {"analysis_signature": analysis_signature})
    if args.stage == "analyze":
        _event("analysis", 100, "Analisi transcript completata", chunks=len(chunks))
        return

    images = discover_image_candidates(chunks, output)
    _event("image_search", 100, "Candidati immagini pronti", chunks=len(images.get("chunks", {})))

    if editorial_artifacts_match(output, analysis_signature):
        _event("online_search", 100, "Artifact Editorial Intelligence riusati")
        _event("review", 100, "Review riusata", artifact=str(output / "review.html"), asr_mode=mode)
        persist_analysis_signature(output, analysis_signature)
        return
    _event("online_search", 1, "Avvio pipeline Editorial Intelligence esistente")
    command = _video_sourcing_command(output, transcript_path, outline_path, args.client_id, source_frames)
    subprocess.run(command, check=True)
    persist_video_diagnostics(output)
    persist_analysis_signature(output, analysis_signature)
    _event("review", 100, "Review pronta", artifact=str(output / "review.html"), asr_mode=mode)


if __name__ == "__main__":
    main()
