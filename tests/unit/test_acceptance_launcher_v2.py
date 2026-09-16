from pathlib import Path


def test_acceptance_launcher_refuses_non_v2_curation_page():
    script = Path("tools/start_curation_acceptance.ps1").read_text(encoding="utf-8")

    assert "$requiredUiMarkers" in script
    for marker in (
        "PROJECTS",
        "TIKTOK LOGIN",
        "INSTAGRAM LOGIN",
        "WEB / NEWS VIDEO",
        "NEW SEARCH",
    ):
        assert marker in script
    assert "UI V2 verification failed" in script
