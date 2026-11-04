"""Verify RMBL keeps only the latest safe local rollback snapshot."""
import json
import os
import subprocess
from pathlib import Path

import pytest


def managed_backup(root: Path, name: str, previous: str, incoming: str) -> Path:
    folder = root / "install-backups" / name
    code = folder / "code"
    code.mkdir(parents=True)
    (code / "RAMBLA_VERSION").write_text(previous + "\n", encoding="utf-8")
    (folder / "ROLLBACK_RMBL.ps1").write_text("# rollback", encoding="utf-8")
    (folder / "update.json").write_text(
        json.dumps({"previous_version": previous, "incoming_version": incoming}),
        encoding="utf-8",
    )
    return folder


@pytest.mark.skipif(os.name != "nt", reason="Runs the real Windows PowerShell cleaner")
def test_successful_install_keeps_one_rollback_snapshot_and_preserves_user_data(tmp_path):
    product = tmp_path / "RMBL B ROLL"
    app = product / "app"
    app.mkdir(parents=True)
    (app / "RAMBLA_VERSION").write_text("v0132\n", encoding="utf-8")
    old = managed_backup(product, "20261103-090000-v0130", "v0130", "v0131")
    keep = managed_backup(product, "20261104-090000-v0131", "v0131", "v0132")
    unknown = product / "install-backups" / "20261101-090000-v0129"
    unknown.mkdir()
    (unknown / "private-note.txt").write_text("keep my files")
    manually_named = product / "install-backups" / "manual-rollback"
    manually_named.mkdir()
    data = product / "rambla-data" / "projects"
    data.mkdir(parents=True)
    (data / "selected-broll.json").write_text('{"keep": true}')
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(Path("tools/prune_rmbl_backups.ps1").resolve()),
         "-InstallRoot", str(app), "-KeepBackup", str(keep)],
        capture_output=True, text=True, timeout=40,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert not old.exists()
    assert keep.is_dir()
    assert unknown.is_dir()
    assert manually_named.is_dir()
    assert (data / "selected-broll.json").is_file()
    assert "rimossi 1 backup" in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="Runs the real Windows PowerShell cleaner")
def test_backup_cleanup_aborts_if_new_installation_does_not_match(tmp_path):
    product = tmp_path / "RMBL B ROLL"
    app = product / "app"
    app.mkdir(parents=True)
    (app / "RAMBLA_VERSION").write_text("v0131")
    old = managed_backup(product, "20261103-090000-v0130", "v0130", "v0131")
    keep = managed_backup(product, "20261104-090000-v0131", "v0131", "v0132")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(Path("tools/prune_rmbl_backups.ps1").resolve()),
         "-InstallRoot", str(app), "-KeepBackup", str(keep)],
        capture_output=True, text=True, timeout=40,
    )
    assert result.returncode != 0
    assert old.is_dir()
    assert keep.is_dir()


def test_cleanup_is_limited_to_managed_backup_root_and_successful_update():
    installer = Path("INSTALL_RMBL_B_ROLL.ps1").read_text(encoding="utf-8-sig")
    updater = Path("SEARCH_UPDATE.ps1").read_text(encoding="utf-8-sig")
    cleaner = Path("tools/prune_rmbl_backups.ps1").read_text(encoding="utf-8")
    assert "tools\\prune_rmbl_backups.ps1" in installer
    assert "Installazione completata e verificata" in installer
    assert "Test-RMBLManagedBackup" in cleaner
    assert "install-backups" in cleaner
    assert "ReparsePoint" in cleaner
    assert "rambla-data" in cleaner
    assert "Clear-RMBLUpdateStaging" in updater
    assert "^rmbl-update-[0-9a-f]{32}$" in updater
    assert "AddHours(-24)" in updater
    assert "$updateCompleted = $true" in updater
