from pathlib import Path


def test_acceptance_launcher_refuses_non_v2_curation_page():
    script = Path("tools/start_curation_acceptance.ps1").read_text(encoding="utf-8")

    assert "$requiredUiMarkers" in script
    for marker in (
        'id="projectsV2"',
        'id="tiktokLoginV2"',
        'id="instagramLoginV2"',
        'id="beatActionsV2"',
        'id="webNewsVideosV2"',
    ):
        assert marker in script
    assert "UI V2 verification failed" in script


def test_acceptance_launcher_pins_python_imports_to_downloaded_build():
    script = Path("tools/start_curation_acceptance.ps1").read_text(encoding="utf-8")

    assert "$env:PYTHONPATH = $workRoot" in script
    assert "'--app-dir',$workRoot" in script or "'--app-dir', $workRoot" in script
    assert "backend.app.curation_server" in script
    assert "Import provenance verification failed" in script


def test_backend_is_regular_package_so_old_launcher_cannot_merge_with_installed_copy():
    marker = Path("backend/__init__.py")
    assert marker.is_file(), "backend must be a regular package in downloaded acceptance builds"


def test_launcher_self_refreshes_from_remote_branch_before_starting_server():
    script = Path("tools/start_curation_acceptance.ps1").read_text(encoding="utf-8")

    assert "RAMBLA_LAUNCHER_REFRESHED" in script
    assert "application/vnd.github.raw+json" in script
    assert "tools/start_curation_acceptance.ps1?ref=$branch" in script
    assert "WriteAllText" in script
    assert "powershell.exe" in script


def test_launcher_does_not_require_playwright_or_pip_before_serving_curation():
    script = Path("tools/start_curation_acceptance.ps1").read_text(encoding="utf-8")

    # Browser automation is optional at server startup. The curation UI must be
    # able to start even when the scoped ASR venv intentionally has no pip and
    # no Playwright package yet.
    assert 'import playwright' not in script
    assert "pip install 'playwright" not in script
    assert 'No module named pip' not in script
