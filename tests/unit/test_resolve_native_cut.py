import pytest
from backend.app.resolve_native_cut import append_exact_segment
from tests.unit.test_cut_pass_routes import tmp_path


class Clip:
    def __init__(self, row, inclusive):
        self.start = row['recordFrame']
        self.end = self.start + row['endFrame'] - row['startFrame'] + inclusive
    def GetStart(self): return self.start
    def GetEnd(self): return self.end


class Pool:
    def __init__(self, inclusive): self.inclusive = inclusive; self.calls = []
    def AppendToTimeline(self, rows):
        self.calls.append(rows)
        return [Clip(r, self.inclusive) for r in rows]


class Timeline:
    def __init__(self): self.deleted = []
    def DeleteClips(self, clips, ripple):
        assert ripple is False
        self.deleted.extend(clips)
        return True


@pytest.mark.parametrize('inclusive', [0, 1])
def test_video_audio_exact_exclusive_bounds_calibrated(inclusive):
    pool, timeline = Pool(inclusive), Timeline()
    segment = dict(source_in_frame=10, source_out_frame=40, edited_in_frame=0, edited_out_frame=30)
    clips, convention = append_exact_segment(pool, timeline, object(), segment, 108000)
    assert convention == inclusive
    assert [(c.GetStart(), c.GetEnd()) for c in clips] == [(108000, 108030)] * 2
    assert [r['mediaType'] for r in pool.calls[-1]] == [1, 2]
    assert len(timeline.deleted) == inclusive * 2
    segment.update(source_in_frame=60, source_out_frame=80, edited_in_frame=30, edited_out_frame=50)
    clips, _ = append_exact_segment(pool, timeline, object(), segment, 108000, convention=convention)
    assert [(c.GetStart(), c.GetEnd()) for c in clips] == [(108030, 108050)] * 2


def test_failed_rollback_reports_partial_timeline_instead_of_silent_retry():
    from types import SimpleNamespace
    from backend.app.resolve_native_cut import delete_owned_native_cut
    project = SimpleNamespace(SetCurrentTimeline=lambda _: True)
    pool = SimpleNamespace(DeleteTimelines=lambda _: False)
    timeline = SimpleNamespace(GetName=lambda: 'partial CUT', GetUniqueId=lambda: 'partial-id')
    with pytest.raises(RuntimeError, match='partial-id'):
        delete_owned_native_cut(project, pool, timeline, object(), {})


def test_selective_media_refresh_preserves_excluded_social_and_generics():
    from types import SimpleNamespace
    from backend.app.resolve_textplus_timeline import remove_prior_rambla_broll
    def clip(provider, color):
        media = SimpleNamespace(GetMetadata=lambda: {'Keywords': 'RAMBLA, ' + provider})
        return SimpleNamespace(GetMediaPoolItem=lambda: media, GetClipColor=lambda: color)
    stock, social, generic = clip('pexels', 'Purple'), clip('youtube_shorts', 'Purple'), clip('pexels', 'Beige')
    removed = []
    timeline = SimpleNamespace(GetTrackCount=lambda _: 1, GetItemListInTrack=lambda *_: [stock, social, generic],
        DeleteClips=lambda clips, ripple: removed.extend(clips) or True)
    count, tracks = remove_prior_rambla_broll(timeline, {'broll': True, 'social': False, 'generic': False})
    assert removed == [stock]
    assert count == 1 and tracks == [1]


def test_finished_timeline_is_recovered_after_receipt_failure(tmp_path):
    from types import SimpleNamespace
    from backend.app.resolve_native_cut import record_native_cut_result, recover_native_cut_result
    source = tmp_path / 'original.mp4'
    source.write_bytes(b'original')
    stat = source.stat()
    cut = dict(source_path=str(source), source_identity=dict(size=stat.st_size, mtime_ns=stat.st_mtime_ns),
               segments=[dict(source_in_frame=0, source_out_frame=20, edited_in_frame=0, edited_out_frame=20)])
    media = SimpleNamespace(GetClipProperty=lambda _: str(source))
    item = SimpleNamespace(GetStart=lambda: 100, GetEnd=lambda: 120, GetSourceStartFrame=lambda: 0,
                           GetSourceEndFrame=lambda: 20, GetMediaPoolItem=lambda: media)
    timeline = SimpleNamespace(GetUniqueId=lambda: 'owned-id', GetStartFrame=lambda: 100,
                               GetItemListInTrack=lambda *_: [item])
    active = []
    project = SimpleNamespace(GetName=lambda: 'TEST', GetTimelineCount=lambda: 1,
                              GetTimelineByIndex=lambda _: timeline, SetCurrentTimeline=lambda t: active.append(t))
    payload = dict(native_cut=cut, handoff_progress_path=str(tmp_path / 'progress.json'))
    result = dict(timeline_id='owned-id', timeline_name='finished CUT')
    record_native_cut_result(project, payload, result)
    assert recover_native_cut_result(project, payload) == result
    assert active == [timeline]
    source.write_bytes(b'replaced')
    with pytest.raises(ValueError, match='modificato'):
        recover_native_cut_result(project, payload)


def test_fractional_timeline_setting_falls_back_to_resolve_ntsc_enum_and_verifies_rate():
    from backend.app.resolve_native_cut import configure_native_timeline
    class Timeline:
        values = {}
        def SetSettings(self, values):
            if values.get('timelineFrameRate') == '29.97': return False
            self.values.update(values)
            return True
        def GetSettings(self):
            return {**self.values, 'timelineFrameRate': 29.97}
    timeline = Timeline()
    configure_native_timeline(timeline, dict(fps='30000/1001', width=1080, height=1920))
    assert timeline.values['timelineFrameRate'] == '29'
    assert timeline.values['timelineDropFrameTimecode'] == '0'
