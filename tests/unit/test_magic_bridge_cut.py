import pytest
from tests.unit.test_resolve_cut_source import snapshot
from tests.unit.test_cut_pass_routes import tmp_path


def test_multitrack_append_uses_original_file_offsets_and_only_owned_clips():
    from backend.app.resolve_native_multitrack import append_mapped_clip
    class Clip:
        def __init__(self,row,adjustment):self.row=row;self.adjustment=adjustment
        def GetStart(self):return self.row['recordFrame']
        def GetEnd(self):return self.GetStart()+self.row['endFrame']-self.row['startFrame']+self.adjustment
        def GetSourceStartFrame(self):return self.row['startFrame']
        def SetProperty(self,values):self.properties=values;return True
        def SetClipEnabled(self,value):self.enabled=value;return True
        def SetSourceAudioChannelMapping(self,value):self.mapping=value;return True
    class Pool:
        def __init__(self):self.rows=[]
        def AppendToTimeline(self,rows):self.rows.extend(rows);return [Clip(rows[0],1)]
    class Timeline:
        def DeleteClips(self,clips,ripple):assert ripple is False;return True
    row=dict(kind='audio',track_index=2,source_in=200,source_out=230,record_in=10,record_out=40,
        enabled=False,properties={'AudioVolume':-3},audio_mapping='{"type":"mono"}')
    pool=Pool();item=append_mapped_clip(pool,Timeline(),object(),row,108000)
    assert item.GetStart()==108010 and item.GetEnd()==108040
    assert not item.enabled and item.mapping=='{"type":"mono"}'
    assert pool.rows[-1]['mediaType']==2 and pool.rows[-1]['trackIndex']==2


def test_snapshot_native_export_never_imports_the_audio_guide_as_video(tmp_path):
    import json
    from backend.app.native_cut_export import load_native_cut
    from backend.app.resolve_cut_source import file_identity
    source=tmp_path/'video.mov';source.write_bytes(b'original')
    data=snapshot();data['signature']='snapshot-signature'
    for track in data['tracks']:
        for clip in track['clips']:clip.update(path=str(source),identity=file_identity(source))
    plan=dict(fps=data['fps'],source_duration_frames=120,duration_frames=60,revision='r',segments=[
        dict(source_in_frame=10,source_out_frame=70,edited_in_frame=0,edited_out_frame=60)])
    child=tmp_path/'child';child.mkdir()
    (child/'cut-origin.json').write_text(json.dumps(dict(plan=plan,source_path='audio-guide.mp4',resolve_source=data)))
    cut=load_native_cut(child,tmp_path)
    assert cut['source_path']=='' and cut['resolve_source']['tracks'][0]['clips'][0]['path']==str(source)
    assert cut['width']==1080 and cut['height']==1920
