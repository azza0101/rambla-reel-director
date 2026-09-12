from __future__ import annotations

import json

from backend.app.asr_benchmark_cli import run_from_files


def test_run_from_files_compares_resolve_srt_and_rambla_json_against_reference(tmp_path) -> None:
    local_path = tmp_path / "rambla.json"
    local_path.write_text(
        json.dumps(
            {
                "language": "it",
                "segments": [
                    {"start": 0.05, "end": 1.55, "text": "Ciao mondo"},
                    {"start": 2.05, "end": 4.0, "text": "Questa è una prova"},
                ],
            }
        ),
        encoding="utf-8",
    )
    resolve_path = tmp_path / "resolve.srt"
    resolve_path.write_text(
        "1\n00:00:00,200 --> 00:00:01,700\nCiao mondo\n\n2\n00:00:02,200 --> 00:00:04,000\nQuesta era una prova\n",
        encoding="utf-8",
    )
    reference_path = tmp_path / "reference.srt"
    reference_path.write_text(
        "1\n00:00:00,000 --> 00:00:01,500\nCiao mondo\n\n2\n00:00:02,000 --> 00:00:04,000\nQuesta è una prova\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "report.json"

    report = run_from_files(
        local_path=local_path,
        resolve_path=resolve_path,
        output_path=output_path,
        reference_path=reference_path,
        source_duration_seconds=4.0,
        local_elapsed_seconds=0.8,
        resolve_elapsed_seconds=0.4,
    )

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved == report
    assert report["mode"] == "REFERENCE_SCORED"
    assert report["winner"]["accuracy"] == "rambla-local"
    assert report["winner"]["timing"] == "rambla-local"
    assert report["winner"]["speed"] == "resolve"
    assert report["inputs"]["resolve_format"] == "srt"
    assert report["inputs"]["local_format"] == "json"
    assert report["resolve_calls"] == 0


def test_run_from_files_without_reference_never_claims_accuracy_winner(tmp_path) -> None:
    local_path = tmp_path / "local.json"
    local_path.write_text(
        json.dumps({"segments": [{"start": 0.0, "end": 1.0, "text": "ciao mondo"}]}),
        encoding="utf-8",
    )
    resolve_path = tmp_path / "resolve.srt"
    resolve_path.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nciao a tutti\n",
        encoding="utf-8",
    )

    report = run_from_files(
        local_path=local_path,
        resolve_path=resolve_path,
        output_path=tmp_path / "report.json",
        source_duration_seconds=1.0,
    )

    assert report["mode"] == "COMPARATIVE_ONLY"
    assert report["winner"]["accuracy"] is None
    assert report["resolve_calls"] == 0
