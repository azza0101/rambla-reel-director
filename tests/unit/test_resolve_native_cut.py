import pytest
from backend.app.resolve_native_cut import append_exact_segment


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
