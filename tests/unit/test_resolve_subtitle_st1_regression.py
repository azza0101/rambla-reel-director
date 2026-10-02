"""Native SRT regression: test real orchestration against a lock-aware importer.

The fake deliberately ignores trackIndex and overwrites an occupied ST1.
No connection to a real Resolve instance is made.
"""
import copy
import sys
from types import SimpleNamespace

import pytest
from backend.app import resolve_native_subtitles as native
from backend.app import resolve_textplus_timeline as materializer

ROWS = [
    {"text": "Uno due", "start_seconds": 0.0, "end_seconds": 1.0},
    {"text": "tre", "start_seconds": 1.1, "end_seconds": 2.0},
]

class Item:
    def __init__(self, uid, text, start, end, *, rmbl=False):
        self.uid, self.text, self.start, self.end = uid, text, start, end
        self.enabled = True
        self.media = SimpleNamespace(
            GetName=lambda: "RAMBLA native subs" if rmbl else "Client source",
            GetClipProperty=lambda key: "",
        )
    def GetUniqueId(self): return self.uid
    def GetName(self): return self.text
    def GetStart(self): return self.start
    def GetEnd(self): return self.end
    def GetMediaPoolItem(self): return self.media
    def GetFusionCompCount(self): return 0
    def GetClipColor(self): return ""
    def SetClipEnabled(self, value): self.enabled = bool(value); return True

class Timeline:
    def __init__(self):
        self.old = Item("old-sub", "Vecchio", 108000, 108030, rmbl=True)
        self.user = Item("user-sub", "Nota cliente", 108250, 108290)
        self.tracks = {
            "video": [self.track([Item("v1", "Video", 108000, 108300)], True)],
            "audio": [self.track([Item("a1", "Audio", 108000, 108300)], False)],
            "subtitle": [self.track([self.old, self.user], True)],
        }
        self.markers = {19.0: {"color": "Blue", "name": "M", "note": "keep", "duration": 1.0}}
        self.add_behavior = "normal"
        self.add_calls = []
    @staticmethod
    def track(items=None, locked=False):
        return {"items": list(items or []), "locked": locked, "enabled": True, "name": "Original"}
    def GetUniqueId(self): return "timeline"
    def GetName(self): return "EGITTO"
    def GetSetting(self, key): return "30"
    def GetStartFrame(self): return 108000
    def GetEndFrame(self): return 108300
    def GetTrackCount(self, kind): return len(self.tracks[kind])
    def GetItemListInTrack(self, kind, track): return list(self.tracks[kind][track - 1]["items"])
    def GetIsTrackLocked(self, kind, track): return self.tracks[kind][track - 1]["locked"]
    def SetTrackLock(self, kind, track, value): self.tracks[kind][track - 1]["locked"] = bool(value); return True
    def GetTrackName(self, kind, track): return self.tracks[kind][track - 1]["name"]
    def SetTrackName(self, kind, track, name): self.tracks[kind][track - 1]["name"] = name; return True
    def GetIsTrackEnabled(self, kind, track): return self.tracks[kind][track - 1]["enabled"]
    def SetTrackEnable(self, kind, track, value): self.tracks[kind][track - 1]["enabled"] = bool(value); return True
    def GetMarkers(self): return copy.deepcopy(self.markers)
    def DeleteMarkerAtFrame(self, frame): raise AssertionError("unchanged markers must not be rewritten")
    def AddMarker(self, *args): raise AssertionError("unchanged markers must not be rewritten")
    def AddTrack(self, kind, options=None):
        self.add_calls.append((kind, options))
        if self.add_behavior == "nochange": return True
        index = (options or {}).get("index", len(self.tracks[kind]) + 1)
        if self.add_behavior == "append": index = len(self.tracks[kind]) + 1
        self.tracks[kind].insert(index - 1, self.track())
        return True

class Folder:
    def __init__(self, name="root"):
        self.name, self.children = name, []
    def GetName(self): return self.name
    def GetSubFolderList(self): return self.children
    def GetClipList(self): return []

class Pool:
    def __init__(self, timeline):
        self.timeline = timeline
        self.root = self.current = Folder()
        self.srt = ""
        self.calls = []
        self.append_failure = False
        self.serial = 0
        self.source = SimpleNamespace(GetClipProperty=lambda key: "Subtitle" if key == "Type" else "",
                                      SetClipProperty=lambda *args: True)
    def GetRootFolder(self): return self.root
    def GetCurrentFolder(self): return self.current
    def SetCurrentFolder(self, folder): self.current = folder; return True
    def MoveClips(self, clips, folder): return True
    def AddSubFolder(self, parent, name):
        folder = Folder(name); parent.children.append(folder); return folder
    def ImportMedia(self, paths):
        from pathlib import Path
        self.srt = Path(paths[0]).read_text(encoding="utf-8-sig")
        return [self.source]
    @staticmethod
    def seconds(stamp):
        h, m, rest = stamp.split(":")
        return int(h) * 3600 + int(m) * 60 + float(rest.replace(",", "."))
    def AppendToTimeline(self, rows):
        self.calls.append(rows)
        if self.append_failure: raise RuntimeError("simulated native failure")
        if self.timeline.GetIsTrackLocked("subtitle", 1): return [self.source]
        self.serial += 1
        new = []
        for number, block in enumerate(self.srt.strip().split("\n\n")):
            _index, time_range, text = block.split("\n", 2)
            a, b = time_range.split(" --> ")
            new.append(Item(f"new-{self.serial}-{number}", text,
                            108000 + round(self.seconds(a) * 30),
                            108000 + round(self.seconds(b) * 30), rmbl=True))
        self.timeline.tracks["subtitle"][0]["items"] = new
        return new

@pytest.fixture
def rig(monkeypatch):
    timeline = Timeline()
    pool = Pool(timeline)
    project = SimpleNamespace(
        GetName=lambda: "P", GetCurrentTimeline=lambda: timeline,
        GetMediaPool=lambda: pool, SetCurrentTimeline=lambda t: True,
        GetTimelineCount=lambda: 1, GetTimelineByIndex=lambda i: timeline,
    )
    manager = SimpleNamespace(GetCurrentProject=lambda: project, SaveProject=lambda: True)
    resolve = SimpleNamespace(GetProjectManager=lambda: manager, OpenPage=lambda page: True)
    monkeypatch.setitem(sys.modules, "DaVinciResolveScript", SimpleNamespace(scriptapp=lambda name: resolve))
    backups, restored = [], []
    def backup(original, name):
        backups.append(copy.deepcopy(original.tracks))
        return original, SimpleNamespace(GetName=lambda: name)
    def restore(*args):
        restored.append(True)
        timeline.tracks = copy.deepcopy(backups[-1])
        return timeline
    monkeypatch.setattr(materializer, "create_active_backup", backup)
    monkeypatch.setattr(materializer, "find_timeline_media_item", lambda *args: object())
    monkeypatch.setattr(materializer, "restore_active_timeline", restore)
    payload = {"mode": "editing", "apply_scope": "subtitles", "destination_mode": "active",
               "source_project_name": "P", "project_name": "KURA", "subtitles": copy.deepcopy(ROWS),
               "bridge_mark_in": 108000}
    return SimpleNamespace(timeline=timeline, pool=pool, payload=payload, backups=backups, restored=restored)

def test_only_subs_works_when_native_importer_ignores_target_and_st1_was_locked(rig):
    markers = copy.deepcopy(rig.timeline.markers)
    result = materializer.materialize_in_resolve(rig.payload)
    assert result["subtitle_count"] == 2
    assert result["subtitle_track_index"] == 1
    assert rig.pool.calls == [[rig.pool.source]]
    assert rig.timeline.GetTrackCount("subtitle") == 2
    assert rig.timeline.old in rig.timeline.GetItemListInTrack("subtitle", 2)
    assert rig.timeline.user in rig.timeline.GetItemListInTrack("subtitle", 2)
    assert not rig.timeline.old.enabled and rig.timeline.user.enabled
    assert rig.timeline.GetIsTrackLocked("subtitle", 2) is True
    assert rig.timeline.GetIsTrackLocked("subtitle", 1) is False
    assert rig.timeline.GetIsTrackLocked("video", 1) is True
    assert rig.timeline.GetIsTrackLocked("audio", 1) is False
    assert rig.timeline.markers == markers
    assert len(rig.backups) == 1 and not rig.restored

def test_only_subs_can_run_twice_without_replacing_prior_subtitle_items(rig):
    materializer.materialize_in_resolve(rig.payload)
    first = rig.timeline.GetItemListInTrack("subtitle", 1)
    result = materializer.materialize_in_resolve(rig.payload)
    assert result["subtitle_count"] == 2
    assert rig.timeline.GetTrackCount("subtitle") == 3
    assert rig.timeline.GetItemListInTrack("subtitle", 2) == first
    assert all(not item.enabled for item in first)
    assert rig.timeline.old in rig.timeline.GetItemListInTrack("subtitle", 3)
    assert rig.timeline.GetTrackName("subtitle", 1) == "RMBL SUBS v2"
    assert len(rig.backups) == 2

def test_only_subs_respects_current_in_not_just_timeline_start(rig):
    rig.payload["bridge_mark_in"] = 108090
    materializer.materialize_in_resolve(rig.payload)
    assert [(x.GetStart(), x.GetEnd()) for x in rig.timeline.GetItemListInTrack("subtitle", 1)] == [
        (108090, 108120), (108123, 108150),
    ]

@pytest.mark.parametrize("behavior", ["append", "nochange"])
def test_failed_indexed_track_creation_never_appends_over_old_subtitles(rig, behavior):
    rig.timeline.add_behavior = behavior
    with pytest.raises(RuntimeError):
        materializer.materialize_in_resolve(rig.payload)
    assert not rig.pool.calls
    assert rig.restored == [True]
    assert rig.timeline.GetTrackCount("subtitle") == 1

def test_native_import_failure_restores_locks_and_runs_existing_rollback(rig):
    rig.pool.append_failure = True
    with pytest.raises(RuntimeError, match="simulated native failure"):
        materializer.materialize_in_resolve(rig.payload)
    assert rig.restored == [True]
    assert rig.timeline.GetIsTrackLocked("subtitle", 1) is True
    assert rig.timeline.GetTrackCount("subtitle") == 1
    assert rig.timeline.GetItemListInTrack("subtitle", 1)[0].enabled is True

def test_empty_subtitles_are_rejected_before_any_import(rig):
    rig.payload["subtitles"] = []
    with pytest.raises(ValueError, match="sottotitoli"):
        materializer.materialize_in_resolve(rig.payload)
    assert not rig.pool.calls

def test_legacy_plain_import_still_restores_its_temporary_lock(rig):
    rig.timeline.tracks["subtitle"][0]["items"] = []
    rows = native.normalize_subtitle_rows(ROWS, fps=30)
    items = native.insert_native_subtitles(None, SimpleNamespace(GetMediaPool=lambda: rig.pool),
                                           rig.timeline, rows, fps=30, base_frame=108000)
    native.verify_native_subtitles(rig.timeline, rows, fps=30, base_frame=108000, items=items)
    assert len(items) == 2 and rig.timeline.GetIsTrackLocked("subtitle", 1) is True
