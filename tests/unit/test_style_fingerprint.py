from backend.app.style_fingerprint import VisualInterval, build_style_fingerprint


def test_fingerprint_aggregates_separate_reference_timing_and_layout():
    fingerprint = build_style_fingerprint(
        exemplar_id="factanza-fixture", duration_seconds=20.0,
        intervals=[
            VisualInterval(0.0, 4.0, "TALKING_HEAD", "FULL_FRAME"),
            VisualInterval(4.0, 7.5, "RECEIPT", "SPEAKER_PLUS_EVIDENCE_TOP"),
            VisualInterval(7.5, 10.0, "TALKING_HEAD", "FULL_FRAME"),
            VisualInterval(10.0, 14.0, "ARCHIVAL", "FULL_FRAME_CUTAWAY"),
            VisualInterval(14.0, 20.0, "TALKING_HEAD", "FULL_FRAME"),
        ],
    )
    assert fingerprint.insert_count == 2
    assert fingerprint.speaker_return_count == 2
    assert fingerprint.median_insert_seconds == 3.75
    assert fingerprint.route_mix["RECEIPT"] > 0
    assert fingerprint.presentation_mix["SPEAKER_PLUS_EVIDENCE_TOP"] > 0
    assert fingerprint.to_reference_style_profile().id == "factanza-fixture"


def test_fingerprint_rejects_gaps_or_overlap():
    import pytest

    with pytest.raises(ValueError, match="contiguous"):
        build_style_fingerprint(
            exemplar_id="bad", duration_seconds=10.0,
            intervals=[VisualInterval(0, 4, "TALKING_HEAD", "FULL_FRAME"),
                       VisualInterval(5, 10, "RECEIPT", "DOCUMENT_CARD")],
        )


def test_unclassified_frames_cannot_be_promoted_to_active_style():
    import pytest

    fingerprint = build_style_fingerprint(
        exemplar_id="unclassified", duration_seconds=3,
        intervals=[VisualInterval(0, 3, "UNCLASSIFIED", "UNCLASSIFIED", classification_confidence=0)],
    )
    with pytest.raises(ValueError, match="unclassified"):
        fingerprint.to_reference_style_profile()


def test_cli_adapter_uses_injected_commands_and_writes_separate_output(tmp_path):
    from subprocess import CompletedProcess
    from backend.app.style_fingerprint_cli import analyze_reference

    media = tmp_path / "reference.mp4"
    media.write_bytes(b"fixture")
    commands = []

    def runner(command):
        commands.append(command)
        if command[0] == "ffprobe":
            return CompletedProcess(command, 0, '{"format":{"duration":"8"}}', "")
        if command[-1] == "-":
            return CompletedProcess(command, 0, "", "pts_time:4.0")
        if command[-1].endswith(".jpg"):
            from pathlib import Path
            Path(command[-1]).write_bytes(b"frame")
        return CompletedProcess(command, 0, "", "")

    def classifier(frame, start, end):
        return {"route": "TALKING_HEAD" if start == 0 else "RECEIPT",
                "presentation": "FULL_FRAME" if start == 0 else "DOCUMENT_CARD",
                "confidence": 0.9}

    payload = analyze_reference(media, tmp_path / "factanza", exemplar_id="factanza_evidence_editorial",
                                runner=runner, classifier=classifier)
    assert payload["id"] == "factanza_evidence_editorial"
    assert payload["insert_count"] == 1
    assert (tmp_path / "factanza" / "style-fingerprint.json").is_file()
    assert (tmp_path / "factanza" / "representative-frames.json").is_file()
    assert len(commands) == 4
