import json
import time
import uuid
import pytest
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient

from backend.app.cut_pass_routes import install_cut_routes
from backend.app.cut_pass import build_cut_plan
from tests.unit.test_cut_pass import transcript


@pytest.fixture
def tmp_path():
    # Windows host rejects pytest's private 0700 temp directories.
    path=Path('.test-tmp')/('cut-'+uuid.uuid4().hex)
    path.mkdir(parents=True)
    return path.resolve()


def test_cut_jobs_persist_proposal_allow_review_and_reject_stale_source(tmp_path,monkeypatch):
    import backend.app.cut_pass_routes as module
    import backend.app.cloud_analyze_cli as asr
    raw=transcript([(1,3,'prima frase'),(5,7,'prima frase completa')])
    p=SimpleNamespace(source_video=SimpleNamespace(path=str(tmp_path/'source.mp4'),has_audio=True,duration=8,fps=30),
        analysis_signature='original')
    calls=[]
    monkeypatch.setattr(asr,'transcribe_groq',lambda *a:calls.append(a) or raw)
    monkeypatch.setattr(module,'propose_groups',lambda t:[{'takes':[[0,1],[2,4]],'confidence':.95,'reason':'correzione'}])
    monkeypatch.setattr(module,'choose_complete_takes',lambda raw,groups:groups)
    app=FastAPI()
    def load(pid):
        if pid!='p':raise HTTPException(404)
        return p
    install_cut_routes(app,None,tmp_path,load,lambda _:None)
    with TestClient(app) as client:
        assert client.post('/api/curation/projects/p/cut/analyze').status_code==200
        for _ in range(100):
            data=client.get('/api/curation/projects/p/cut').json()
            if data['job']['status']!='running':break
            time.sleep(.01)
        assert data['job']['status']=='succeeded',data
        assert data['text']=='prima frase completa'
        revision=data['plan']['revision']
        response=client.put('/api/curation/projects/p/cut',json={'revision':revision,'selected_takes':{'0':0}})
        assert response.status_code==200
        assert response.json()['text']=='prima frase'
        assert client.put('/api/curation/projects/p/cut',json={'revision':revision}).status_code==409
        assert client.get('/api/curation/projects/p/cut/preview/../../project.json').status_code==404
        p.analysis_signature='changed'
        assert client.get('/api/curation/projects/p/cut').status_code==409
    assert len(calls)==1
    assert not (tmp_path/'p'/'run'/'transcript-raw.json').exists()


def test_cut_preview_renders_exact_source_ranges_with_original_audio(tmp_path,monkeypatch):
    from backend.app.cut_pass_routes import render_cut
    from backend.app import cut_pass_routes as module
    raw=transcript([(1,2,'a b'),(5,6,'c d')])
    plan=build_cut_plan(raw,duration=7,fps=30,signature='s',groups=[])
    calls=[]
    monkeypatch.setattr(module.subprocess,'run',lambda command,**kw:calls.append(command))
    render_cut(tmp_path/'original.mp4',tmp_path/'preview.mp4',plan,preview=True)
    graph=(tmp_path/'preview.fffilter').read_text()
    assert 'gte(n,24)*lt(n,66)' in graph
    assert 'atrim=start=0.800000000:end=2.200000000' in graph
    assert 'concat=n=2:v=0:a=1' in graph
    assert calls[0][calls[0].index('-i')+1]==str(tmp_path/'original.mp4')


def test_cut_panel_is_optional_and_precedes_word_selection():
    from backend.app.curation_ui_v2 import render_curation_page_v2
    html=render_curation_page_v2('cut')
    assert html.index('id="cutPassPanel"')<html.index('id="transcriptWorkspaceV14"')
    assert 'id="cutPassFold"' in html
    assert 'CONFERMA CUT E CONTINUA' in html


def test_cut_page_javascript_parses():
    import re,shutil,subprocess
    from backend.app.curation_ui_v2 import render_curation_page_v2
    node=shutil.which('node')
    if not node:pytest.skip('node unavailable')
    html=render_curation_page_v2('cut-js')
    scripts='\n'.join(re.findall(r'<script>(.*?)</script>',html,re.S))
    result=subprocess.run([node,'--check'],input=scripts,text=True,encoding='utf-8',capture_output=True)
    assert result.returncode==0,result.stderr


def test_actual_cut_render_has_exact_frame_count_and_audio(tmp_path):
    import shutil,subprocess
    from backend.app.cut_pass_routes import render_cut
    if not shutil.which('ffmpeg'):pytest.skip('ffmpeg unavailable')
    source=tmp_path/'source.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=red:s=160x240:r=30:d=4',
        '-f','lavfi','-i','sine=frequency=440:duration=4','-c:v','libx264','-pix_fmt','yuv420p',
        '-c:a','aac',str(source)],check=True,capture_output=True)
    raw=transcript([(.5,1,'prima frase'),(2.5,3,'seconda frase')])
    plan=build_cut_plan(raw,duration=4,fps=30,signature='s',groups=[])
    target=tmp_path/'clean.mp4';render_cut(source,target,plan)
    result=subprocess.run(['ffprobe','-v','error','-count_frames','-show_entries',
        'stream=codec_type,nb_read_frames','-of','json',str(target)],check=True,capture_output=True,text=True)
    streams=json.loads(result.stdout)['streams']
    assert int(next(s for s in streams if s['codec_type']=='video')['nb_read_frames'])==plan['duration_frames']
    assert any(s['codec_type']=='audio' for s in streams)


def test_confirm_creates_independent_clean_project_with_reusable_timing(tmp_path,monkeypatch):
    import shutil,subprocess
    from backend.app import cut_pass_routes as module
    from backend.app.curation_project import ProjectStore
    from backend.app.debug_server import _probe_source_video
    from backend.app.atomic_io import write_json
    from backend.app.analysis_reuse import ensure_analysis_ready
    if not shutil.which('ffmpeg'):pytest.skip('ffmpeg unavailable')
    source=tmp_path/'original.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=red:s=160x240:r=30:d=4',
        '-f','lavfi','-i','sine=frequency=440:duration=4','-c:v','libx264','-pix_fmt','yuv420p',
        '-c:a','aac',str(source)],check=True,capture_output=True)
    root=tmp_path/'projects';store=ProjectStore(root,probe_runner=_probe_source_video)
    original=store.create('original');original=store.register_local_video(original.project_id,source)
    raw=transcript([(.5,1,'prima frase'),(2.5,3,'frase corretta')])
    folder=root/original.project_id/'cut';folder.mkdir()
    plan=build_cut_plan(raw,duration=4,fps=30,signature=original.analysis_signature,
        groups=[{'takes':[[0,1],[2,3]],'confidence':.95,'reason':'ripartenza'}])
    write_json(folder/'plan.json',plan);write_json(folder/'transcript-original.json',raw)
    app=FastAPI();install_cut_routes(app,store,root,store.load,lambda _:None)
    prefix='/api/curation/projects/'+original.project_id+'/cut'
    with TestClient(app) as client:
        response=client.post(prefix+'/confirm',json={'revision':plan['revision']})
        assert response.status_code==200
        for _ in range(500):
            data=client.get(prefix).json()
            if data['job']['status']!='running':break
            time.sleep(.01)
        assert data['job']['status']=='succeeded',data
        child=store.load(data['job']['result']['project_id'])
    assert child.project_id!=original.project_id
    assert Path(child.source_video.path).parent==root/child.project_id/'source'
    child_run=root/child.project_id/'run'
    assert ensure_analysis_ready(child_run,child)
    assert json.loads((child_run/'transcript-raw.json').read_text())['text']=='frase corretta'
    assert store.load(original.project_id).source_video.path==str(source.resolve())
    assert (root/child.project_id/'cut-origin.json').is_file()


def test_cut_project_cannot_send_compacted_times_to_unchanged_resolve_timeline(tmp_path):
    from backend.app.curation_server import create_app
    from backend.app.curation_project import ProjectStore
    root=tmp_path/'projects';store=ProjectStore(root,probe_runner=lambda _: {})
    p=store.create('CUT');(root/p.project_id/'cut-origin.json').write_text('{}')
    app=create_app(project_root=root,allowed_media_roots=[tmp_path])
    with TestClient(app) as client:
        response=client.post(f'/api/curation/projects/{p.project_id}/resolve-preparation')
        assert response.status_code==409
        assert 'fase successiva' in response.json()['detail']
