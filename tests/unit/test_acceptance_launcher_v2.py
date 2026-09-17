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
