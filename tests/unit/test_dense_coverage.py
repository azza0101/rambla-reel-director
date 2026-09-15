from pathlib import Path


def test_visual_coverage_ratio_counts_broll_and_continuation_only():
    from backend.app.editorial_import import visual_coverage_ratio

    plan = {
        "visual_beats": [
            {"start": 0.0, "end": 5.0, "action": "BROLL"},
            {"start": 5.0, "end": 7.0, "action": "KEEP_TALKING_HEAD"},
            {"start": 7.0, "end": 10.0, "action": "CONTINUE_PREVIOUS_VISUAL"},
        ]
    }
    assert visual_coverage_ratio(plan) == 0.8


def test_editorial_input_requests_dense_visual_coverage():
    from backend.app.editorial_import import INSTRUCTIONS

    text = INSTRUCTIONS.casefold()
    assert "90" in text and "98" in text
    assert "continue_previous_visual" in text
    assert "keep_talking_head" in text


def test_acceptance_launcher_uses_stable_origin_for_project_restore():
    text = Path("tools/start_curation_acceptance.ps1").read_text(encoding="utf-8")
    assert "$port = 8765" in text
    assert "8765..8799" not in text
    assert ".curation-acceptance-server.json" in text
