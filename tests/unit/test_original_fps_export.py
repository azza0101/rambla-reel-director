import json
import subprocess
from fractions import Fraction
from pathlib import Path
from xml.etree import ElementTree as ET
import pytest


def test_offline_probe_uses_original_nominal_rate(monkeypatch):
    import backend.app.offline_resolve_archive as mod
    data={'streams':[{'codec_type':'video','r_frame_rate':'30000/1001','avg_frame_rate':'29933/1000','width':1920,'height':1080,'duration':'10','nb_frames':'300','codec_name':'h264'}],'format':{}}
    monkeypatch.setattr(mod.subprocess,'run',lambda *a,**k:subprocess.CompletedProcess([],0,json.dumps(data),''))
    assert mod.probe_media(Path('clip.mp4'))['fps']==pytest.approx(30000/1001)


def test_offline_does_not_silently_round_unrepresentable_rate():
    from backend.app.offline_resolve_archive import _rate
    e=ET.Element('clip');_rate(e,30000/1001)
    assert e.findtext('rate/timebase')=='30' and e.findtext('rate/ntsc')=='TRUE'
    with pytest.raises(ValueError,match='fps|FPS'):
        _rate(ET.Element('clip'),29.5)


def test_light_conversion_rejects_changed_fps(tmp_path,monkeypatch):
    import backend.app.envato_light_media as m
    import backend.app.media_export_quality as quality
    source=tmp_path/'source.mp4';source.write_bytes(b'source')
    probes=iter([{'duration':1.,'audio':False,'video':{'width':3840,'height':2160,'codec_name':'h264','nb_frames':'30','r_frame_rate':'30/1','avg_frame_rate':'30/1'}},
                 {'duration':1.,'audio':False,'video':{'width':1920,'height':1080,'codec_name':'h264','nb_frames':'30','r_frame_rate':'25/1','avg_frame_rate':'25/1'}}])
    monkeypatch.setattr(m,'_probe',lambda _:next(probes))
    monkeypatch.setattr(quality,'require_editing_quality',lambda _: {})
    def ffmpeg(cmd,**kwargs):Path(cmd[-1]).write_bytes(b'converted');return subprocess.CompletedProcess(cmd,0)
    monkeypatch.setattr(m.subprocess,'run',ffmpeg)
    with pytest.raises(ValueError,match='fps|FPS'):
        m.prepare_light_media(source,tmp_path/'out')
    assert source.read_bytes()==b'source'
    assert not list((tmp_path/'out').glob('*.mp4'))


def test_cut_rejects_source_with_different_fps_before_render(tmp_path):
    import shutil
    from backend.app.cut_pass_routes import render_cut
    if not shutil.which('ffmpeg'):pytest.skip('ffmpeg unavailable')
    source=tmp_path/'source.mp4';target=tmp_path/'cut.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=red:s=160x120:r=25:d=1','-f','lavfi','-i','sine=duration=1','-c:v','libx264','-c:a','aac',str(source)],check=True,capture_output=True)
    plan={'fps':'30','duration_frames':30,'segments':[{'source_in_frame':0,'source_out_frame':30}]}
    with pytest.raises(ValueError,match='fps|FPS'):
        render_cut(source,target,plan)
    assert not target.exists()

@pytest.mark.parametrize('rate',['25','30000/1001','60000/1001'])
def test_cut_preserves_original_rate_for_real_cfr_video(tmp_path,rate):
    import shutil
    from backend.app.cut_pass_routes import render_cut
    if not shutil.which('ffmpeg'):pytest.skip('ffmpeg unavailable')
    source=tmp_path/'source.mp4';target=tmp_path/'out.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',f'color=red:s=160x120:r={rate}:d=2','-f','lavfi','-i','sine=duration=2','-c:v','libx264','-c:a','aac',str(source)],check=True,capture_output=True)
    frames=int(float(Fraction(rate)))
    plan={'fps':rate,'duration_frames':frames,'segments':[{'source_in_frame':0,'source_out_frame':frames}]}
    render_cut(source,target,plan)
    probe=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=r_frame_rate,nb_frames','-of','json',str(target)],check=True,capture_output=True,text=True)
    stream=json.loads(probe.stdout)['streams'][0]
    assert Fraction(stream['r_frame_rate'])==Fraction(rate)
    assert int(stream['nb_frames'])==frames


def test_cut_refuses_variable_frame_intervals(monkeypatch):
    import backend.app.cut_pass_routes as m
    data={'streams':[{'r_frame_rate':'30/1'}],'packets':[{'pts_time':'0.000'},{'pts_time':'0.033333'},{'pts_time':'0.100'}]}
    monkeypatch.setattr(m.subprocess,'run',lambda *a,**k:subprocess.CompletedProcess([],0,json.dumps(data),''))
    with pytest.raises(ValueError,match='variabili'):
        m.assert_constant_source_fps(Path('vfr.mp4'),'30')

@pytest.mark.parametrize('rate',['30000/1001','60000/1001'])
def test_1080_conversion_keeps_original_rate_and_frames(tmp_path,rate):
    import shutil
    from backend.app.envato_light_media import prepare_light_media
    if not shutil.which('ffmpeg'):pytest.skip('ffmpeg unavailable')
    source=tmp_path/'source.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',f'color=red:s=1920x1200:r={rate}:d=1','-c:v','libx264','-preset','ultrafast',str(source)],check=True,capture_output=True)
    output=prepare_light_media(source,tmp_path/'cache')
    def stream(path):
        return json.loads(subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=r_frame_rate,nb_frames','-of','json',str(path)],capture_output=True,text=True,check=True).stdout)['streams'][0]
    original,converted=stream(source),stream(output)
    assert Fraction(original['r_frame_rate'])==Fraction(converted['r_frame_rate'])==Fraction(rate)
    assert original['nb_frames']==converted['nb_frames']

def test_conversion_rejects_changed_frame_cadence_even_if_count_is_equal(monkeypatch):
    import backend.app.envato_light_media as m
    timestamps=iter([[0,.033,.066,.100],[0,.033,.083,.100]])
    def probe(*args,**kwargs):
        data={'packets':[{'pts_time':str(x)} for x in next(timestamps)]}
        return subprocess.CompletedProcess([],0,json.dumps(data),'')
    monkeypatch.setattr(m.subprocess,'run',probe)
    with pytest.raises(ValueError,match='tempi|fotogrammi'):
        m.assert_unchanged_frame_timing(Path('input.mp4'),Path('output.mp4'))
