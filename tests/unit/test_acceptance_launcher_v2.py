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


def test_playwright_bootstrap_treats_failed_import_as_exit_code_not_powershell_error():
    script = Path("tools/start_curation_acceptance.ps1").read_text(encoding="utf-8")

    # Windows PowerShell with ErrorActionPreference=Stop can promote native stderr
    # into a terminating NativeCommandError. The dependency probe must therefore
    # use Start-Process and inspect ExitCode instead of invoking python directly.
    assert "$playwrightProbe = Start-Process" in script
    assert "$playwrightProbe.ExitCode" in script
    assert '& $runtime -c "import playwright"' not in script
