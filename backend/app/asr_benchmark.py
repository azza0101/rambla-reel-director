"""Offline ASR comparison for Resolve exports and RAMBLA/local transcripts.

The benchmark is deliberately Resolve-independent: Resolve is treated as an
artifact producer (for example an exported SRT), so running this module never
connects to or mutates a Resolve project.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True, slots=True)
class TranscriptArtifact:
    provider: str
    language: str
    source_duration_seconds: float
    segments: tuple[TranscriptSegment, ...]
    elapsed_seconds: float | None = None

    @property
    def text(self) -> str:
        return " ".join(segment.text for segment in self.segments).strip()

    @property
    def realtime_factor(self) -> float | None:
        if self.elapsed_seconds is None:
            return None
        return self.elapsed_seconds / self.source_duration_seconds


def _clean_display_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _words(text: str) -> list[str]:
    return re.findall(r"[\wÀ-ÿ]+", text.casefold(), flags=re.UNICODE)


def _chars(text: str) -> list[str]:
    return list("".join(_words(text)))


def _levenshtein(reference: list[str], hypothesis: list[str]) -> int:
    if not reference:
        return len(hypothesis)
    if not hypothesis:
        return len(reference)
    previous = list(range(len(hypothesis) + 1))
    for row_index, ref_item in enumerate(reference, start=1):
        current = [row_index]
        for col_index, hyp_item in enumerate(hypothesis, start=1):
            substitution = previous[col_index - 1] + (ref_item != hyp_item)
            insertion = current[col_index - 1] + 1
            deletion = previous[col_index] + 1
            current.append(min(substitution, insertion, deletion))
        previous = current
    return previous[-1]


def _error_rate(reference: list[str], hypothesis: list[str]) -> float:
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return _levenshtein(reference, hypothesis) / len(reference)


def normalize_transcript_artifact(
    artifact: dict[str, Any],
    *,
    provider: str,
    source_duration_seconds: float | None = None,
    elapsed_seconds: float | None = None,
) -> TranscriptArtifact:
    if not provider.strip():
        raise ValueError("provider is required")
    rows = artifact.get("segments")
    if not isinstance(rows, list) or not rows:
        raise ValueError("transcript segments are required")

    segments: list[TranscriptSegment] = []
    previous_end = 0.0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("transcript segment must be an object")
        start = float(row.get("start", row.get("start_seconds", -1.0)))
        end = float(row.get("end", row.get("end_seconds", -1.0)))
        text = _clean_display_text(row.get("text"))
        if start < 0 or end <= start or not text:
            raise ValueError("transcript segment has invalid timing/text")
        if segments and start < previous_end:
            raise ValueError("transcript segments must be ordered and non-overlapping")
        segments.append(TranscriptSegment(start=start, end=end, text=text))
        previous_end = end

    declared_duration = source_duration_seconds
    if declared_duration is None:
        declared_duration = artifact.get("source_duration_seconds") or artifact.get("duration_seconds")
    duration = max(float(declared_duration or 0.0), segments[-1].end)
    if duration <= 0:
        raise ValueError("source duration must be positive")

    measured = elapsed_seconds
    if measured is None and artifact.get("elapsed_seconds") is not None:
        measured = float(artifact["elapsed_seconds"])
    if measured is not None and measured < 0:
        raise ValueError("elapsed_seconds cannot be negative")

    return TranscriptArtifact(
        provider=provider.strip(),
        language=str(artifact.get("language") or "und"),
        source_duration_seconds=duration,
        segments=tuple(segments),
        elapsed_seconds=measured,
    )


def _parse_srt_timestamp(value: str) -> float:
    match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})", value.strip())
    if not match:
        raise ValueError(f"invalid SRT timestamp: {value}")
    hours, minutes, seconds, millis = (int(part) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds + millis / 1000.0


def parse_srt(text: str, *, provider: str = "resolve", elapsed_seconds: float | None = None) -> TranscriptArtifact:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise ValueError("SRT content is empty")
    segments: list[dict[str, Any]] = []
    for block in re.split(r"\n\s*\n", normalized):
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        timing_index = next((index for index, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            raise ValueError("SRT block is missing timing")
        timing = lines[timing_index].split("-->", 1)
        if len(timing) != 2:
            raise ValueError("invalid SRT timing line")
        subtitle_text = _clean_display_text(" ".join(lines[timing_index + 1 :]))
        if not subtitle_text:
            raise ValueError("SRT block is missing subtitle text")
        segments.append(
            {
                "start": _parse_srt_timestamp(timing[0]),
                "end": _parse_srt_timestamp(timing[1]),
                "text": subtitle_text,
            }
        )
    return normalize_transcript_artifact(
        {"language": "und", "segments": segments},
        provider=provider,
        elapsed_seconds=elapsed_seconds,
    )


def _token_overlap(left: str, right: str) -> float:
    left_words, right_words = set(_words(left)), set(_words(right))
    union = left_words | right_words
    return len(left_words & right_words) / len(union) if union else 0.0


def _timing_metrics(reference: TranscriptArtifact, candidate: TranscriptArtifact) -> tuple[float | None, int]:
    unused = set(range(len(candidate.segments)))
    boundary_errors: list[float] = []
    matched = 0
    for ref in reference.segments:
        choices = sorted(
            ((-_token_overlap(ref.text, candidate.segments[index].text), index) for index in unused),
            key=lambda item: (item[0], item[1]),
        )
        if not choices:
            break
        negative_score, best_index = choices[0]
        if -negative_score <= 0:
            continue
        hyp = candidate.segments[best_index]
        unused.remove(best_index)
        boundary_errors.extend((abs(ref.start - hyp.start), abs(ref.end - hyp.end)))
        matched += 1
    if not boundary_errors:
        return None, matched
    return sum(boundary_errors) * 1000.0 / len(boundary_errors), matched


def _speed_winner(candidates: list[TranscriptArtifact]) -> str | None:
    timed = [candidate for candidate in candidates if candidate.realtime_factor is not None]
    if not timed:
        return None
    return min(timed, key=lambda item: (float(item.realtime_factor), item.provider)).provider


def compare_transcripts(
    *,
    reference: TranscriptArtifact | None,
    candidates: list[TranscriptArtifact],
) -> dict[str, Any]:
    if len(candidates) < 2:
        raise ValueError("at least two ASR candidates are required")
    providers = [candidate.provider for candidate in candidates]
    if len(set(providers)) != len(providers):
        raise ValueError("candidate provider names must be unique")

    results: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        row: dict[str, Any] = {
            "segment_count": len(candidate.segments),
            "word_count": len(_words(candidate.text)),
            "elapsed_seconds": candidate.elapsed_seconds,
            "realtime_factor": candidate.realtime_factor,
            "wer": None,
            "cer": None,
            "mean_boundary_error_ms": None,
            "matched_segments": None,
        }
        if reference is not None:
            row["wer"] = _error_rate(_words(reference.text), _words(candidate.text))
            row["cer"] = _error_rate(_chars(reference.text), _chars(candidate.text))
            timing_error, matched = _timing_metrics(reference, candidate)
            row["mean_boundary_error_ms"] = timing_error
            row["matched_segments"] = matched
        results[candidate.provider] = row

    accuracy_winner = None
    timing_winner = None
    if reference is not None:
        accuracy_winner = min(
            candidates,
            key=lambda item: (
                float(results[item.provider]["wer"]),
                float(results[item.provider]["cer"]),
                item.provider,
            ),
        ).provider
        timed = [
            candidate
            for candidate in candidates
            if results[candidate.provider]["mean_boundary_error_ms"] is not None
        ]
        if timed:
            timing_winner = min(
                timed,
                key=lambda item: (
                    float(results[item.provider]["mean_boundary_error_ms"]),
                    item.provider,
                ),
            ).provider

    pairwise = {
        "providers": [candidates[0].provider, candidates[1].provider],
        "word_disagreement_rate": _error_rate(_words(candidates[0].text), _words(candidates[1].text)),
        "char_disagreement_rate": _error_rate(_chars(candidates[0].text), _chars(candidates[1].text)),
    }
    return {
        "schema_version": "asr-benchmark-1",
        "mode": "REFERENCE_SCORED" if reference is not None else "COMPARATIVE_ONLY",
        "reference_provider": reference.provider if reference is not None else None,
        "providers": results,
        "pairwise": pairwise,
        "winner": {
            "accuracy": accuracy_winner,
            "timing": timing_winner,
            "speed": _speed_winner(candidates),
        },
    }
