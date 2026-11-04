"""Active Resolve source safety for user-uploaded uncut reels."""
from pathlib import Path
from types import SimpleNamespace
import pytest

from backend.app.original_video_active import (
    inspect_active_original_timeline, append_active_original_video,
)


def original(tmp_path):
    path = tmp_path / "premontato.mp4"
    path.write_bytes(b"upload")
    stat = path.stat()
    return {
        "source_path": str(path.resolve()),
        "source_identity": {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns},
        "fps": "30",
        "source_has_audio": True,
        "duration_frames": 120,
        "segments": [{
            "source_in_frame": 0, "source_out_frame": 120,
            "edited_in_frame": 0, "edited_out_frame": 120,
        }],
    }


class Media:
    def __init__(self, path): self.path = path
    def GetClipProperty(self, key): return self.path if key == "File Path" else ""


class Item:
    def __init__(self, path, start=86400, end=86520):
        self.path, self.start, self.end = path, start, end
    def GetStart(self): return self.start
    def GetEnd(self): return self.end
    def GetMediaPoolItem(self): return Media(self.path)
    def GetSourceStartFrame(self): return 0


class Timeline:
    def __init__(self, video=None, audio=None, fps="30"):
        self.tracks = {"video": [list(video or [])], "audio": [list(audio or [])]}
        self.fps = fps
        self.links = []
    def GetTrackCount(self, kind): return len(self.tracks[kind])
    def GetItemListInTrack(self, kind, track): return self.tracks[kind][track - 1]
    def GetStartFrame(self): return 86400
    def GetSetting(self, key): return self.fps
    def SetClipsLinked(self, clips, linked): self.links.append((clips, linked)); return True


def test_empty_active_timeline_can_accept_full_uncut_video_and_audio(monkeypatch, tmp_path):
    source = original(tmp_path)
    timeline = Timeline()
    assert inspect_active_original_timeline(timeline, source) == "import"

    class Pool:
        def __init__(self): self.appended = []
        def ImportMedia(self, paths):
            assert paths == [source["source_path"]]
            return [Media(paths[0])]
        def AppendToTimeline(self, rows):
            self.appended.extend(rows)
            result = []
            for row in rows:
                item = Item(source["source_path"], row["recordFrame"],
                            row["recordFrame"] + row["endFrame"] - row["startFrame"])
                kind = "video" if row["mediaType"] == 1 else "audio"
                timeline.tracks[kind][0].append(item)
                result.append(item)
            return result

    pool = Pool()
    result = append_active_original_video(pool, timeline, source, "import")
    assert result == {
        "video_count": 1, "audio_count": 1,
        "source_mode": "import", "base_frame": 86400,
    }
    assert [row["mediaType"] for row in pool.appended] == [1, 2]
    assert pool.appended[0]["recordFrame"] == 86400
    assert timeline.links[0][1] is True


def test_active_timeline_already_has_the_same_video_no_duplicate(tmp_path):
    source = original(tmp_path)
    existing = Item(source["source_path"])
    timeline = Timeline(video=[existing], audio=[Item(source["source_path"])])
    assert inspect_active_original_timeline(timeline, source) == "reuse"
    pool = SimpleNamespace(ImportMedia=lambda _: pytest.fail("Must reuse source"),
                           AppendToTimeline=lambda _: pytest.fail("Must not append again"))
    assert append_active_original_video(pool, timeline, source, "reuse")["source_mode"] == "reuse"


def test_mismatched_existing_video_is_not_overwritten(tmp_path):
    source = original(tmp_path)
    timeline = Timeline(video=[Item(str(tmp_path / "different.mp4"))])
    with pytest.raises(ValueError, match="montaggio video differente"):
        inspect_active_original_timeline(timeline, source)


def test_active_original_video_rejects_audio_only_timeline(tmp_path):
    source = original(tmp_path)
    timeline = Timeline(audio=[Item(str(tmp_path / "existing_audio.wav"))])
    with pytest.raises(ValueError, match="ha audio ma non video"):
        inspect_active_original_timeline(timeline, source)


def test_active_original_video_does_not_overlay_wrong_fps(tmp_path):
    source = original(tmp_path)
    timeline = Timeline(fps="25")
    with pytest.raises(ValueError, match="FPS della timeline"):
        inspect_active_original_timeline(timeline, source)


def test_active_video_existing_audio_mismatch_is_rejected(tmp_path):
    source = original(tmp_path)
    timeline = Timeline(
        video=[Item(source["source_path"])],
        audio=[Item(str(tmp_path / "other.wav"))],
    )
    with pytest.raises(ValueError, match="audio A1"):
        inspect_active_original_timeline(timeline, source)


def test_active_source_video_bridge_allows_destination_choice_in_repo():
    from pathlib import Path
    script = Path("tools/resolve_bridge/standalone_bridge.py").read_text(encoding="utf-8")
    assert "summary.get('native_cut'):" in script
    assert "summary.get('native_cut') or summary.get('original_video')" not in script
    assert "il video originale richiede INVIA TUTTO su una nuova timeline" not in script
    worker = Path("backend/app/resolve_handoff_jobs.py").read_text(encoding="utf-8")
    assert 'destination_mode = \'new\'' not in worker.split("if package.get('payload', {}).get('original_video'):")[1].split("if package.get('payload', {}).get('native_cut'):")[0]


def test_export_component_checkboxes_are_visible_before_send_button():
    from backend.app.timeline_export_ui import PANEL, JS
    assert PANEL.index('id="resolveComponentsV71"') < PANEL.index('id="sendResolvePackageV33"')
    assert '<details class="legacyExportsV33"><summary>Componenti da esportare' not in PANEL
    assert "count>0" in JS
    assert "input.onchange" in JS


def test_export_javascript_parses_in_node_when_available(tmp_path):
    import shutil
    import subprocess
    from backend.app.timeline_export_ui import JS
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not available on this host")
    script = tmp_path / "resolve-export-v0133.js"
    script.write_text(JS, encoding="utf-8")
    result = subprocess.run([node, "--check", str(script)],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_envato_login_and_official_user_download_are_visible_in_media_section():
    from backend.app.curation_ui_v2 import render_curation_page_v2
    html = render_curation_page_v2()
    assert 'id="envatoLoginV2"' in html
    assert 'id="socialConnectionsV5"' in html
    assert "APRI ENVATO E IMPORTA DOWNLOAD" in html
    assert "download/start" in html
    assert "started.token" in html
