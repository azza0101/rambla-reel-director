from pathlib import Path

import pytest

from backend.app.resolve_native_subtitles import (
    insert_native_subtitles,
    normalize_subtitle_rows,
    render_filtered_srt,
    verify_native_subtitles,
    ensure_media_pool_folder,
    cleanup_stale_subtitle_media,
    subtitle_track_for_items,
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


def test_native_srt_import_is_anchored_to_timeline_start_and_restores_playhead():
    timeline = Timeline()
    timeline.playhead = "01:06:42:28"
    timeline.timecode_calls = []
    timeline.GetCurrentTimecode = lambda: timeline.playhead
    timeline.GetStartTimecode = lambda: "01:00:00:00"

    def set_timecode(value):
        timeline.timecode_calls.append(value)
        timeline.playhead = value
        return True

    timeline.SetCurrentTimecode = set_timecode

    class Clip:
        def GetClipProperty(self, key): return "Subtitle" if key == "Type" else ""

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
        def ImportMedia(self, paths):
            assert timeline.playhead == "01:00:00:00"
            return [clip]
        def AppendToTimeline(self, clips):
            assert timeline.playhead == "01:00:00:00"
            timeline.items = [NativeItem("Uno due", 108000, 108030), NativeItem("tre", 108033, 108060)]
            return timeline.items

    pool = Pool()
    class Project:
        def GetMediaPool(self): return pool

    insert_native_subtitles(None, Project(), timeline, ROWS, fps=30, base_frame=108000)

    assert timeline.timecode_calls == ["01:00:00:00", "01:06:42:28"]
    assert timeline.playhead == "01:06:42:28"


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


def test_native_srt_isolates_reserved_track_and_restores_existing_subtitle_tracks():
    existing = NativeItem("client subtitle", 108500, 108530)

    class MultiTrackTimeline:
        def __init__(self):
            self.tracks = [[], [existing]]
            self.locks = {1: False, 2: True}
            self.enabled = {1: True, 2: True}
        def GetStartFrame(self): return 108000
        def GetTrackCount(self, kind): return len(self.tracks)
        def GetItemListInTrack(self, kind, track): return self.tracks[track - 1]
        def GetIsTrackLocked(self, kind, track): return self.locks[track]
        def SetTrackLock(self, kind, track, value): self.locks[track] = bool(value); return True
        def GetIsTrackEnabled(self, kind, track): return self.enabled[track]
        def SetTrackEnable(self, kind, track, value): self.enabled[track] = bool(value); return True

    timeline = MultiTrackTimeline()

    class Clip:
        def GetClipProperty(self, key): return "Subtitle" if key == "Type" else ""

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
            assert timeline.enabled == {1: True, 2: False}
            assert timeline.locks == {1: False, 2: False}
            inserted = [NativeItem("Uno due", 108000, 108030), NativeItem("tre", 108033, 108060)]
            timeline.tracks[0].extend(inserted)
            return inserted

    pool = Pool()
    class Project:
        def GetMediaPool(self): return pool

    inserted = insert_native_subtitles(
        None, Project(), timeline, ROWS, fps=30, base_frame=108000, target_track=1
    )

    assert len(inserted) == 2
    assert timeline.locks == {1: False, 2: True}
    assert timeline.enabled == {1: True, 2: True}


def test_selective_subtitles_target_a_new_upper_track_with_clipinfo():
    class MultiTrackTimeline:
        def __init__(self):
            self.tracks=[[], []]
            self.locks={1:True,2:False}
        def GetTrackCount(self, kind): assert kind=="subtitle"; return len(self.tracks)
        def AddTrack(self, kind): assert kind=="subtitle"; self.tracks.append([]); return True
        def GetItemListInTrack(self, kind, track): assert kind=="subtitle"; return self.tracks[track-1]
        def GetIsTrackLocked(self, kind, track): return self.locks.get(track,False)
        def SetTrackLock(self, kind, track, value): self.locks[track]=bool(value); return True
        def DeleteClips(self, items, _ripple):
            for row in self.tracks:
                row[:] = [item for item in row if item not in items]
            return True
    timeline=MultiTrackTimeline()

    class Clip:
        def GetClipProperty(self, key): return "Subtitle" if key=="Type" else ""
    clip=Clip()
    class Folder:
        def GetName(self): return "TEMP"
        def GetSubFolderList(self): return []
        def GetClipList(self): return []
    class Pool:
        def __init__(self): self.folder=Folder(); self.appended=None
        def GetRootFolder(self): return self.folder
        def AddSubFolder(self, parent, name): return self.folder
        def GetCurrentFolder(self): return self.folder
        def SetCurrentFolder(self, folder): return True
        def ImportMedia(self, paths): return [clip]
        def AppendToTimeline(self, rows):
            self.appended=rows
            assert rows[0]["trackIndex"] == 2
            timeline.tracks[1]=[NativeItem("Uno due",108000,108030),NativeItem("tre",108033,108060)]
            return timeline.tracks[1]
    pool=Pool()
    class Project:
        def GetMediaPool(self): return pool

    inserted=insert_native_subtitles(None,Project(),timeline,ROWS,fps=30,base_frame=108000,target_track=2)
    assert len(inserted)==2
    assert pool.appended[0]["trackIndex"]==2
    verify_native_subtitles(timeline,ROWS,fps=30,base_frame=108000,track_index=2)


def test_selective_subtitles_accept_resolve_21_fallback_to_st1_and_remove_empty_upper_track():
    class MultiTrackTimeline:
        def __init__(self):
            self.tracks=[[]]
            self.locks={1:False}
            self.deleted_tracks=[]
        def GetTrackCount(self, kind): assert kind=="subtitle"; return len(self.tracks)
        def AddTrack(self, kind): assert kind=="subtitle"; self.tracks.append([]); return True
        def DeleteTrack(self, kind, track):
            assert kind=="subtitle"
            self.deleted_tracks.append(track)
            self.tracks.pop(track-1)
            return True
        def GetItemListInTrack(self, kind, track): assert kind=="subtitle"; return self.tracks[track-1]
        def GetIsTrackLocked(self, kind, track): return self.locks.get(track,False)
        def SetTrackLock(self, kind, track, value): self.locks[track]=bool(value); return True
    timeline=MultiTrackTimeline()

    class Clip:
        def GetClipProperty(self, key): return "Subtitle" if key=="Type" else ""
    clip=Clip()
    class Folder:
        def GetName(self): return "TEMP"
        def GetSubFolderList(self): return []
        def GetClipList(self): return []
    class Pool:
        def __init__(self): self.folder=Folder()
        def GetRootFolder(self): return self.folder
        def AddSubFolder(self, parent, name): return self.folder
        def GetCurrentFolder(self): return self.folder
        def SetCurrentFolder(self, folder): return True
        def ImportMedia(self, paths): return [clip]
        def AppendToTimeline(self, rows):
            # Resolve 21.1 ignores requested ST2 and materializes the imported
            # native SRT on ST1.
            timeline.tracks[0]=[
                NativeItem("Uno due",108000,108030),
                NativeItem("tre",108033,108060),
            ]
            return timeline.tracks[0]
    pool=Pool()
    class Project:
        def GetMediaPool(self): return pool

    inserted=insert_native_subtitles(None,Project(),timeline,ROWS,fps=30,base_frame=108000,target_track=2)

    assert len(inserted)==2
    assert subtitle_track_for_items(timeline,inserted)==1
    assert timeline.deleted_tracks == [2]
    verify_native_subtitles(timeline,ROWS,fps=30,base_frame=108000,items=inserted)


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


def test_overlapping_subtitles_preserve_all_text_on_separate_frames():
    rows=[{'text':'prima','start_seconds':0,'end_seconds':1},
          {'text':'seconda','start_seconds':.95,'end_seconds':.98},
          {'text':'terza','start_seconds':.96,'end_seconds':1.1}]
    normalized=normalize_subtitle_rows(rows,fps=30)
    assert [r['text'] for r in normalized]==['prima','seconda','terza']
    assert all(r['end_frame']>r['start_frame'] for r in normalized)
    assert all(a['end_frame']<=b['start_frame'] for a,b in zip(normalized,normalized[1:]))


def test_srt_import_path_changes_with_timing_or_text_to_avoid_resolve_cache():
    from backend.app.resolve_native_subtitles import subtitle_content_path
    path=Path('subtitles.srt')
    old=render_filtered_srt(ROWS)
    changed=render_filtered_srt([{**ROWS[0],'start_seconds':.1},ROWS[1]])
    assert subtitle_content_path(path,old)!=subtitle_content_path(path,changed)
    assert subtitle_content_path(path,old)==subtitle_content_path(path,old)
    assert subtitle_content_path(path,old).suffix=='.srt'
