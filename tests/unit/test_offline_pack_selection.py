import json
import io
import zipfile

import pytest

from backend.app.media_pack_export import create_media_pack
from backend.app.curation_project import ProjectStore
from backend.app.curation_server import create_app
from fastapi.testclient import TestClient


def test_offline_pack_respects_component_flags_and_includes_explicit_original(tmp_path):
    root=tmp_path/'project'; root.mkdir()
    original=tmp_path/'original.mp4'; original.write_bytes(b'original')
    video=root/'broll.mp4'; video.write_bytes(b'broll')
    plan={'fps':25,'duration_frames':25,'clips':[{'asset_id':'x','beat_id':'b','provider':'pexels',
          'title':'B-roll','media_path':str(video),'track_index':2,'record_start_frame':0,
          'record_end_frame':25,'source_start_frame':0,'source_end_frame':25,'duration_frames':25}]}
    out=tmp_path/'out.zip'
    create_media_pack(out,project_id='x',project_name='test',project_root=root,timeline=plan,
      source_video_path=str(original),captions_srt='one',titles=[{'text':'hello'}],
      components={'source_video':True,'subtitles':False,'highlights':False,'broll':False,'social':False,'generic':False,'video':False})
    with zipfile.ZipFile(out) as z:
        names=z.namelist()
        assert z.read('00_VIDEO_ORIGINALE/original.mp4') == b'original'
        assert not any(name.startswith('01_FRASI/') for name in names)
        assert '03_RESOLVE/sottotitoli.srt' not in names
        assert '03_RESOLVE/titoli_e_testi.json' not in names
        assert json.loads(z.read('manifest.json'))['components']['source_video'] is True


def test_offline_pack_does_not_claim_to_export_native_cut_it_cannot_build(tmp_path):
    root=tmp_path/'project'; root.mkdir()
    with pytest.raises(ValueError,match='CUT'):
        create_media_pack(tmp_path/'out.zip',project_id='x',project_name='test',project_root=root,
            timeline={'fps':25,'duration_frames':1,'clips':[]},components={'video':True})


def test_zip_endpoint_uses_submitted_options(tmp_path):
    projects=tmp_path/'projects'
    source=tmp_path/'my-original.mp4';source.write_bytes(b'my-video')
    probe=lambda _: {'duration':1,'fps':25,'width':320,'height':180,'has_audio':True}
    store=ProjectStore(projects,probe_runner=probe)
    project=store.create('Selections')
    store.register_local_video(project.project_id,source)
    client=TestClient(create_app(project_root=projects,probe_runner=probe))
    r=client.post(f'/api/curation/projects/{project.project_id}/exports/media-pack.zip',
                  json={'source_video':True,'subtitles':False,'highlights':False,'broll':False,'social':False,'generic':False,'video':False})
    assert r.status_code==200, r.text
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        assert z.read('00_VIDEO_ORIGINALE/my-original.mp4') == b'my-video'
        assert '03_RESOLVE/sottotitoli.srt' not in z.namelist()


def test_dra_endpoint_uses_selected_components_without_resolve(tmp_path,monkeypatch):
    projects=tmp_path/'projects';source=tmp_path/'source.mp4';source.write_bytes(b'video')
    probe=lambda _: {'duration':1,'fps':25,'width':320,'height':180,'has_audio':True}
    store=ProjectStore(projects,probe_runner=probe);project=store.create('Dra')
    store.register_local_video(project.project_id,source)
    seen={}
    def writer(payload,path):
        seen.update(payload)
        with zipfile.ZipFile(path,'w') as z:z.writestr('Dra.dra/project.drp',b'fixture')
    monkeypatch.setattr('backend.app.offline_resolve_archive.create_offline_resolve_archive',writer)
    client=TestClient(create_app(project_root=projects,probe_runner=probe))
    r=client.post(f'/api/curation/projects/{project.project_id}/exports/media-pack.zip?include_dra=true',
                  json={'source_video':True,'subtitles':False,'highlights':False,'broll':False,'social':False,'generic':False,'video':False})
    assert r.status_code==200,r.text
    assert seen['original_video']['source_path']==str(source.resolve())
    assert seen['titles']==[] and seen['subtitles']==[]
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:assert 'Dra.dra/project.drp' in z.namelist()
