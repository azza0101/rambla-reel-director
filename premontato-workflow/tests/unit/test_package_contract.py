from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_runtime_dependency_lock_is_hashed_and_license_documented():
    lock = ROOT / "runtime" / "requirements.lock"
    assert lock.exists(), "release must carry an offline dependency lock"
    content = lock.read_text(encoding="utf-8")
    assert "--hash=sha256:" in content
    assert "pypdf==" in content and "opencv-python-headless==" in content
    assert (ROOT / "runtime" / "THIRD_PARTY_NOTICES.txt").exists()


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

