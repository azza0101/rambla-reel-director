from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_runtime_dependency_lock_is_hashed_and_license_documented():
    lock = ROOT / "runtime" / "requirements.lock"
    assert lock.exists(), "release must carry an offline dependency lock"
    content = lock.read_text(encoding="utf-8")
    assert "--hash=sha256:" in content
    assert "pypdf==" in content and "opencv-python-headless==" in content
    assert "opencv-python-headless==4.11.0.86" in content
    runtime_builder = (ROOT / "tools" / "build_runtime.ps1").read_text(encoding="utf-8")
    assert "CascadeClassifier" in runtime_builder and "haarcascade_frontalface_default.xml" in runtime_builder
    assert (ROOT / "runtime" / "THIRD_PARTY_NOTICES.txt").exists()
    launcher = (ROOT / "tools" / "launcher" / "Program.cs").read_text(encoding="utf-8")
    builder = (ROOT / "tools" / "build_installer.ps1").read_text(encoding="utf-8")
    assert "System.IO.Compression" in launcher
    assert "Framework64\\v4.0.30319\\csc.exe" in builder
    assert "dotnet publish" not in builder


def test_installer_copies_worker_runtime_and_sdk_only_from_local_resolve():
    installer = (ROOT / "install" / "Install-Premontato.ps1").read_text(encoding="utf-8")
    assert "runtime=Join-Path $sourceRoot 'runtime'" in installer
    assert "runtime" in installer and "python.exe" in installer
    assert "WorkflowIntegration.node" in installer
    assert "Invoke-WebRequest" not in installer


def test_release_workflow_excludes_media_credentials_and_sdk_binary():
    workflow = ROOT / ".github" / "workflows" / "premontato-release.yml"
    assert workflow.exists(), "release workflow must build installer from source"
    content = workflow.read_text(encoding="utf-8")
    assert "FILES/" in content
    assert "WorkflowIntegration.node" in content
    assert "Install-Premontato.exe" in content


def test_github_updater_is_versioned_and_uses_a_credential_free_release_payload():
    updater = ROOT / "plugin" / "updater.js"
    updater_script = ROOT / "plugin" / "update.ps1"
    builder = ROOT / "tools" / "build_update.ps1"
    assert updater.exists() and updater_script.exists() and builder.exists()
    assert "PROTECTED" in updater.read_text(encoding="utf-8").upper()
    assert "WorkflowIntegration.node" in updater_script.read_text(encoding="utf-8")
    assert "Name -ne 'WorkflowIntegration.node'" in builder.read_text(encoding="utf-8")
    assert "DPAPI" not in builder.read_text(encoding="utf-8").upper()


def test_support_debug_uses_existing_update_allowlist_and_never_sends_without_confirmation():
    main = (ROOT / "plugin" / "main.js").read_text(encoding="utf-8")
    updater = (ROOT / "plugin" / "updater.js").read_text(encoding="utf-8")
    renderer = (ROOT / "plugin" / "renderer.js").read_text(encoding="utf-8")
    html = (ROOT / "plugin" / "index.html").read_text(encoding="utf-8")
    update_script = (ROOT / "plugin" / "update.ps1").read_text(encoding="utf-8")
    assert "prepareSupportReport" in main and "submitSupportReport" in main
    assert "options.confirmed !== true" in updater
    assert "--body-file" in updater and "--label', 'bug'" in updater
    assert "support-confirm" in renderer and "<dialog id=\"support-dialog\"" in html
    assert "'updater.js'" in update_script
    manifest = (ROOT / "plugin" / "package.json").read_text(encoding="utf-8")
    xml = (ROOT / "plugin" / "manifest.xml").read_text(encoding="utf-8")
    import json
    version = json.loads(manifest)["version"]
    assert f"<Version>{version}</Version>" in xml


def test_update_validator_accepts_semver_parameter_in_powershell():
    updater = (ROOT / "plugin" / "update.ps1").read_text(encoding="utf-8")
    assert "-notmatch '^\\d+\\.\\d+\\.\\d+$'" in updater


def test_update_extracts_entries_from_the_reopened_archive():
    updater = (ROOT / "plugin" / "update.ps1").read_text(encoding="utf-8")
    assert "$zip.GetEntry($entry.ArchiveName)" in updater
    assert "$entry.Entry.Open()" not in updater


def test_update_replace_operations_use_valid_backup_paths_on_windows_powershell():
    updater = (ROOT / "plugin" / "update.ps1").read_text(encoding="utf-8")
    assert "[IO.File]::Replace($temporary,$target,$backupFile)" in updater
    assert "$rollbackBackup=$item.Target+'.premontato-rollback-'" in updater
    assert "[IO.File]::Replace($restore,$item.Target,$rollbackBackup)" in updater
    assert "[IO.File]::Replace($temporary,$target,$null)" not in updater
    assert "[IO.File]::Replace($restore,$item.Target,$null)" not in updater


def test_tagged_release_workflow_uploads_to_an_existing_release_without_promoting_it():
    workflow = (ROOT / ".github" / "workflows" / "premontato-release.yml").read_text(encoding="utf-8")
    assert "releases/latest" in workflow
    assert "gh release upload" in workflow
    assert "gh release create" not in workflow

