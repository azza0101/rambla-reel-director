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

