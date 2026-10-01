from pathlib import Path
import shutil
import uuid

from fastapi.testclient import TestClient

from backend.app.resolve_bridge import can_reuse_audio_capture, detect_video_ranges, phrase_has_video, timeline_audio_fingerprint, timeline_range, count_audio_items
from backend.app.curation_server import create_app


class Timeline:
    def __init__(self, marks): self.marks = marks
    def GetMarkInOut(self): return self.marks
    def GetStartFrame(self): return 100
    def GetEndFrame(self): return 301


def test_bridge_prefers_audio_in_out():
    assert timeline_range(Timeline({"audio": {"in": 120, "out": 180}, "video": {"in": 130, "out": 170}})) == (120, 180, "audio")


def test_bridge_uses_video_marks_then_whole_timeline():
    assert timeline_range(Timeline({"video": {"in": 130, "out": 170}})) == (130, 170, "video")
    assert timeline_range(Timeline({})) == (100, 300, "timeline")


class Item:
    def __init__(self, start, end, name="clip"):
        self.start, self.end, self.name = start, end, name
    def GetStart(self): return self.start
    def GetEnd(self): return self.end
    def GetName(self): return self.name
    def GetUniqueId(self): return self.name + "-id"
    def GetLeftOffset(self, *_): return 2
    def GetRightOffset(self, *_): return 3
    def GetMediaPoolItem(self): return self


class VideoTimeline(Timeline):
    def GetTrackCount(self, kind): return 3 if kind == "video" else 0
    def GetIsTrackEnabled(self, kind, index): return index != 3
    def GetTrackName(self, kind, index): return f"V{index}"
    def GetItemListInTrack(self, kind, index):
        return {1: [Item(100, 300, "base")], 2: [Item(110, 140, "existing b-roll")], 3: [Item(150, 180)]}[index]


def test_detect_video_ranges_uses_overlays_by_default_and_can_include_v1():
    assert detect_video_ranges(VideoTimeline({}), 100, 199, 10) == [
        {"start": 1.0, "end": 4.0, "track": 2, "track_name": "V2", "clip_name": "existing b-roll"}
    ]
    assert detect_video_ranges(VideoTimeline({}), 100, 199, 10, include_v1=True) == [
        {"start": 0.0, "end": 10.0, "track": 1, "track_name": "V1", "clip_name": "base"},
        {"start": 1.0, "end": 4.0, "track": 2, "track_name": "V2", "clip_name": "existing b-roll"}
    ]


def test_phrase_video_badge_requires_half_the_phrase_duration():
    ranges = [{"start": 1.0, "end": 3.0}]
    assert phrase_has_video(0.0, 4.0, ranges)
    assert not phrase_has_video(0.0, 5.0, ranges)


class AudioTimeline(Timeline):
    def __init__(self, items): super().__init__({}); self.items = items
    def GetUniqueId(self): return "timeline-id"
    def GetTrackCount(self, kind): return 1 if kind == "audio" else 0
    def GetIsTrackEnabled(self, kind, index): return True
    def GetTrackName(self, kind, index): return "Dialogue"
    def GetItemListInTrack(self, kind, index): return self.items


def test_audio_fingerprint_changes_for_audio_edits_but_not_video_edits():
    first = timeline_audio_fingerprint(AudioTimeline([Item(100, 150, "voice")]), 100, 200, 25)
    same = timeline_audio_fingerprint(AudioTimeline([Item(100, 150, "voice")]), 100, 200, 25)
    changed = timeline_audio_fingerprint(AudioTimeline([Item(101, 150, "voice")]), 100, 200, 25)
    assert first == same
    assert first != changed


def test_count_audio_items_only_counts_enabled_clips_in_range():
    assert count_audio_items(AudioTimeline([Item(100,150,"voice")]),100,200) == 1
    assert count_audio_items(AudioTimeline([Item(250,300,"outside")]),100,200) == 0


def test_audio_cache_requires_the_same_timeline_range_and_fingerprint():
    previous = {"resolve_timeline_id":"tl-1", "mark_in":100, "mark_out":200,
                "fps":25.0, "audio_fingerprint":"same"}
    current = {**previous, "audio_item_count":1}
    assert can_reuse_audio_capture(previous, current, guide_ready=True)
    assert not can_reuse_audio_capture(previous, {**current, "resolve_timeline_id":"tl-2"}, guide_ready=True)
    assert not can_reuse_audio_capture(previous, {**current, "mark_out":201}, guide_ready=True)
    assert not can_reuse_audio_capture(previous, {**current, "audio_fingerprint":"changed"}, guide_ready=True)
    assert not can_reuse_audio_capture(previous, {**current, "audio_item_count":0}, guide_ready=True)
    assert not can_reuse_audio_capture(previous, current, guide_ready=True, force_recalculate=True)


def test_resolve_script_is_a_stable_non_blocking_standalone_launcher():
    plugin = Path("tools/resolve_bridge/RAMBLA_B_ROLL.py").read_text(encoding="utf-8")
    assert 'standalone_bridge.py' in plugin
    assert 'pythonw.exe' in plugin
    assert 'subprocess.Popen' in plugin
    assert 'creationflags=0x08000000' in plugin
    assert 'UIDispatcher' not in plugin
    assert 'RunLoop' not in plugin
    assert '/resolve-handoffs/pending' not in plugin
    assert 'auto_update_bridge' not in plugin
    assert 'os.replace' not in plugin


def test_bridge_source_is_served_for_local_self_update():
    root = Path(".test-resolve-bridge") / uuid.uuid4().hex
    try:
        response = TestClient(create_app(project_root=root / "projects")).get(
            "/api/curation/resolve-bridge/plugin.py"
        )
        source = Path("tools/resolve_bridge/RAMBLA_B_ROLL.py").read_text(encoding="utf-8")
        assert response.status_code == 200
        assert response.text == source
        assert response.headers["x-rambla-bridge-sha256"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_bridge_session_exposes_a_real_recent_heartbeat():
    root = Path(".test-resolve-bridge") / uuid.uuid4().hex
    try:
        client = TestClient(create_app(project_root=root / "projects"))
        before = client.get("/api/curation/resolve-bridge/session").json()
        assert before["connected"] is False
        started = client.post("/api/curation/resolve-bridge/session", json={"bridge_session_id":"live-window"}).json()
        assert started["bridge_session_id"] == "live-window"
        after = client.get("/api/curation/resolve-bridge/session").json()
        assert after["connected"] is True
        assert after["bridge_session_id"] == "live-window"
    finally:
        shutil.rmtree(root, ignore_errors=True)
