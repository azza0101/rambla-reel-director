from backend.app.resolve_textplus_timeline import conform_broll_media
import pytest


def test_video_broll_is_never_converted_even_with_unaligned_trim(monkeypatch, tmp_path):
    source = tmp_path / 'mixed-rate.webm'
    source.write_bytes(b'original')
    monkeypatch.setattr('backend.app.resolve_textplus_timeline.probe_preview', lambda _: {'duration': 10})
    def forbidden(*args, **kwargs):
        raise AssertionError('video conversion or frame scan must not be started')
    monkeypatch.setattr('backend.app.resolve_textplus_timeline.subprocess.run', forbidden)
    row = conform_broll_media([{'media_path':str(source),'record_start_frame':10,'record_end_frame':41,
                               'source_start_frame':13,'source_end_frame':44}], 30)[0]
    assert row['media_path'] == str(source)
    assert row['source_start_frame'] == 13 and row['source_end_frame'] == 44
    assert source.read_bytes() == b'original'


def test_native_rate_mapping_is_sent_to_resolve_and_duration_is_verified():
    from backend.app.resolve_textplus_timeline import append_broll_clips
    class Imported:
        def GetClipProperty(self, name): return '25'
    class Placed:
        def GetStart(self): return 100
        def GetEnd(self): return 130
    class Timeline:
        def GetTrackCount(self, kind): return 2
    class Pool:
        def __init__(self): self.rows=[]
        def ImportMedia(self, paths): return [Imported()]
        def AppendToTimeline(self, rows): self.rows.extend(rows); return [Placed()]
    pool=Pool()
    row={'media_path':'original.mp4','asset_id':'a','track_index':2,
         'source_start_frame':30,'record_start_frame':0,'record_end_frame':30}
    assert append_broll_clips(pool,Timeline(),[row],base_frame=100,fps=30)==1
    assert pool.rows[0]['startFrame']==25 and pool.rows[0]['endFrame']==50
    Placed.GetEnd=lambda self: 129
    with pytest.raises(RuntimeError, match='durata'):
        append_broll_clips(pool,Timeline(),[row],base_frame=100,fps=30)
