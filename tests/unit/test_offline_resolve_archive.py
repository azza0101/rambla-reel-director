import json
import zipfile
from xml.etree import ElementTree as ET

import pytest

from backend.app.offline_resolve_archive import create_offline_resolve_archive


def test_offline_title_preserves_kura_preset_and_includes_its_resources(tmp_path):
    import io
    import struct
    import zlib
    source=tmp_path/'source.mp4';source.write_bytes(b'video')
    payload={'project_name':'Kura','fps':30,'original_video':{'source_path':str(source),'width':320,'height':180,'duration_frames':90},
             'titles':[{'text':'National Geographic','start_frame':5,'end_frame':50}]}
    probe=lambda _: {'fps':30,'width':320,'height':180,'duration_frames':90,'has_audio':False}
    out=tmp_path/'kura.zip';create_offline_resolve_archive(payload,out,probe_media=probe)
    with zipfile.ZipFile(out) as archive:
        assert 'KURA_Paper_Text_Optimized.drfx' in archive.namelist()
        assert 'Installa KURA Windows.cmd' in archive.namelist()
        assert 'Installa KURA Mac.command' in archive.namelist()
        assert 'Installa KURA Windows.ps1' in archive.namelist()
        with zipfile.ZipFile(io.BytesIO(archive.read('Kura.dra/project.drp'))) as project:
            name=next(n for n in project.namelist() if n.startswith('SeqContainer/'))
            tree=ET.fromstring(project.read(name))
            clip=next(x for x in tree.findall('.//Sm2TiVideoClip') if x.findtext('PrettyType')=='Fusion Title')
            raw=bytes.fromhex(clip.findtext('.//CompositionBA'))
            outer=zlib.decompress(raw[4:]);mark=outer.rfind(b'Compressed = true, }');offset=outer.find(b'\0',mark)+1
            composition_start=outer.index(b'Composition {')
            assert struct.unpack('>I',outer[composition_start-4:composition_start])[0] == len(outer)-composition_start
            comp=zlib.decompress(outer[offset+4:]).decode('utf8')
            assert 'Template = TextPlus' in comp
            assert b'KURA_Paper_Text_Optimized' in bytes.fromhex(clip.findtext('.//Sm2TiCompositionTable/FieldsBlob'))
            assert 'StyledText = Input { Value = "National\\nGeographic"' in comp
            assert 'Font = Input { Value = "Montserrat"' in comp
            assert 'Style = Input { Value = "Black"' in comp
        with zipfile.ZipFile(io.BytesIO(archive.read('KURA_Paper_Text_Optimized.drfx'))) as preset:
            assert any(n.endswith('/paper.jpg') for n in preset.namelist())
        with zipfile.ZipFile(io.BytesIO(archive.read('Kura.dra/project.drp'))) as project:
            seq=next(n for n in project.namelist() if n.startswith('SeqContainer/'))
            clip=next(x for x in ET.fromstring(project.read(seq)).findall('.//Sm2TiVideoClip') if x.findtext('PrettyType')=='Fusion Title')
            outer=zlib.decompress(bytes.fromhex(clip.findtext('.//CompositionBA'))[4:])
            assert b'ResolveCaches:' not in outer and b'LastFile =' not in outer


def test_optimized_effect_installer_bundle_installs_the_effect(tmp_path):
    import os
    import subprocess
    from backend.app.kura_text_effect import build_effect_install_bundle
    if os.name != 'nt': pytest.skip('Windows installer')
    bundle=build_effect_install_bundle(tmp_path/'effect.zip')
    with zipfile.ZipFile(bundle) as archive: archive.extractall(tmp_path)
    env=dict(os.environ,APPDATA=str(tmp_path/'appdata'))
    run=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(tmp_path/'Installa KURA Windows.ps1')],env=env,capture_output=True,text=True,timeout=30)
    assert run.returncode == 0,run.stderr
    root=tmp_path/'appdata'/'Blackmagic Design'/'DaVinci Resolve'/'Support'/'Fusion'/'Templates'
    assert (root/'Edit'/'Effects'/'KURA_Paper_Text_Optimized'/'KURA_Paper_Text_Optimized.setting').is_file()


def test_offline_title_composition_covers_the_whole_clip(tmp_path):
    import io
    import zlib
    source=tmp_path/'source.mp4'; source.write_bytes(b'video')
    payload={'project_name':'Long','fps':30,'original_video':{'source_path':str(source),'width':320,'height':180,'duration_frames':240},
             'titles':[{'text':'Una frase lunga','start_frame':10,'end_frame':110}]}
    probe=lambda _: {'fps':30,'width':320,'height':180,'duration_frames':240,'has_audio':False}
    archive=tmp_path/'long.zip'; create_offline_resolve_archive(payload,archive,probe_media=probe)
    with zipfile.ZipFile(archive) as z, zipfile.ZipFile(io.BytesIO(z.read('Long.dra/project.drp'))) as p:
        seq=next(n for n in p.namelist() if n.startswith('SeqContainer/'))
        clip=next(x for x in ET.fromstring(p.read(seq)).findall('.//Sm2TiVideoClip') if x.findtext('PrettyType')=='Fusion Title')
        outer=zlib.decompress(bytes.fromhex(clip.findtext('.//CompositionBA'))[4:])
        assert b'RenderRange = { 0, 99 }' in outer
        pos=outer.index(b'Compressed = true, }'); offset=outer.index(b'\0',pos)+1
        assert b'GlobalOut = Input { Value = 99' in zlib.decompress(outer[offset+4:])


def test_unverified_long_effect_is_rejected(tmp_path):
    source=tmp_path/'source.mp4';source.write_bytes(b'video')
    payload={'project_name':'Long','fps':30,'original_video':{'source_path':str(source),'width':320,'height':180,'duration_frames':240},
             'titles':[{'text':'Una frase lunga','start_frame':10,'end_frame':190}]}
    probe=lambda _: {'fps':30,'width':320,'height':180,'duration_frames':240,'has_audio':False}
    with pytest.raises(ValueError,match='125 fotogrammi'):
        create_offline_resolve_archive(payload,tmp_path/'long.zip',probe_media=probe)


def test_windows_installer_is_idempotent_and_preserves_conflicts(tmp_path):
    import os
    import shutil
    import subprocess
    from backend.app.offline_resolve_archive import KURA_PRESET, KURA_INSTALLER
    if os.name != 'nt': pytest.skip('Windows installer')
    package=tmp_path/'KURA_paper_title_v9_STANDALONE_FIXED.drfx'
    shutil.copyfile(KURA_PRESET,package)
    script=tmp_path/'Installa KURA Windows.ps1'
    shutil.copyfile(KURA_INSTALLER/script.name,script)
    env=dict(os.environ,APPDATA=str(tmp_path/'appdata'))
    command=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script)]
    first=subprocess.run(command,env=env,capture_output=True,text=True,timeout=30)
    assert first.returncode==0,first.stderr
    second=subprocess.run(command,env=env,capture_output=True,text=True,timeout=30)
    assert second.returncode==0 and 'gia presente' in second.stdout,second.stderr
    root=tmp_path/'appdata'/'Blackmagic Design'/'DaVinci Resolve'/'Support'/'Fusion'/'Templates'
    installed=root/'Edit'/'Titles'/'KURA_paper_title_v9'/'paper.jpg'
    installed.write_bytes(b'personalized')
    (root/package.name).unlink()
    third=subprocess.run(command,env=env,capture_output=True,text=True,timeout=30)
    assert third.returncode!=0
    assert installed.read_bytes()==b'personalized'


def test_windows_installer_accepts_existing_package_and_title_without_overwriting(tmp_path):
    import os
    import shutil
    import subprocess
    from backend.app.offline_resolve_archive import KURA_PRESET, KURA_INSTALLER
    if os.name != 'nt': pytest.skip('Windows installer')
    package=tmp_path/'KURA_paper_title_v9_STANDALONE_FIXED.drfx';shutil.copyfile(KURA_PRESET,package)
    script=tmp_path/'Installa KURA Windows.ps1';shutil.copyfile(KURA_INSTALLER/script.name,script)
    root=tmp_path/'appdata'/'Blackmagic Design'/'DaVinci Resolve'/'Support'/'Fusion'/'Templates'
    root.mkdir(parents=True);shutil.copyfile(package,root/package.name)
    setting=root/'Edit'/'Titles'/'KURA_paper_title_v9'/'KURA_paper_title_v9.setting'
    setting.parent.mkdir(parents=True);setting.write_bytes(b'existing-custom-title')
    env=dict(os.environ,APPDATA=str(tmp_path/'appdata'))
    run=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script)],env=env,capture_output=True,text=True,timeout=30)
    assert run.returncode==0,run.stderr
    assert setting.read_bytes()==b'existing-custom-title'


def test_archive_contains_native_timed_tracks_and_relink_index(tmp_path):
    source=tmp_path/'source.mp4';source.write_bytes(b'original-video')
    cover=tmp_path/'cover.mp4';cover.write_bytes(b'coverage')
    payload={'project_name':'Test','fps':30,'duration_seconds':6,
             'original_video':{'source_path':str(source),'fps':'30','width':320,'height':180,'duration_frames':180,'has_audio':True},
             'broll_clips':[{'asset_id':'b1','media_path':str(cover),'track_index':2,
                             'record_start_frame':30,'record_end_frame':90,'source_start_frame':45,'enabled':False}],
             'subtitles':[{'text':'Ciao & buongiorno','start_frame':15,'end_frame':45}],
             'titles':[{'text':'Parola chiave','start_frame':30,'end_frame':75}],
             'generic_broll_clips':[]}
    def probe(path):
        return {'fps':30,'width':320,'height':180,'duration_frames':180,'has_audio':True,'channels':1,'sample_rate':48000}
    dest=tmp_path/'archive.zip'
    create_offline_resolve_archive(payload,dest,probe_media=probe)
    with zipfile.ZipFile(dest) as z:
        assert z.read('Test.dra/MediaFiles/source.mp4')==b'original-video'
        assert z.read('Test.dra/MediaFiles/cover.mp4')==b'coverage'
        import io
        with zipfile.ZipFile(io.BytesIO(z.read('Test.dra/project.drp'))) as p:
            mdat=p.read('media.dat')
            assert str(source).encode() in mdat and str(cover).encode() in mdat
            key=next(x for x in p.namelist() if x.startswith('SeqContainer/'))
            text=p.read(key).decode()
            assert 'Ciao &amp; buongiorno' in text
            assert '<PrettyType>Fusion Title</PrettyType>' in text
            tree=ET.fromstring(text)
            assert len(tree.findall('VideoTrackVec/Element/Sm2TiTrack'))>=3
            assert tree.findall('VideoTrackVec/Element/Sm2TiTrack')[1].findtext('Items/Element/Sm2TiVideoClip/Flags')=='2'
            assert len(tree.findall('AudioTrackVec/Element/Sm2TiTrack'))==1
            assert tree.findtext('.//SubtitleTrackVec/Element/Sm2TiTrack/Items/Element/Sm2TiGenerator/Start')=='15'


def test_coverage_creates_all_requested_tracks_and_titles_are_above_them(tmp_path):
    import io
    source=tmp_path/'source.mp4'; source.write_bytes(b'video')
    clips=[]
    for index in (2,3,5):
        path=tmp_path/f'coverage-{index}.mp4';path.write_bytes(b'video')
        clips.append({'asset_id':str(index),'media_path':str(path),'track_index':index,
                      'record_start_frame':10,'record_end_frame':40,'source_start_frame':0})
    payload={'project_name':'Layers','fps':30,'original_video':{'source_path':str(source),'width':320,'height':180,'duration_frames':120},
             'broll_clips':clips,'titles':[{'text':'Ciao','start_frame':10,'end_frame':40}]}
    probe=lambda _: {'fps':30,'width':320,'height':180,'duration_frames':120,'has_audio':False}
    out=tmp_path/'layers.zip';create_offline_resolve_archive(payload,out,probe_media=probe)
    with zipfile.ZipFile(out) as z,zipfile.ZipFile(io.BytesIO(z.read('Layers.dra/project.drp'))) as p:
        key=next(n for n in p.namelist() if n.startswith('SeqContainer/'))
        tracks=ET.fromstring(p.read(key)).findall('VideoTrackVec/Element/Sm2TiTrack')
        assert len(tracks)==6
        assert tracks[1].findtext('.//Sm2TiVideoClip/Name')=='coverage-2.mp4'
        assert tracks[2].findtext('.//Sm2TiVideoClip/Name')=='coverage-3.mp4'
        assert tracks[3].find('.//Sm2TiVideoClip') is None
        assert tracks[4].findtext('.//Sm2TiVideoClip/Name')=='coverage-5.mp4'
        assert tracks[5].findtext('.//Sm2TiVideoClip/PrettyType')=='Fusion Title'


def test_archive_rejects_missing_media_instead_of_fake_success(tmp_path):
    payload={'project_name':'Test','fps':30,'broll_clips':[{'media_path':str(tmp_path/'missing.mp4')}], 'subtitles':[],'titles':[]}
    with pytest.raises(ValueError,match='disponibile'):
        create_offline_resolve_archive(payload,tmp_path/'out.zip')


def test_archive_rejects_ambiguous_duplicate_filenames(tmp_path):
    a=tmp_path/'a';b=tmp_path/'b';a.mkdir();b.mkdir();(a/'clip.mp4').write_bytes(b'1');(b/'clip.mp4').write_bytes(b'2')
    payload={'project_name':'Test','fps':30,'broll_clips':[{'media_path':str(a/'clip.mp4')},{'media_path':str(b/'clip.mp4')}],'titles':[],'subtitles':[]}
    with pytest.raises(ValueError,match='nome'):
        create_offline_resolve_archive(payload,tmp_path/'out.zip')


def test_native_cut_segments_keep_source_offsets_and_audio(tmp_path):
    source=tmp_path/'long.mp4';source.write_bytes(b'video')
    cut={'source_path':str(source),'fps':'25','width':320,'height':180,'source_has_audio':True,
         'duration_frames':100,'segments':[{'source_in_frame':25,'source_out_frame':75,'edited_in_frame':0,'edited_out_frame':50},
                                          {'source_in_frame':150,'source_out_frame':200,'edited_in_frame':50,'edited_out_frame':100}]}
    payload={'project_name':'Cut','fps':25,'duration_seconds':4,'native_cut':cut}
    probe=lambda _: {'fps':25,'width':320,'height':180,'duration_frames':250,'has_audio':True,'channels':1,'sample_rate':48000}
    out=tmp_path/'cut.zip';create_offline_resolve_archive(payload,out,probe_media=probe)
    import io
    with zipfile.ZipFile(out) as z,zipfile.ZipFile(io.BytesIO(z.read('Cut.dra/project.drp'))) as p:
        seq=next(x for x in p.namelist() if x.startswith('SeqContainer/'))
        tree=ET.fromstring(p.read(seq))
        video=tree.findall('VideoTrackVec/Element/Sm2TiTrack/Items/Element/Sm2TiVideoClip')
        audio=tree.findall('AudioTrackVec/Element/Sm2TiTrack/Items/Element/Sm2TiAudioClip')
        assert [(x.findtext('Start'),x.findtext('Duration'),x.findtext('In')) for x in video]==[('0','50','25'),('50','50','150')]
        assert len(audio)==2


def test_unverified_video_codec_is_rejected(tmp_path):
    source=tmp_path/'hevc.mp4';source.write_bytes(b'video')
    payload={'project_name':'Test','fps':25,'original_video':{'source_path':str(source),'width':320,'height':180,'duration_frames':25}}
    probe=lambda _: {'fps':25,'width':320,'height':180,'duration_frames':25,'codec':'hevc'}
    with pytest.raises(ValueError,match='codec non supportato'):
        create_offline_resolve_archive(payload,tmp_path/'out.zip',probe_media=probe)


def test_unverified_stereo_is_rejected(tmp_path):
    source=tmp_path/'stereo.mp4';source.write_bytes(b'video')
    payload={'project_name':'Stereo','fps':25,'original_video':{'source_path':str(source),'width':320,'height':180,'duration_frames':25,'has_audio':True}}
    probe=lambda _: {'fps':25,'width':320,'height':180,'duration_frames':25,'has_audio':True,'channels':2,'sample_rate':48000}
    with pytest.raises(ValueError,match='audio stereo'):
        create_offline_resolve_archive(payload,tmp_path/'out.zip',probe_media=probe)
