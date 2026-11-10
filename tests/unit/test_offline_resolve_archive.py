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
             'titles':[{'text':'National\nGeographic','start_frame':5,'end_frame':50}]}
    probe=lambda _: {'fps':30,'width':320,'height':180,'duration_frames':90,'has_audio':False}
    out=tmp_path/'kura.zip';create_offline_resolve_archive(payload,out,probe_media=probe)
    with zipfile.ZipFile(out) as archive:
        assert 'KURA_paper_title_v9_STANDALONE_FIXED.drfx' in archive.namelist()
        with zipfile.ZipFile(io.BytesIO(archive.read('Kura.dra/project.drp'))) as project:
            name=next(n for n in project.namelist() if n.startswith('SeqContainer/'))
            tree=ET.fromstring(project.read(name))
            clip=next(x for x in tree.findall('.//Sm2TiVideoClip') if x.findtext('PrettyType')=='Fusion Title')
            raw=bytes.fromhex(clip.findtext('.//CompositionBA'))
            outer=zlib.decompress(raw[4:]);mark=outer.rfind(b'Compressed = true, }');offset=outer.find(b'\0',mark)+1
            composition_start=outer.index(b'Composition {')
            assert struct.unpack('>I',outer[composition_start-4:composition_start])[0] == len(outer)-composition_start
            comp=zlib.decompress(outer[offset+4:]).decode('utf8')
            assert 'KURA_paper_title_v9 = GroupOperator' in comp
            assert 'StyledText = Input { Value = "National\\nGeographic"' in comp
            assert 'setting:/paper.jpg' in comp
        with zipfile.ZipFile(io.BytesIO(archive.read('KURA_paper_title_v9_STANDALONE_FIXED.drfx'))) as preset:
            assert any(n.endswith('/paper.jpg') for n in preset.namelist())


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
