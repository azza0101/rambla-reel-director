from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import inspect
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


from .atomic_io import write_json as _write_json


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
    return recorded == analysis_signature and has_editorial_artifacts(output_dir) and has_concrete_visual_video_artifact(output_dir)


def has_concrete_visual_video_artifact(output_dir: Path) -> bool:
    path = output_dir / "visual-plan.json"
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    chunks = artifact.get("chunks", {}) if isinstance(artifact, dict) else {}
    return bool(chunks) and all(isinstance(row.get("video_search"), dict) for row in chunks.values())


def invalidate_stale_analysis_outputs(output_dir: Path, analysis_signature: str) -> None:
    if editorial_artifacts_match(output_dir, analysis_signature):
        return
    for name in ("online-candidates.json", "image-candidates.json", "video-sourcing.json", "image-sourcing.json", "video-sourcing-diagnostics.json", "visual-plan.json", "edit-plan.json", "review.html", "analysis-signature.json"):
        path = output_dir / name
        if path.is_file():
            path.unlink()


def has_editorial_artifacts(output_dir: Path) -> bool:
    return all((output_dir / name).is_file() for name in (
        "online-candidates.json", "edit-plan.json", "review.html",
    ))


def _source_name(source: Any) -> str:
    return str(getattr(source, "provider_name", "") or type(source).__name__.replace("ImageSource", "").replace("PhotoSource", "")).casefold()


def build_image_intent(index: int, chunks: list[dict[str, Any]], outline: dict[str, Any] | None = None) -> dict[str, Any]:
    """Diagnostic-only lexical intent; production sourcing requires a generated plan."""
    current = str(chunks[index].get('text') or '')
    nearby = ' '.join(str(c.get('text') or '') for c in chunks[max(0,index-1):index+2])
    beat = next((b for b in (outline or {}).get('beats',[]) if str(b.get('id')) == str(chunks[index]['id'])),{})
    return {'intent':beat.get('intent') or current,'queries':semantic_query_variants(current),'context':nearby,'editorial_intent':beat.get('intent','')}


def discover_image_candidates(
    chunks: list[dict[str, Any]], output_dir: Path, *, sources: list[Any] | None = None,
    outline: dict[str, Any] | None = None, ranker: Any = None,
    preview_fetcher: Callable[[str], Any] | None = None, relevance_floor: float = 0.30,
    client_id: str = "debug-reel", event_callback: Callable[..., None] | None = None,
    visual_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Search, locally materialize and Qwen-rank images with per-chunk resumability."""
    if sources is None and not visual_plan:
        raise ValueError("imported visual plan required before production image sourcing")
    artifact = output_dir / "image-candidates.json"
    intents = {}
    for index, chunk in enumerate(chunks):
        chunk_id = str(chunk["id"])
        planned = (visual_plan or {}).get("chunks", {}).get(chunk_id)
        if not planned:
            if sources is None: raise ValueError(f"missing imported visual beat: {chunk_id}")
            intents[chunk_id] = build_image_intent(index, chunks, outline)
            continue
        shots = list(planned.get("shots") or [])
        queries = [query for shot in shots for query in shot.get("image_queries", [])]
        intents[chunk_id] = {
            "intent": planned["core_meaning"], "queries": queries, "context": planned.get("local_context", ""),
            "editorial_function": planned.get("editorial_function"), "subtext": planned.get("subtext"),
            "visual_mode": planned.get("visual_mode"), "shots": shots, "avoid": planned.get("avoid", []),
            "planner_provider": planned.get("planner_provider"), "planning_score": planned.get("planning_score"),
        }
    if artifact.is_file():
        try: cached = json.loads(artifact.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError): cached = {"chunks": {}}
    else: cached = {"chunks": {}}

    from .image_sources import GoogleImageSource, PexelsPhotoSource, WikimediaImageSource, search_image_candidates
    from .media_quality import image_quality, diverse_candidates

    active_sources = sources if sources is not None else [WikimediaImageSource()]
    if sources is None and os.environ.get("PEXELS_API_KEY", "").strip():
        active_sources.append(PexelsPhotoSource(os.environ["PEXELS_API_KEY"]))

    if sources is None and os.environ.get('GOOGLE_API_KEY') and os.environ.get('GOOGLE_CSE_ID'):
        active_sources.append(GoogleImageSource(os.environ['GOOGLE_API_KEY'], os.environ['GOOGLE_CSE_ID']))
    quality_signature = hashlib.sha256(json.dumps({'version':3,'intents':intents,'floor':relevance_floor,'providers':[_source_name(x) for x in active_sources],'ranker':type(ranker).__name__},sort_keys=True).encode()).hexdigest()

    async def fetch(url: str) -> bytes:
        if preview_fetcher is not None:
            value = preview_fetcher(url)
            return await value if inspect.isawaitable(value) else value
        import httpx
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": "RAMBLA-Reel-Director/0.2 (https://github.com/azza0101/rambla-reel-director)"}) as client:
            response = await client.get(url); response.raise_for_status(); return response.content

    async def collect() -> dict[str, Any]:
        result: dict[str, Any] = {"schema_version": "curation-images-0.2", "chunks": {}, "errors": [], "active_providers": [_source_name(source) for source in active_sources]}
        reused = 0; retried = 0
        history = []; duplicate_count = 0
        result["quality_signature"] = quality_signature
        cache_root = output_dir / "image-cache"; cache_root.mkdir(parents=True, exist_ok=True)
        for index, chunk in enumerate(chunks):
            chunk_id = str(chunk["id"]); intent = intents[chunk_id]
            planned = (visual_plan or {}).get('chunks', {}).get(chunk_id, {})
            if planned.get('visual_action', 'BROLL') != 'BROLL':
                result['chunks'][chunk_id] = {'status':'not_requested', 'visual_action':planned['visual_action'], 'candidates':[], 'accepted_count':0, 'raw_count':0, 'queries':[], 'active_providers':[], 'zero_result_reason':planned['visual_action']}
                continue
            from .media_quality import other_media_history
            cross_media = other_media_history(output_dir, 'video', chunk_id)
            queries = intent["queries"] or [str(chunk.get("text") or "image")]
            previous = cached.get("chunks", {}).get(chunk_id, {})
            previous_queries = previous.get("queries") or ([previous.get("query")] if previous.get("query") else [])
            if previous.get("candidates") and previous_queries == queries and cached.get("quality_signature") == quality_signature and all(Path(c.get("preview_path") or "missing").is_file() for c in previous["candidates"]):
                row = dict(previous, cache_status="reused"); row["candidates"], removed = diverse_candidates(row["candidates"], history + cross_media, limit=4); row["accepted_count"] = len(row["candidates"]); history.extend(row["candidates"]); duplicate_count += removed; result["chunks"][chunk_id] = row; reused += 1
                if event_callback: event_callback("image_search", 100 * (index + 1) / max(1, len(chunks)), "Image chunk reused", chunk_id=chunk_id, **{key: row.get(key) for key in ("raw_count", "accepted_count", "active_providers")})
                continue
            retried += 1; gathered = {}; errors = []
            query_to_shot = {
                query: shot for shot in intent.get("shots", []) for query in shot.get("image_queries", [])
            }
            for query in queries:
                if event_callback: event_callback("image_search",100*index/max(1,len(chunks)),"Searching images",chunk_id=chunk_id,query=query,providers=result["active_providers"])
                rows, query_errors = await search_image_candidates(query, sources=active_sources, per_source_limit=5)
                errors.extend({"query": query, **error} for error in query_errors)
                for candidate in rows: gathered.setdefault((candidate.provider, candidate.provider_id), candidate)
            materialized = []
            for candidate in gathered.values():
                if max(candidate.width,candidate.height) < 1024 or min(candidate.width,candidate.height) < 480 or candidate.width*candidate.height < 500_000:
                    errors.append({'provider':candidate.provider,'code':'image_dimensions_rejected'})
                    continue
                suffix = Path(candidate.thumbnail_url.split("?", 1)[0]).suffix.lower()
                if suffix not in {".jpg", ".jpeg", ".png", ".webp"}: suffix = ".jpg"
                path = cache_root / f"{hashlib.sha256((candidate.provider + ':' + candidate.provider_id).encode()).hexdigest()[:20]}{suffix}"
                try:
                    if ranker is not None or sources is None:
                        if not path.is_file(): path.write_bytes(await fetch(candidate.thumbnail_url))
                        preview_path = str(path)
                    else:
                        preview_path = None
                    quality = image_quality(path) if preview_path else {}
                    shot = query_to_shot.get(candidate.query, {})
                    materialized.append({**asdict(candidate), **quality, "id": f"{candidate.provider}:{candidate.provider_id}", "client_id": client_id, "path": preview_path or candidate.thumbnail_url, "preview_path": preview_path, "source": candidate.provider, "description": candidate.description or candidate.title, "shot_id": shot.get("shot_id"), "shot_description": shot.get("description")})
                except Exception as exc:
                    errors.append({"query": candidate.query, "provider": candidate.provider, "code": "preview_error", "message": type(exc).__name__})
            originals = {item["id"]: item for item in materialized}
            ranked_groups: list[list[dict[str, Any]]] = []
            shot_rows = intent.get("shots") or [{"shot_id": None, "description": intent["intent"]}]
            for shot in shot_rows:
                group = [item for item in materialized if item.get("shot_id") == shot.get("shot_id")] if intent.get("shots") else materialized
                ranking_intent = str(shot.get("description") or intent["intent"])
                ranked = ranker.rank(ranking_intent, group) if ranker is not None else [dict(item, score=1.0, embedding_score=None, reason="provider order; Qwen ranker unavailable") for item in group]
                accepted_group = []
                for ranked_row in ranked:
                    score = float(ranked_row.get("score", 0))
                    if score < relevance_floor: continue
                    original = originals.get(str(ranked_row.get("id")), {})
                    accepted_group.append({**original, "score": score, "embedding_score": ranked_row.get("embedding_score"), "rank_reason": ranked_row.get("reason"), "matched_query": original.get("query"), "shot_id": shot.get("shot_id"), "shot": shot.get("description")})
                ranked_groups.append(accepted_group)
            accepted = [group[0] for group in ranked_groups if group]
            remainder = sorted((candidate for group in ranked_groups for candidate in group[1:]), key=lambda item: (-float(item.get("score", 0)), str(item.get("id"))))
            accepted, removed = diverse_candidates(accepted + remainder, history + cross_media, limit=4)
            duplicate_count += removed; history.extend(accepted)
            zero_reason = None
            if not gathered: zero_reason = "0 provider results" if not errors else "provider search failed"
            elif not materialized: zero_reason = "no usable HD previews"
            elif not accepted: zero_reason = f"no unique candidates above relevance floor {relevance_floor:.2f}"
            row = {"status": "searched", "cache_status": "refreshed", "intent": intent["intent"], "context": intent["context"], "editorial_function": intent.get("editorial_function"), "subtext": intent.get("subtext"), "visual_mode": intent.get("visual_mode"), "shots": intent.get("shots", []), "avoid": intent.get("avoid", []), "planner_provider": intent.get("planner_provider"), "planning_score": intent.get("planning_score"), "queries": queries, "query": queries[0], "active_providers": result["active_providers"], "raw_count": len(gathered), "accepted_count": len(accepted), "zero_result_reason": zero_reason, "errors": errors, "candidates": accepted}
            result["chunks"][chunk_id] = row; result["errors"].extend({"chunk_id": chunk_id, **error} for error in errors)
            result["cache_reused_chunks"] = reused; result["retried_chunks"] = retried
            _write_json(artifact, result)
            if event_callback: event_callback("image_search", 100 * (index + 1) / max(1, len(chunks)), "Image chunk searched", chunk_id=chunk_id, query=queries, providers=row["active_providers"], raw=row["raw_count"], accepted=row["accepted_count"], zero_reason=zero_reason, errors=errors)
        result["cache_reused_chunks"] = reused; result["retried_chunks"] = retried
        result["duplicates_rejected"] = duplicate_count
        from .media_quality import cross_chunk_duplicate_rate
        result["cross_chunk_duplicate_rate"] = cross_chunk_duplicate_rate([row["candidates"] for row in result["chunks"].values()])
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
    real_runtime = model_factory is None
    if real_runtime:
        from faster_whisper import WhisperModel

        model_factory = WhisperModel
    try:
        if real_runtime and os.name == "nt":
            import ctypes
            ctypes.WinDLL("cublas64_12.dll")
        model = model_factory(
            model_size_or_path=model_name,
            device="cuda",
            compute_type="float16",
            download_root=str(cache_dir),
        )
        mode = "cuda/float16"
        if real_runtime:
            import numpy as np
            preflight_segments, _ = model.transcribe(np.zeros(16000,dtype=np.float32),language='it',vad_filter=False)
            list(preflight_segments)
            _event('asr',1,'ASR CUDA preflight passed',mode=mode,runtime=sys.executable)
        segments, info = model.transcribe(
            str(video), language="it", word_timestamps=True, vad_filter=True
        )
        rows = _consume_segments(segments, info, timeline_fps, progress_callback)
    except Exception as exc:
        if real_runtime:
            _event('asr',1,'CUDA ASR unavailable; using CPU',mode='cpu/int8',reason=type(exc).__name__,runtime=sys.executable)
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
    transcript: dict[str, Any], *, max_chunk_seconds: float = 8.0
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build deterministic idea-first chunks with timing as a safety bound.

    Sentence endings, audible pauses, and discourse turns win over a fixed time
    window. Commas are remembered as safe fallback boundaries, while subordinate
    connectors stay attached to the clause that follows them.
    """
    words = [
        dict(word)
        for segment in transcript.get("segments", [])
        for word in segment.get("words", [])
    ]
    word_groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    soft_break: int | None = None
    preferred_seconds = min(5.0, max_chunk_seconds)
    discourse_starters = {"ma", "però", "pero", "invece", "quindi", "mentre", "tuttavia"}
    subordinate_starters = {"che", "perché", "perche", "se", "quando", "anche"}

    def flush(count: int | None = None) -> None:
        nonlocal current, soft_break
        count = len(current) if count is None else count
        if count:
            word_groups.append(current[:count])
            current = current[count:]
        soft_break = next(
            (index for index, item in reversed(list(enumerate(current, 1)))
             if str(item.get("text", "")).rstrip().endswith((",", ":"))),
            None,
        )

    for word in words:
        token = str(word.get("text", "")).strip()
        normalized = token.casefold().strip(".,;:!?")
        gap = float(word["start"]) - float(current[-1]["end"]) if current else 0.0
        if current and gap >= 0.55 and float(current[-1]["end"]) - float(current[0]["start"]) >= 1.1:
            flush()
        if current and normalized in discourse_starters and len(current) >= 3:
            flush()

        prospective_duration = float(word["end"]) - float(current[0]["start"]) if current else 0.0
        if current and prospective_duration > max_chunk_seconds:
            fallback_breaks = [
                index for index, item in enumerate(current, 1)
                if index >= 3
                and len(current) - index >= 3
                and str(item.get("text", "")).rstrip().endswith((",", ":"))
            ]
            split_at = fallback_breaks[-1] if fallback_breaks else (soft_break if soft_break and soft_break >= 3 else len(current))
            while split_at > 3 and str(current[split_at - 1].get("text", "")).casefold().strip(".,;:!?") in subordinate_starters:
                split_at -= 1
            flush(split_at)
        current.append(word)
        if token.endswith((",", ":")):
            soft_break = len(current)
        if token.endswith((".", "!", "?", ";")):
            flush()
        elif (
            soft_break
            and soft_break >= 3
            and len(current) - soft_break >= 3
            and float(current[-1]["end"]) - float(current[0]["start"]) >= preferred_seconds
        ):
            flush(soft_break)
    if current:
        flush()

    # Absorb accidental micro-fragments, while retaining concise complete
    # sentences (for example, "Poi cambia tutto.") as intentional punchlines.
    merged: list[list[dict[str, Any]]] = []
    for group in word_groups:
        duration = float(group[-1]["end"]) - float(group[0]["start"])
        complete_punchline = len(group) >= 3 and str(group[-1].get("text", "")).endswith((".", "!", "?"))
        if merged and (len(group) < 3 or duration < 1.1) and not complete_punchline:
            combined_duration = float(group[-1]["end"]) - float(merged[-1][0]["start"])
            if combined_duration <= max_chunk_seconds:
                merged[-1].extend(group)
                continue
        merged.append(group)
    chunks = [_chunk(group, index) for index, group in enumerate(merged)]

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
    stop = {
        "il", "lo", "la", "i", "gli", "le", "un", "una", "e", "di", "a", "da", "in", "con", "su", "per", "che", "si", "sono",
        "io", "noi", "voi", "mi", "me", "ci", "vi", "ne", "dei", "se", "ma", "però", "pero", "quindi", "forse", "pure", "anche",
        "avevo", "abbiamo", "ho", "ha", "hanno", "era", "è", "essere", "trovato", "sembrava", "perfetto", "esempio", "oggi", "ciao", "spiego",
        "perché", "perche", "non", "vendiamo", "possiamo", "chiamarlo", "sempre", "niente", "spettacoli", "cavalcate", "significa", "esattamente", "questo",
    }
    tokens = [token.strip(".,;:!?()\"") for token in text.split()]
    concrete = [token for token in tokens if token and token != "'" and token.casefold() not in stop]
    literal = " ".join(concrete[:6])
    context = " ".join(concrete[-5:])
    named = " ".join(
        token for index, token in enumerate(tokens)
        if token and token[0].isupper() and index > 0 and token.casefold() not in stop
    )
    return list(dict.fromkeys(query for query in (named, context, literal) if len(query.split()) >= 2))[:3]


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
        "--outline", str(outline_path), "--chunks", str(output / "semantic-chunks.json"), "--output-dir", str(output), "--client-id", client_id,
        "--source-frames", str(source_frames), "--model-root", str(DEFAULT_MODEL_ROOT),
        "--embedding-code-root", str(DEFAULT_EMBEDDING_CODE),
    ]


def _image_sourcing_command(output: Path, chunks_path: Path, outline_path: Path, client_id: str) -> list[str]:
    return [
        str(DEFAULT_PIPELINE_PYTHON if DEFAULT_PIPELINE_PYTHON.is_file() else Path(sys.executable)),
        "-m", "backend.app.image_sourcing_cli", "--chunks", str(chunks_path),
        "--outline", str(outline_path), "--output-dir", str(output), "--client-id", client_id,
        "--model-root", str(DEFAULT_MODEL_ROOT), "--embedding-code-root", str(DEFAULT_EMBEDDING_CODE),
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
    parser.add_argument("--client-id", default="debug-reel")
    args = parser.parse_args()

    from .project_lock import project_stage_lock
    with project_stage_lock(args.output_dir.resolve()):
        _run_stages(args)


def _run_stages(args):
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
        from .editorial_import import retrieval_bundle
        retrieval_output, chunks, _, _ = retrieval_bundle(output)
        if args.stage == "images":
            _event("image_search", 1, "Image sourcing avviato", items=len(chunks))
            subprocess.run(_image_sourcing_command(output, chunks_path, outline_path, args.client_id), check=True)
            images = json.loads((retrieval_output / "image-candidates.json").read_text(encoding="utf-8"))
            _write_json(output / "image-sourcing.json", {"status": "complete", "chunks": len(chunks)})
            _event("image_search", 100, "Image sourcing completato", chunks=len(images.get("chunks", {})))
            return
        _event("online_search", 1, "Video sourcing avviato", items=len(chunks))
        subprocess.run(_video_sourcing_command(output, transcript_path, outline_path, args.client_id, source_frames), check=True)
        persist_video_diagnostics(retrieval_output)
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

    subprocess.run(_image_sourcing_command(output, chunks_path, outline_path, args.client_id), check=True)
    images = json.loads((retrieval_output / "image-candidates.json").read_text(encoding="utf-8"))
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
