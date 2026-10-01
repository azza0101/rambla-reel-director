from pathlib import Path


def test_one_click_installer_covers_app_and_resolve_bridge():
    cmd = Path("INSTALL_RMBL_B_ROLL.cmd").read_text(encoding="utf-8")
    script = Path("INSTALL_RMBL_B_ROLL.ps1").read_text(encoding="utf-8")
    assert "ExecutionPolicy Bypass" in cmd
    assert "INSTALL_RESOLVE_BRIDGE.ps1" in script
    assert "RMBL B ROLL.lnk" in script
    assert "RMBL_B_ROLL_APP.vbs" in script


def test_standalone_launcher_never_starts_the_resolve_bridge():
    launcher = Path("RMBL_B_ROLL_APP.vbs").read_text(encoding="utf-8")
    assert "launch_local_v5.py" in launcher
    assert "RAMBLA_B_ROLL.py" not in launcher
    assert "resolve_bridge" not in launcher


def test_distribution_builder_has_an_explicit_safe_payload():
    source = Path("BUILD_WINDOWS_PACKAGE.ps1").read_text(encoding="utf-8")
    assert "backend" in source and "tools" in source and "tests" not in source
    assert "Compress-Archive" in source
    assert "rambla-data" not in source
