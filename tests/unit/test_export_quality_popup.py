import asyncio
import io
import zipfile
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from backend.app.curation_project import ProjectStore
from backend.app.curation_server import create_app

FLAGS={'source_video':False,'video':False,'subtitles':False,'highlights':False,'broll':True,'social':False,'generic':False}

def test_zip_warns_before_delivery_and_can_continue_without_bad_clips(tmp_path):
    root=tmp_path/'projects'; project=ProjectStore(root,probe_runner=lambda _:{}).create('Test')
    app=create_app(project_root=root)
    route=next(r for r in app.routes if r.path.endswith('/exports/media-pack.zip'))
    env=dict(zip(route.endpoint.__code__.co_freevars,route.endpoint.__closure__))
    env['broll_timeline_payload'].cell_contents=lambda *a,**k: {'fps':25,'duration_frames':25,'clips':[], 'unavailable':[{'asset_id':'pexels:1','title':'Clip sgranata','reason':'Video 640x360: richiesti almeno 720p'}]}
    client=TestClient(app); path=f'/api/curation/projects/{project.project_id}/exports/media-pack.zip'
    response=client.post(path,json=FLAGS)
    assert response.status_code==409
    assert '640x360' in str(response.json()['detail'])
    signature=response.json()['detail']['signature']
    response=client.post(path+'?accept_missing=true&accepted_signature='+signature,json=FLAGS)
    assert response.status_code==200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert b'640x360' in archive.read('00_AVVISO_MEDIA_MANCANTI.txt')

def test_youtube_low_resolution_prompts_before_bridge(tmp_path, monkeypatch):
    import json
    import backend.app.curation_artifacts as artifacts
    import backend.app.transcript_intents as intents
    import backend.app.social_media as social
    from backend.app.media_export_quality import MediaQualityError
    root=tmp_path/'projects'; p=ProjectStore(root,probe_runner=lambda _:{}).create('Test')
    run=root/p.project_id/'run'; run.mkdir(exist_ok=True)
    (run/'selection-plan.json').write_text(json.dumps({'chunks':{'beat':{'selected_assets':[{'asset_id':'one'}]}}}))
    candidate=SimpleNamespace(asset_id='one',chunk_id='beat',provider='youtube_shorts',kind='video',title='Clip',source_page='https://www.youtube.com/shorts/test',local_asset_path=None,preview_path=None)
    monkeypatch.setattr(artifacts,'load_curation_run',lambda _:SimpleNamespace(candidate_index={'one':candidate}))
    monkeypatch.setattr(intents,'has_selected_intent',lambda *a:True)
    def fail(*a,**kw):raise MediaQualityError('Video 640x360: richiesti almeno 720p')
    monkeypatch.setattr(social,'prepare_media',fail)
    seen=[]
    def report(*args): pass
    async def issue(row):seen.append(row);return 'ignore'
    report.interactive=True;report.issue=issue
    app=create_app(project_root=root)
    errors=asyncio.run(app.state.prepare_selected_timeline_media(p.project_id,report=report))
    assert seen and seen[0]['reason']=='low_resolution'
    assert errors[0]['asset_id']=='one'

def test_dra_requests_decision_and_records_skipped_clip(tmp_path,monkeypatch):
    root=tmp_path/'projects';project=ProjectStore(root,probe_runner=lambda _:{}).create('Test')
    app=create_app(project_root=root)
    route=next(r for r in app.routes if r.path.endswith('/exports/media-pack.zip'))
    env=dict(zip(route.endpoint.__code__.co_freevars,route.endpoint.__closure__))
    issue={'asset_id':'pexels:1','title':'Clip sgranata','message':'Video 640x360: richiesti almeno 720p','reason':'low_resolution'}
    async def prepare(*a,**kw):return [issue]
    env['prepare_selected_timeline_media'].cell_contents=prepare
    excluded=[]
    def payload(project_id,flags,ignored):
        excluded.append(set(ignored))
        return {'broll_unavailable':[]}
    env['editing_resolve_payload'].cell_contents=payload
    def writer(payload,path):
        with zipfile.ZipFile(path,'w') as z:z.writestr('Test.dra/project.drp',b'fixture')
    monkeypatch.setattr('backend.app.offline_resolve_archive.create_offline_resolve_archive',writer)
    client=TestClient(app);path=f'/api/curation/projects/{project.project_id}/exports/media-pack.zip?include_dra=true'
    response=client.post(path,json=FLAGS)
    assert response.status_code==409 and response.json()['detail']['issues'][0]['message']==issue['message']
    assert excluded==[{'pexels:1'}]
    signature=response.json()['detail']['signature']
    response=client.post(path+'&accept_missing=true&accepted_signature='+signature,json=FLAGS)
    assert response.status_code==200 and excluded==[{'pexels:1'}, {'pexels:1'}]
    assert response.headers['X-Rambla-Missing-Count']=='1'
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        assert b'640x360' in z.read('00_AVVISO_MEDIA_MANCANTI.txt')

def test_popup_choices_control_zip_delivery():
    import json, shutil, subprocess
    from backend.app.timeline_export_ui import JS
    node=shutil.which('node')
    if not node: pytest.skip('Node non disponibile')
    start=JS.index('function showZipIssuesV164(')
    end=JS.index("$('exportMediaPackV125').onclick=exportMediaPackV125;",start)
    source=JS[start:end]
    harness=r'''
const vm=require('vm'); const source=process.argv[1];
async function scenario(choice){
 const elements={}; let calls=[],downloads=0,listed=[];
 function $(id){return elements[id]||(elements[id]={id,checked:false,disabled:false,open:false,textContent:'',children:[],replaceChildren(){this.children=[]},append(x){this.children.push(x);listed.push(x.textContent)},showModal(){this.open=true;queueMicrotask(()=>$(choice==='continue'?'zipIssueContinueV164':choice==='cancel'?'zipIssueCancelV164':'zipIssueRetryV164').onclick())},close(){this.open=false}})}
 const ctx={state:{pid:'p',run:false},resolveComponentsV71:{broll:true},$,console,URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},setTimeout(){},document:{body:{append(){}},createElement(type){return type==='a'?{click(){downloads++},remove(){}}:{textContent:''}}},fetch:async url=>{calls.push(url);return calls.length===1?{status:409,ok:false,json:async()=>({detail:{code:'media_issues',signature:'sig',issues:[{title:'Clip',reason:'640x360'}]}})}:{status:200,ok:true,blob:async()=>({}),headers:{get:()=> '1'}}}};
 vm.runInNewContext(source,ctx);await ctx.exportMediaPackV125();return {calls,downloads,listed,status:$('timelineExportStatusV33').textContent,disabled:$('exportMediaPackV125').disabled};
}
(async()=>{for(const choice of ['continue','cancel','retry']){const r=await scenario(choice); if(!r.listed[0].includes('640x360')||r.disabled)throw Error(choice+JSON.stringify(r));if(choice==='cancel'&&(r.calls.length!==1||r.downloads))throw Error(JSON.stringify(r));if(choice!=='cancel'&&(r.calls.length!==2||r.downloads!==1||!r.calls[1].includes('accept_missing='+(choice==='continue'))))throw Error(JSON.stringify(r));} })().catch(e=>{console.error(e);process.exit(1)});
'''
    result=subprocess.run([node,'-e',harness,source],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr

def test_new_problem_after_confirmation_requires_another_decision(tmp_path):
    root=tmp_path/'projects';project=ProjectStore(root,probe_runner=lambda _:{}).create('Test')
    app=create_app(project_root=root)
    route=next(r for r in app.routes if r.path.endswith('/exports/media-pack.zip'))
    env=dict(zip(route.endpoint.__code__.co_freevars,route.endpoint.__closure__))
    problems=[{'asset_id':'pexels:1','title':'Clip 1','reason':'640x360'}]
    env['broll_timeline_payload'].cell_contents=lambda *a,**k: {'fps':25,'duration_frames':25,'clips':[],'unavailable':problems}
    client=TestClient(app);path=f'/api/curation/projects/{project.project_id}/exports/media-pack.zip'
    initial=client.post(path,json=FLAGS);signature=initial.json()['detail']['signature']
    problems.append({'asset_id':'pexels:2','title':'Clip 2','reason':'480x270'})
    response=client.post(path+'?accept_missing=true&accepted_signature='+signature,json=FLAGS)
    assert response.status_code==409 and len(response.json()['detail']['issues'])==2
