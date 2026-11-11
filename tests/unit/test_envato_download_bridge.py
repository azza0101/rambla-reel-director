import json
import shutil
import uuid
import zipfile
from pathlib import Path


def _root():
    path = Path.cwd() / (".test-envato-download-" + uuid.uuid4().hex)
    path.mkdir()
    return path


def test_adopts_new_direct_video_and_persists_asset_mapping(monkeypatch):
    from backend.app.envato_download_bridge import capture_snapshot, adopt_new_download
    import backend.app.envato_light_media as light
    def make_light(source, directory):
        target=directory/'light.mp4'; target.write_bytes(source.read_bytes()); return target
    monkeypatch.setattr(light, 'prepare_light_media', make_light)

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
        assert source.exists()
        assert not (target.parent / 'original.mp4').exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_adopts_largest_video_from_new_envato_zip_and_ignores_partial_files(monkeypatch):
    from backend.app.envato_download_bridge import capture_snapshot, adopt_new_download
    import backend.app.envato_light_media as light
    def make_light(source, directory):
        target=directory/'light.mp4'; target.write_bytes(source.read_bytes()); return target
    monkeypatch.setattr(light, 'prepare_light_media', make_light)

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
        assert Path(result["media_path"]).suffix == ".mp4"
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


def test_failed_conversion_keeps_download_and_cached_original(monkeypatch):
    from backend.app.envato_download_bridge import adopt_new_download, capture_snapshot
    import backend.app.envato_light_media as light
    root = _root()
    try:
        downloads, run = root / 'Downloads', root / 'run'
        downloads.mkdir(); run.mkdir()
        baseline = capture_snapshot(downloads)
        source = downloads / 'asset.mov'; source.write_bytes(b'original video')
        def fail(*args):
            raise RuntimeError('ffmpeg failed')
        monkeypatch.setattr(light, 'prepare_light_media', fail)
        result = adopt_new_download(downloads, baseline, run, 'asset')
        assert result['status'] == 'error'
        assert source.read_bytes() == b'original video'
        assert next((run / 'envato-media').rglob('original.mov')).read_bytes() == b'original video'
        assert not (run / 'envato-downloads.json').exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_envato_uses_active_chrome_profile_instead_of_windows_default_browser(monkeypatch):
    from backend.app import browser_profiles

    launched = []
    monkeypatch.setattr(browser_profiles, "_installed_chrome", lambda: r"C:\Chrome\chrome.exe")
    monkeypatch.setattr(browser_profiles, "normal_chrome_profile", lambda: (Path("C:/Chrome/User Data"), "Profile 2"))
    class Process:
        pid = 41
        def wait(self, timeout):
            return 0
    monkeypatch.setattr(browser_profiles.subprocess, "Popen", lambda command, **kwargs: launched.append(command) or Process())

    pid = browser_profiles._default_login_launcher(
        "envato", Path("unused"), "https://elements.envato.com/example"
    )

    assert launched == [[r"C:\Chrome\chrome.exe", "--profile-directory=Profile 2", "--new-window", "https://elements.envato.com/example"]]
    assert pid == 41
