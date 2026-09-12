from __future__ import annotations

import pytest

from backend.app.asr_benchmark import (
    compare_transcripts,
    normalize_transcript_artifact,
    parse_srt,
)


def _artifact(provider: str, text: str, *, elapsed: float | None = None, offset: float = 0.0) -> dict:
    row = {
        "provider": provider,
        "language": "it",
        "source_duration_seconds": 4.0,
        "segments": [
            {"start": 0.0 + offset, "end": 1.8 + offset, "text": text.split(" | ")[0]},
            {"start": 2.0 + offset, "end": 4.0 + offset, "text": text.split(" | ")[1]},
        ],
    }
    if elapsed is not None:
        row["elapsed_seconds"] = elapsed
    return row


def test_normalize_transcript_artifact_accepts_existing_rambla_shape() -> None:
    artifact = {
        "source": "clip.mp4",
        "language": "it",
        "timeline_fps": 24,
        "segments": [
            {"start": 0.0, "end": 1.0, "text": " Ciao   mondo "},
            {"start": 1.0, "end": 2.0, "text": "come stai?"},
        ],
    }

    normalized = normalize_transcript_artifact(artifact, provider="rambla-local", source_duration_seconds=2.0, elapsed_seconds=0.5)

    assert normalized.provider == "rambla-local"
    assert normalized.text == "Ciao mondo come stai?"
    assert normalized.source_duration_seconds == 2.0
    assert normalized.elapsed_seconds == 0.5
    assert normalized.realtime_factor == pytest.approx(0.25)


def test_parse_srt_normalizes_resolve_export_without_mutating_resolve() -> None:
    srt = """1\n00:00:00,000 --> 00:00:01,500\nCiao mondo\n\n2\n00:00:02,000 --> 00:00:04,000\nQuesta è una prova.\n"""

    normalized = parse_srt(srt, provider="resolve", elapsed_seconds=1.2)

    assert normalized.provider == "resolve"
    assert normalized.source_duration_seconds == 4.0
    assert [row.text for row in normalized.segments] == ["Ciao mondo", "Questa è una prova."]
    assert normalized.realtime_factor == pytest.approx(0.3)


def test_compare_transcripts_uses_reference_for_accuracy_timing_and_speed() -> None:
    reference = normalize_transcript_artifact(
        _artifact("human", "ciao mondo | questa è una prova"),
        provider="human",
    )
    local = normalize_transcript_artifact(
        _artifact("rambla-local", "ciao mondo | questa è una prova", elapsed=0.8, offset=0.05),
        provider="rambla-local",
    )
    resolve = normalize_transcript_artifact(
        _artifact("resolve", "ciao mondo | questa era una prova", elapsed=0.4, offset=0.20),
        provider="resolve",
    )

    report = compare_transcripts(reference=reference, candidates=[local, resolve])

    assert report["mode"] == "REFERENCE_SCORED"
    assert report["winner"]["accuracy"] == "rambla-local"
    assert report["winner"]["speed"] == "resolve"
    assert report["providers"]["rambla-local"]["wer"] == 0.0
    assert report["providers"]["resolve"]["wer"] > 0.0
    assert report["providers"]["rambla-local"]["mean_boundary_error_ms"] < report["providers"]["resolve"]["mean_boundary_error_ms"]


def test_compare_transcripts_without_reference_is_explicitly_comparative_only() -> None:
    local = normalize_transcript_artifact(
        _artifact("rambla-local", "ciao mondo | questa è una prova", elapsed=0.8),
        provider="rambla-local",
    )
    resolve = normalize_transcript_artifact(
        _artifact("resolve", "ciao mondo | questa era una prova", elapsed=0.4),
        provider="resolve",
    )

    report = compare_transcripts(reference=None, candidates=[local, resolve])

    assert report["mode"] == "COMPARATIVE_ONLY"
    assert report["winner"]["accuracy"] is None
    assert report["pairwise"]["word_disagreement_rate"] > 0.0
    assert report["winner"]["speed"] == "resolve"


def test_rejects_overlapping_or_out_of_order_segments() -> None:
    with pytest.raises(ValueError, match="ordered and non-overlapping"):
        normalize_transcript_artifact(
            {
                "segments": [
                    {"start": 0.0, "end": 2.0, "text": "uno"},
                    {"start": 1.5, "end": 3.0, "text": "due"},
                ]
            },
            provider="bad",
            source_duration_seconds=3.0,
        )
