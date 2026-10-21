from pathlib import Path
import json
import pytest
from fastapi.testclient import TestClient
from tests.unit.test_cut_pass_routes import tmp_path

TOKEN='test-session-private'

def client_for(root):
    from backend.app.autocut_service import create_app
    return TestClient(create_app(root, token=TOKEN, probe_runner=lambda p:{'duration':10,'fps':30,'width':1920,'height':1080,'has_audio':True}))

def test_worker_requires_session_and_has_no_bridge_routes(tmp_path):
    client=client_for(tmp_path)
    assert client.get('/autocut').status_code==403
    client.headers['X-Autocut-Session']=TOKEN
    assert client.get('/autocut/health').json()['service']=='rmbl-autocut'
    assert client.get('/api/curation/resolve-handoffs/pending').status_code==404
    html=client.get('/autocut').text
    assert 'cutTakeDialog' in html and 'cutPauseStrong' in html
    assert 'integrationImport' in html and 'integrationApply' in html


def test_source_is_reused_only_for_same_timeline_and_physical_file(tmp_path):
    client=client_for(tmp_path);client.headers['X-Autocut-Session']=TOKEN
    source=tmp_path/'original.mp4';source.write_bytes(b'original')
    payload={'path':str(source),'project_name':'TEST','timeline_id':'timeline-1','timeline_name':'Full video'}
    first=client.post('/autocut/source',json=payload)
    assert first.status_code==200,first.text
    assert client.post('/autocut/source',json=payload).json()['project_id']==first.json()['project_id']
    source.write_bytes(b'changed-video')
    assert client.post('/autocut/source',json=payload).json()['project_id']!=first.json()['project_id']
    assert source.read_bytes()==b'changed-video'


def test_no_source_and_no_cut_never_produce_an_apply_payload(tmp_path):
    client=client_for(tmp_path);client.headers['X-Autocut-Session']=TOKEN
    assert client.post('/autocut/source',json={'path':str(tmp_path/'missing.mp4'),'project_name':'T','timeline_id':'x','timeline_name':'x'}).status_code==422
    assert client.get('/autocut/projects/../native-cut').status_code in (404,422)


def test_apply_refuses_a_different_open_timeline_before_native_calls(monkeypatch):
    from types import SimpleNamespace as Obj
    from backend.app.autocut_apply import apply_payload
    import backend.app.resolve_native_cut as native
    calls=[]
    monkeypatch.setattr(native,'create_native_cut_base',lambda *a,**k:calls.append(True))
    resolve=Obj(GetProjectManager=lambda:Obj(GetCurrentProject=lambda:Obj(GetName=lambda:'TEST',GetCurrentTimeline=lambda:Obj(GetUniqueId=lambda:'different'))))
    payload={'context':{'project_name':'TEST','timeline_id':'original'},'native_cut':{'fps':'30','source_duration_frames':30,'duration_frames':30,'segments':[{'source_in_frame':0,'source_out_frame':30,'edited_in_frame':0,'edited_out_frame':30}]}}
    with pytest.raises(RuntimeError,match='Timeline Resolve cambiata'):apply_payload(resolve,payload)
    assert calls==[]


def test_apply_reuses_existing_native_engine(monkeypatch):
    from types import SimpleNamespace as Obj
    from backend.app.autocut_apply import apply_payload
    import backend.app.resolve_native_cut as native
    cut={'fps':'30','source_duration_frames':30,'duration_frames':30,'segments':[{'source_in_frame':0,'source_out_frame':30,'edited_in_frame':0,'edited_out_frame':30}]}
    calls=[]
    def existing(resolve,project,payload,**kwargs):
        calls.append(payload['native_cut']);return {'timeline':object(),'timeline_name':'CUT','timeline_id':'new'}
    monkeypatch.setattr(native,'create_native_cut_base',existing)
    resolve=Obj(GetProjectManager=lambda:Obj(GetCurrentProject=lambda:Obj(GetName=lambda:'TEST',GetCurrentTimeline=lambda:Obj(GetUniqueId=lambda:'original'))))
    result=apply_payload(resolve,{'context':{'project_name':'TEST','timeline_id':'original'},'native_cut':cut})
    assert calls==[cut] and result=={'timeline_name':'CUT','timeline_id':'new'}


def test_installer_copies_local_sdk_and_preserves_data(tmp_path):
    import sys
    from tools.install_autocut_integration import install
    app=tmp_path/'app';app.mkdir()
    import shutil
    shutil.copytree(Path('tools/autocut_integration'),app/'tools'/'autocut_integration')
    sdk=tmp_path/'WorkflowIntegration.node';sdk.write_bytes(b'local-native-sdk')
    plugins=tmp_path/'Plugins';data=tmp_path/'data';data.mkdir();(data/'keep.json').write_text('saved choices')
    target=install(app,plugins,data,python=Path(sys.executable),sdk=sdk)
    assert target.name=='com.rambla.autocut'
    assert (target/'WorkflowIntegration.node').read_bytes()==sdk.read_bytes()
    assert (data/'keep.json').read_text()=='saved choices'
    config=json.loads((target/'runtime.json').read_text('utf-8'))
    assert set(config)=={'app_root','python','data_root'}
    assert not (target/'test_source_adapter.js').exists()


def test_new_worker_does_not_expose_confirm_child_or_editorial(tmp_path):
    client=client_for(tmp_path);client.headers['X-Autocut-Session']=TOKEN
    assert client.post('/api/curation/projects/aaaaaaaaaaaa/cut/confirm',json={}).status_code==404
    assert client.post('/api/curation/projects/aaaaaaaaaaaa/director',json={}).status_code==404
    assert client.get('/autocut/busy').json()=={'busy':False}


def test_native_payload_rejects_a_revision_changed_during_prepare(tmp_path,monkeypatch):
    import backend.app.native_cut_export as native
    client=client_for(tmp_path);client.headers['X-Autocut-Session']=TOKEN
    source=tmp_path/'source.mp4';source.write_bytes(b'original')
    project=client.post('/autocut/source',json={'path':str(source),'project_name':'T','timeline_id':'original','timeline_name':'Full'}).json()
    folder=tmp_path/'projects'/project['project_id']/'cut';folder.mkdir()
    (folder/'plan.json').write_text(json.dumps({'revision':'requested'}),'utf-8')
    monkeypatch.setattr(native,'load_native_cut',lambda *args:{'revision':'newer'})
    response=client.get('/autocut/projects/'+project['project_id']+'/native-cut?revision=requested')
    assert response.status_code==409


def test_shutdown_refuses_while_apply_is_running(tmp_path):
    client=client_for(tmp_path);client.headers['X-Autocut-Session']=TOKEN
    client.app.state.autocut_apply_jobs['x']={'status':'running'}
    assert client.post('/autocut/shutdown').status_code==409


def test_session_restores_the_same_saved_project_after_worker_restart(tmp_path):
    client=client_for(tmp_path);client.headers['X-Autocut-Session']=TOKEN
    source=tmp_path/'source.mp4';source.write_bytes(b'original')
    context={'path':str(source),'project_name':'T','timeline_id':'original','timeline_name':'Full'}
    project=client.post('/autocut/source',json=context).json()
    second=client_for(tmp_path);second.headers['X-Autocut-Session']=TOKEN
    restored=second.get('/autocut/session').json()
    assert restored['project']['project_id']==project['project_id']
    assert restored['context']==context


def test_autocut_has_private_diagnostics_and_respects_automatic_optout(tmp_path):
    from backend.app.autocut_service import create_app
    from fastapi.testclient import TestClient
    app=create_app(tmp_path,token=TOKEN,probe_runner=lambda _: {},enable_automatic_diagnostics=True)
    reporter=app.state.diagnostics
    assert reporter.settings()['automatic'] is True
    reporter.set_automatic(False,start_worker=False)
    again=create_app(tmp_path,token=TOKEN,probe_runner=lambda _: {},enable_automatic_diagnostics=True)
    assert again.state.diagnostics.settings()['automatic'] is False
    client=TestClient(again);client.headers['X-Autocut-Session']=TOKEN
    assert client.get('/api/curation/diagnostics').status_code==200
    assert 'rmblSupportOpen' in client.get('/autocut').text


def test_apply_ui_uses_isolated_backend_validation_not_blocking_native_sdk():
    from backend.app.autocut_ui import AFTER
    handler=AFTER.split("$('integrationApplyGo').onclick=async()=>{",1)[1].split("$('integrationUpdate').onclick",1)[0]
    assert '.snapshot(' not in handler
    assert "'/projects/'+state.pid+'/apply'" in handler


def test_apply_destination_is_validated_and_defaults_to_new():
    from backend.app.autocut_service import ApplyRequest
    from pydantic import ValidationError
    assert ApplyRequest(revision='r').destination=='new'
    assert ApplyRequest(revision='r',destination='active').destination=='active'
    with pytest.raises(ValidationError):ApplyRequest(revision='r',destination='anything')


def test_apply_popup_is_styled_and_offers_both_destinations():
    from backend.app.autocut_ui import render_autocut,AFTER
    html=render_autocut()
    assert 'id="integrationApplyDialog"' in html
    assert 'name="applyDestination" value="active"' in html
    assert 'name="applyDestination" value="new"' in html
    assert 'if(!confirm(' not in AFTER


def test_source_ranges_have_distinct_projects_and_do_not_overwrite_full_video(tmp_path):
    client=client_for(tmp_path);client.headers['X-Autocut-Session']=TOKEN
    source=tmp_path/'original.mp4';source.write_bytes(b'original')
    context={'path':str(source),'project_name':'TEST','timeline_id':'timeline','timeline_name':'Full'}
    full=client.post('/autocut/source',json=context).json()
    selected=client.post('/autocut/source',json={**context,'source_range':{'in_frame':30,'out_frame':180,'fps':'30'}}).json()
    assert full['project_id']!=selected['project_id']
    assert selected['source_video']['path']==full['source_video']['path']
    again=client.post('/autocut/source',json=context).json()
    assert again['project_id']==full['project_id']
    invalid=client.post('/autocut/source',json={**context,'source_range':{'in_frame':200,'out_frame':400,'fps':'30'}})
    assert invalid.status_code==422
