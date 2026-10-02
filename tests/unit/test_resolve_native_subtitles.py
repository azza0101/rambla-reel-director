from pathlib import Path

import pytest

from backend.app.resolve_native_subtitles import (
    insert_native_subtitles,
    normalize_subtitle_rows,
    render_filtered_srt,
    verify_native_subtitles,
    ensure_media_pool_folder,
    cleanup_stale_subtitle_media,
)


ROWS = [
    {"text": "Uno due", "start_seconds": 0.0, "end_seconds": 1.0, "start_frame": 0, "end_frame": 30},
    {"text": "tre", "start_seconds": 1.1, "end_seconds": 2.0, "start_frame": 33, "end_frame": 60},
]


def test_render_filtered_srt_uses_relative_timing_and_utf8_text():
    assert render_filtered_srt(ROWS) == (
        "1\n00:00:00,000 --> 00:00:01,000\nUno due\n\n"
        "2\n00:00:01,100 --> 00:00:02,000\ntre\n"
    )


def test_render_filtered_srt_allows_no_remaining_subtitles():
    assert render_filtered_srt([]) == ""


def test_subtitle_frames_are_rebuilt_for_the_actual_resolve_timeline_fps():
    source = [{"text": "ciao", "start_seconds": 0.256, "end_seconds": 1.024, "start_frame": 6, "end_frame": 26}]

    normalized = normalize_subtitle_rows(source, fps=30)

    assert normalized[0]["start_frame"] == 8
    assert normalized[0]["end_frame"] == 31
    assert source[0]["start_frame"] == 6


class NativeItem:
    def __init__(self, name, start, end):
        self.name, self.start, self.end = name, start, end

    def GetName(self): return self.name
    def GetStart(self): return self.start
    def GetEnd(self): return self.end


class Timeline:
    def __init__(self, items=None):
        self.items = list(items or [])
        self.added = []
        self.has_track = bool(self.items)
        self.locked = False

    def GetTrackCount(self, kind):
        assert kind == "subtitle"
        return 1 if self.has_track else 0

    def AddTrack(self, kind):
        self.added.append(kind)
        self.has_track = True
        return True

    def GetItemListInTrack(self, kind, track):
        assert (kind, track) == ("subtitle", 1)
        return self.items

    def GetIsTrackLocked(self, kind, track):
        assert (kind, track) == ("subtitle", 1)
        return self.locked

    def SetTrackLock(self, kind, track, locked):
        assert (kind, track) == ("subtitle", 1)
        self.locked = bool(locked)
        return True


def test_verify_native_subtitles_matches_text_and_absolute_frame_ranges():
    timeline = Timeline([NativeItem("Uno due", 108000, 108030), NativeItem("tre", 108033, 108060)])
    verify_native_subtitles(timeline, ROWS, fps=30, base_frame=108000)


def test_verify_native_subtitles_accepts_resolve_one_frame_rounding():
    timeline = Timeline([NativeItem("Uno due", 108001, 108029), NativeItem("tre", 108032, 108061)])
    verify_native_subtitles(timeline, ROWS, fps=30, base_frame=108000)


def test_verify_native_subtitles_rejects_wrong_text_or_range():
    timeline = Timeline([NativeItem("wrong", 108000, 108030), NativeItem("tre", 108033, 108060)])
    with pytest.raises(RuntimeError, match="verification"):
        verify_native_subtitles(timeline, ROWS, fps=30, base_frame=108000)


def test_insert_native_subtitles_imports_srt_and_appends_native_media():
    timeline = Timeline()

    class Clip:
        def GetClipProperty(self, key):
            return "Subtitle" if key == "Type" else ""

    clip = Clip()

    class Pool:
        def __init__(self):
            self.srt = ""
            self.appended = None
            self.root = type("Folder", (), {"GetSubFolderList": lambda self: [], "GetClipList": lambda self: []})()
            self.original = object()
            self.current = self.original

        def GetRootFolder(self): return self.root
        def AddSubFolder(self, parent, name):
            assert parent is self.root and name == "TEMP"
            return type("Folder", (), {"GetName": lambda self: "TEMP"})()
        def GetCurrentFolder(self): return self.current
        def SetCurrentFolder(self, folder): self.current = folder; return True
        def MoveClips(self, clips, folder): return True

        def ImportMedia(self, paths):
            self.srt = Path(paths[0]).read_text(encoding="utf-8-sig")
            return [clip]

        def AppendToTimeline(self, clips):
            self.appended = clips
            timeline.items = [NativeItem("Uno due", 108000, 108030), NativeItem("tre", 108033, 108060)]
            return timeline.items

    pool = Pool()

    class Project:
        def GetMediaPool(self): return pool

    inserted = insert_native_subtitles(None, Project(), timeline, ROWS, fps=30, base_frame=108000)

    assert timeline.added == ["subtitle"]
    assert pool.srt.startswith("1\n00:00:00,000")
    assert pool.appended == [clip]
    assert pool.current is pool.original
    assert [item.GetName() for item in inserted] == ["Uno due", "tre"]


def test_insert_native_subtitles_temporarily_unlocks_first_subtitle_track():
    timeline = Timeline()
    timeline.has_track = True
    timeline.locked = True

    class Clip:
        def GetClipProperty(self, key):
            return "Subtitle" if key == "Type" else ""

    clip = Clip()

    class Folder:
        def GetName(self): return "TEMP"
        def GetSubFolderList(self): return []
        def GetClipList(self): return []

    class Pool:
        def __init__(self): self.folder = Folder()
        def GetRootFolder(self): return self.folder
        def AddSubFolder(self, parent, name): return self.folder
        def GetCurrentFolder(self): return self.folder
        def SetCurrentFolder(self, folder): return True
        def ImportMedia(self, paths): return [clip]
        def AppendToTimeline(self, clips):
            # Resolve 21.1 returns a media item but creates no subtitle clips
            # while subtitle track 1 is locked.
            if timeline.locked:
                return [clip]
            timeline.items = [NativeItem("Uno due", 108000, 108030), NativeItem("tre", 108033, 108060)]
            return timeline.items

    pool = Pool()
    class Project:
        def GetMediaPool(self): return pool

    inserted = insert_native_subtitles(None, Project(), timeline, ROWS, fps=30, base_frame=108000)

    assert len(inserted) == 2
    assert timeline.locked is True


def test_insert_native_subtitles_is_a_noop_for_empty_rows():
    timeline = Timeline()
    assert insert_native_subtitles(None, object(), timeline, [], fps=30, base_frame=108000) == []
    assert timeline.added == []


def test_ensure_media_pool_folder_reuses_temp_or_creates_it_once():
    class Folder:
        def __init__(self, name, children=None): self.name, self.children = name, list(children or [])
        def GetName(self): return self.name
        def GetSubFolderList(self): return self.children

    existing = Folder("TEMP")
    root = Folder("Root", [existing])

    class Pool:
        def __init__(self): self.created = []
        def GetRootFolder(self): return root
        def AddSubFolder(self, parent, name):
            self.created.append((parent, name))
            return Folder(name)

    pool = Pool()
    assert ensure_media_pool_folder(pool, "TEMP") is existing
    assert pool.created == []

    root.children.clear()
    created = ensure_media_pool_folder(pool, "TEMP")
    assert created.GetName() == "TEMP"
    assert pool.created == [(root, "TEMP")]


def test_cleanup_stale_subtitle_media_preserves_current_source():
    class Clip:
        def __init__(self, name, path): self.name, self.path = name, path
        def GetName(self): return self.name
        def GetClipProperty(self, key): return self.path if key == "File Path" else "Subtitle"

    keep = Clip("RAMBLA_4_NATIVE_SUBS_current", "C:/current.srt")
    stale = Clip("rambla-native-subs-old", "C:/old.srt")
    unrelated = Clip("captions-client", "C:/client.srt")

    class Folder:
        def GetClipList(self): return [keep, stale, unrelated]
        def GetSubFolderList(self): return []

    class Pool:
        def __init__(self): self.deleted = []
        def GetRootFolder(self): return Folder()
        def DeleteClips(self, clips): self.deleted = clips; return True

    pool = Pool()
    assert cleanup_stale_subtitle_media(pool, keep=keep) == 1
    assert pool.deleted == [stale]
