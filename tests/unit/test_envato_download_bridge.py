import json
import shutil
import uuid
import zipfile
from pathlib import Path


def _root():
    path = Path.cwd() / (".test-envato-download-" + uuid.uuid4().hex)
    path.mkdir()
    return path


def test_adopts_new_direct_video_and_persists_asset_mapping():
    from backend.app.envato_download_bridge import capture_snapshot, adopt_new_download

    root = _root()
    try:
        downloads, run = root / "Downloads", root / "run"
        downloads.mkdir(); run.mkdir()
        baseline = capture_snapshot(downloads)
        source = downloads / "bathroom-stock-video.mp4"
        source.write_bytes(b"video" * 100)

        result = adopt_new_download(downloads, baseline, run, "beat_003--envato:item")

        assert result["status"] == "ready"
        target = Path(result["media_path"])
        assert target.is_file() and target.parent.parent.name == "envato-media"
        registry = json.loads((run / "envato-downloads.json").read_text(encoding="utf-8"))
        assert registry["assets"]["beat_003--envato:item"]["media_path"] == str(target)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_adopts_largest_video_from_new_envato_zip_and_ignores_partial_files():
    from backend.app.envato_download_bridge import capture_snapshot, adopt_new_download

    root = _root()
    try:
        downloads, run = root / "Downloads", root / "run"
        downloads.mkdir(); run.mkdir()
        baseline = capture_snapshot(downloads)
        (downloads / "unfinished.crdownload").write_bytes(b"partial")
        package = downloads / "envato-item.zip"
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("preview.mp4", b"x" * 10)
            archive.writestr("footage/main.mov", b"x" * 200)
            archive.writestr("../escape.mov", b"x" * 500)

        result = adopt_new_download(downloads, baseline, run, "beat_006--envato:item")

        assert result["status"] == "ready"
        assert Path(result["media_path"]).suffix == ".mov"
        assert Path(result["media_path"]).read_bytes() == b"x" * 200
        assert not (root / "escape.mov").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_reports_waiting_when_no_completed_download_changed():
    from backend.app.envato_download_bridge import capture_snapshot, adopt_new_download

    root = _root()
    try:
        downloads, run = root / "Downloads", root / "run"
        downloads.mkdir(); run.mkdir()
        (downloads / "old.mp4").write_bytes(b"old")
        baseline = capture_snapshot(downloads)

        assert adopt_new_download(downloads, baseline, run, "asset")["status"] == "waiting"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_envato_uses_windows_url_shell_instead_of_spawning_chrome(monkeypatch):
    from backend.app import browser_profiles

    opened = []
    monkeypatch.setattr(browser_profiles.os, "name", "nt")
    monkeypatch.setattr(browser_profiles.os, "startfile", lambda url: opened.append(url), raising=False)

    pid = browser_profiles._default_login_launcher(
        "envato", Path("unused"), "https://elements.envato.com/example"
    )

    assert opened == ["https://elements.envato.com/example"]
    assert pid == 0
