"""Cloud-only analysis worker: Groq speech-to-text or direct transcript text.

This worker deliberately loads no local ML model. FFmpeg is used only for CPU media
normalization; transcription is performed by the configured cloud API.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any

import httpx

from .atomic_io import write_json
from .debug_run_cli import build_short_outline, _event


GROQ_TRANSCRIPTIONS_ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"
DEFAULT_GROQ_ASR_MODEL = "whisper-large-v3-turbo"


def _source_input(output: Path) -> dict[str, Any]:
    path = output.parent / "source" / "source-input.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {"kind": "video"}
    return value if isinstance(value, dict) else {"kind": "video"}


def _split_text(text: str) -> list[str]:
    clean = " ".join(str(text or "").split())
    if not clean:
        return []
    rows = [row.strip() for row in re.split(r"(?<=[.!?;:])\s+", clean) if row.strip()]
    return rows or [clean]


def transcript_from_text(text: str, *, fps: int = 25, words_per_second: float = 2.5) -> dict[str, Any]:
    rows = _split_text(text)
    if not rows:
        raise ValueError("transcript text is empty")
    cursor = 0.0
    segments: list[dict[str, Any]] = []
    for sentence in rows:
        tokens = sentence.split()
        words: list[dict[str, Any]] = []
        for token in tokens:
            start = cursor
            cursor += 1.0 / words_per_second
            words.append({"start": round(start, 4), "end": round(cursor, 4), "text": token})
        if not words:
            continue
        segments.append({
            "start": words[0]["start"],
            "end": words[-1]["end"],
            "text": " ".join(token["text"] for token in words),
            "words": words,
        })
    return {
        "provider": "direct-text",
        "language": None,
        "timeline_fps": int(fps),
        "segments": segments,
        "text": " ".join(row["text"] for row in segments),
        "source_duration_seconds": round(cursor, 4),
        "timing_basis": "synthetic_text_timing",
    }


def _segment_words(segment: dict[str, Any]) -> list[dict[str, Any]]:
    raw = segment.get("words")
    if isinstance(raw, list) and raw:
        output = []
        for row in raw:
            if not isinstance(row, dict):
                continue
            text = str(row.get("word") or row.get("text") or "").strip()
            if not text:
                continue
            try:
                start, end = float(row["start"]), float(row["end"])
            except (KeyError, TypeError, ValueError):
                continue
            if end < start:
                continue
            output.append({"start": start, "end": end, "text": text})
        if output:
            return output
    text = str(segment.get("text") or "").strip()
    tokens = text.split()
    if not tokens:
        return []
    start = float(segment.get("start") or 0.0)
    end = float(segment.get("end") or start + max(0.4, len(tokens) * 0.4))
    step = max(0.02, (end - start) / len(tokens))
    return [
        {"start": round(start + index * step, 4), "end": round(start + (index + 1) * step, 4), "text": token}
        for index, token in enumerate(tokens)
    ]


def _normalize_groq(payload: dict[str, Any], *, fps: int = 25) -> dict[str, Any]:
    raw_segments = [s for s in (payload.get("segments") or []) if isinstance(s, dict)]
    segments: list[dict[str, Any]] = []
    # verbose_json returns word timestamps at the top level, not nested in
    # segments. Never replace measured word times with equal subdivisions.
    measured = _segment_words({'words': payload['words']}) if payload.get('words') else []
    if measured:
        for index, word in enumerate(measured):
            if index:
                word['start'] = max(word['start'], measured[index-1]['start'] + 1 / fps)
            word['end'] = max(word['end'], word['start'] + 1 / fps)
        for previous, current in zip(measured, measured[1:]):
            previous['end'] = min(previous['end'], current['start'])
        remaining = list(measured)
        for raw in raw_segments or []:
            end = float(raw.get('end') or 0)
            words = [w for w in remaining if float(w['start']) < end]
            remaining = [w for w in remaining if float(w['start']) >= end]
            if words:
                segments.append({'start': words[0]['start'], 'end': words[-1]['end'],
                                 'text': ' '.join(w['text'] for w in words), 'words': words})
        if remaining:
            segments.append({'start': remaining[0]['start'], 'end': remaining[-1]['end'],
                             'text': ' '.join(w['text'] for w in remaining), 'words': remaining})
    elif isinstance(raw_segments, list):
        for raw in raw_segments:
            if not isinstance(raw, dict):
                continue
            words = _segment_words(raw)
            if not words:
                continue
            segments.append({
                "start": float(words[0]["start"]),
                "end": float(words[-1]["end"]),
                "text": " ".join(str(word["text"]).strip() for word in words).strip(),
                "words": words,
            })
    if not segments:
        text = str(payload.get("text") or "").strip()
        if not text:
            raise RuntimeError("Groq returned an empty transcript")
        return transcript_from_text(text, fps=fps)
    duration = max(float(row["end"]) for row in segments)
    return {
        "provider": "groq",
        "model": str(payload.get("model") or os.environ.get("RAMBLA_CLOUD_ASR_MODEL", DEFAULT_GROQ_ASR_MODEL)),
        "language": payload.get("language"),
        "timeline_fps": int(fps),
        "segments": segments,
        "text": " ".join(row["text"] for row in segments),
        "source_duration_seconds": float(payload.get('duration') or duration),
        "timing_basis": "cloud_asr_word_timestamps" if measured or (raw_segments and all(s.get('words') for s in raw_segments)) else "estimated_segment_word_timing",
    }


def _compressed_audio(source: Path, output: Path) -> Path:
    target = output / "cloud-asr-input.flac"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(source),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "flac", str(target),
    ], check=True, capture_output=True)
    return target


def _groq_asr_form(model: str, *, language: str = "") -> dict[str, str | list[str]]:
    form: dict[str, str | list[str]] = {
        "model": model,
        "response_format": "verbose_json",
        "temperature": "0",
        "timestamp_granularities[]": ["word", "segment"],
    }
    if language:
        form["language"] = language
    return form


def _analysis_provenance(video: Path, guide_audio: Path | None) -> dict[str, Any]:
    from .debug_run_cli import analysis_input_signature

    return analysis_input_signature(video, guide_audio or video)


def transcribe_groq(source: Path, output: Path) -> dict[str, Any]:
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required for cloud audio/video transcription")
    audio = _compressed_audio(source, output)
    if audio.stat().st_size > 95 * 1024 * 1024:
        raise RuntimeError("Audio exceeds the 100 MB Groq transcription limit after compression; split the source first")
    model = os.environ.get("RAMBLA_CLOUD_ASR_MODEL", DEFAULT_GROQ_ASR_MODEL).strip() or DEFAULT_GROQ_ASR_MODEL
    language = os.environ.get("RAMBLA_ASR_LANGUAGE", "").strip()
    data = _groq_asr_form(model, language=language)
    started = time.perf_counter()
    with audio.open("rb") as handle:
        files = {"file": (audio.name, handle, "audio/flac")}
        with httpx.Client(timeout=httpx.Timeout(180.0, connect=20.0, write=60.0)) as client:
            from .magic_usage import invoke_http
            response = invoke_http('groq_asr', {'model':model, 'source':str(source.resolve()),
                'size':source.stat().st_size, 'mtime_ns':source.stat().st_mtime_ns, 'data':data}, lambda: client.post(
                GROQ_TRANSCRIPTIONS_ENDPOINT,
                headers={"Authorization": f"Bearer {api_key}"},
                data=data,
                files=files,
            ))
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            body = response.json()
            detail = str((body.get("error") or {}).get("message") or "")[:300]
        except Exception:
            pass
        raise RuntimeError(f"Groq ASR failed ({response.status_code})" + (f": {detail}" if detail else "")) from exc
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Groq ASR returned an invalid response")
    transcript = _normalize_groq(payload)
    transcript["elapsed_seconds"] = round(time.perf_counter() - started, 4)
    return transcript


def run_cloud_analysis(
    *,
    video: Path,
    output: Path,
    guide_audio: Path | None,
    analysis_signature: str,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    source = _source_input(output)
    kind = str(source.get("kind") or "video").casefold()
    _event("prepare", 100, "Cloud input ready", source_kind=kind, local_gpu=False)
    if kind == "text":
        text_path = Path(str(source.get("text_path") or (output.parent / "source" / "source-text.txt")))
        text = text_path.read_text(encoding="utf-8")
        _event("asr", 5, "Using supplied transcript text", provider="direct-text", local_gpu=False)
        transcript = transcript_from_text(text)
    else:
        audio_source = (guide_audio or video).resolve()
        if not audio_source.is_file():
            raise FileNotFoundError(audio_source)
        _event("asr", 5, "Cloud transcription started", provider="groq", local_gpu=False)
        transcript = transcribe_groq(audio_source, output)
    transcript["source"] = str(video.resolve())
    transcript_path = output / "transcript-raw.json"
    write_json(transcript_path, transcript)
    _event(
        "asr", 100, "Transcript ready",
        provider=transcript.get("provider"),
        segments=len(transcript.get("segments") or []),
        words=sum(len(row.get("words") or []) for row in transcript.get("segments") or []),
        local_gpu=False,
    )
    outline, chunks = build_short_outline(transcript)
    write_json(output / "semantic-beats.json", outline)
    write_json(output / "semantic-chunks.json", chunks)
    write_json(output / "run-input.json", _analysis_provenance(video, guide_audio))
    write_json(output / "analysis-signature.json", {"analysis_signature": analysis_signature})
    _event("semantic_chunking", 100, "Semantic chunks ready", chunks=len(chunks))
    _event("analysis", 100, "Cloud analysis complete", chunks=len(chunks), local_gpu=False)
    return {"chunks": len(chunks), "provider": transcript.get("provider"), "local_gpu": False}


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze RAMBLA source without local ML/GPU")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--guide-audio", type=Path)
    parser.add_argument("--analysis-signature", default="")
    parser.add_argument("--stage", default="analyze")
    args = parser.parse_args()
    if args.stage != "analyze":
        raise SystemExit("cloud_analyze_cli supports analyze only")
    run_cloud_analysis(
        video=args.video.resolve(),
        output=args.output_dir.resolve(),
        guide_audio=args.guide_audio.resolve() if args.guide_audio else None,
        analysis_signature=args.analysis_signature,
    )


if __name__ == "__main__":
    main()
