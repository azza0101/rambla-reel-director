import json
from types import SimpleNamespace


def test_custom_search_groups_pexels_and_envato_and_keeps_selection(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.curation_project import ProjectStore
    from backend.app.curation_server import create_app
    from backend.app.online_assets import PexelsSource
    from backend.app.envato_source import EnvatoSource
    root=tmp_path/'projects';p=ProjectStore(root,probe_runner=lambda _:{}).create('Test')
    run=root/p.project_id/'run';run.mkdir(exist_ok=True)
    def row(provider, pid):
        return SimpleNamespace(provider=provider,provider_id=pid,query='rome',source_page='https://elements.envato.com/item-ABCDEF' if provider=='envato' else 'https://pexels.com/video/123',title='Rome',description='Rome',duration=8,width=1280,height=720,orientation='landscape',preview_url='https://example.com/a.jpg',selected_rendition_url='https://example.com/a.mp4',provider_rank=1)
    async def pexels(self,*args,**kwargs):return [row('pexels','123')]
    async def envato(self,*args,**kwargs):return [row('envato','abc')]
    monkeypatch.setattr(PexelsSource,'search',pexels);monkeypatch.setattr(EnvatoSource,'search',envato)
    app=create_app(project_root=root)
    with TestClient(app) as c:
        base=f'/api/curation/projects/{p.project_id}/generic-coverage'
        result=c.get(base,params={'scope':'custom','manual_query':'rome','refresh':True})
        assert result.status_code==200, result.text
        rows=result.json()['items']; assert {r['provider'] for r in rows}=={'pexels','envato'}
        assert {r['provider_id'] for r in rows}=={'123','envato:abc'}
        assert c.put(base+'/selection',json={'provider_ids':['123','envato:abc']}).status_code==200
        assert set(c.get(base).json()['selected'])=={'123','envato:abc'}


def test_ui_groups_custom_and_refreshes_export():
    from backend.app.timeline_export_ui import PANEL, JS
    assert 'CUSTOM B-ROLL' in PANEL and 'customCoverageV138' in PANEL
    assert 'customPexelsCardsV138' in PANEL and 'customEnvatoCardsV138' in PANEL
    assert 'await loadResolveComponentsV71()' in JS


def test_window_reopens_after_build_changes():
    from pathlib import Path
    source=Path('tools/focus_rambla_app.ps1').read_text(encoding='utf8')
    assert 'rambla-window-build.txt' in source
    assert '$savedBuild -ne $build' in source


def test_selected_envato_custom_download_is_added_to_export_media(tmp_path, monkeypatch):
    import asyncio
    from backend.app.curation_project import ProjectStore
    from backend.app.curation_server import create_app
    from backend.app.envato_auto_download import EnvatoSession
    from backend.app import video_preview
    root=tmp_path/'projects';p=ProjectStore(root,probe_runner=lambda _:{}).create('Test')
    run=root/p.project_id/'run';run.mkdir(exist_ok=True)
    path=run/'generic-coverage.json'
    path.write_text(json.dumps({'items':[{'provider':'envato','provider_id':'envato:abc','title':'Rome','source_page':'https://elements.envato.com/item-ABCDEF','duration':20}], 'selected':['envato:abc']}))
    async def download(self,url,name,folder,asset_id,progress=None):
        assert name=='Test' and asset_id=='generic:envato:abc'
        video=folder/'envato-ready.mp4';video.write_bytes(b'fixture');return {'media_path':str(video)}
    monkeypatch.setattr(EnvatoSession,'download',download)
    monkeypatch.setattr('backend.app.media_export_quality.require_editing_quality',lambda path:{'duration':9,'playable':True,'width':1920,'height':1080})
    app=create_app(project_root=root)
    assert asyncio.run(app.state.prepare_generic_media(p.project_id))==[]
    row=json.loads(path.read_text())['items'][0]
    assert row['media_path'].endswith('envato-ready.mp4') and row['duration']==9

def test_custom_search_keeps_selected_existing_pexels_in_both_groups(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.curation_project import ProjectStore
    from backend.app.curation_server import create_app
    from backend.app.online_assets import PexelsSource
    from backend.app.envato_source import EnvatoSource
    root=tmp_path/'projects';p=ProjectStore(root,probe_runner=lambda _:{}).create('Test')
    run=root/p.project_id/'run';run.mkdir(exist_ok=True)
    (run/'generic-coverage.json').write_text(json.dumps({'items':[{'provider':'pexels','provider_id':'123','coverage_group':'topic'}], 'selected':['123']}))
    async def pexels(self,*a,**kw):return [SimpleNamespace(provider='pexels',provider_id='123',query='rome',source_page='https://pexels.com/video/123',title='Rome',description='Rome',duration=8,width=1280,height=720,orientation='landscape',preview_url='https://example.com/a.jpg',selected_rendition_url='https://example.com/a.mp4',provider_rank=1)]
    async def envato(self,*a,**kw):return []
    monkeypatch.setattr(PexelsSource,'search',pexels);monkeypatch.setattr(EnvatoSource,'search',envato)
    with TestClient(create_app(project_root=root)) as c:
        r=c.get(f'/api/curation/projects/{p.project_id}/generic-coverage',params={'scope':'custom','manual_query':'rome','refresh':True})
        assert r.status_code==200
        assert set(r.json()['items'][0]['coverage_groups'])=={'topic','custom'}
        assert r.json()['selected']==['123']

def test_selected_custom_envato_reaches_resolve_handoff(tmp_path, monkeypatch):
    import time
    from fastapi.testclient import TestClient
    from backend.app.curation_project import ProjectStore
    from backend.app.curation_server import create_app
    from backend.app.envato_auto_download import EnvatoSession
    from backend.app import video_preview
    root=tmp_path/'projects';p=ProjectStore(root,probe_runner=lambda _:{}).create('Test')
    run=root/p.project_id/'run';run.mkdir(exist_ok=True)
    (run/'generic-coverage.json').write_text(json.dumps({'items':[{'provider':'envato','provider_id':'envato:abc','title':'Rome','source_page':'https://elements.envato.com/item-ABCDEF','duration':20}], 'selected':['envato:abc']}))
    async def download(self,url,name,folder,asset_id,progress=None):
        video=folder/'envato-ready.mp4';video.write_bytes(b'fixture');return {'media_path':str(video)}
    monkeypatch.setattr(EnvatoSession,'download',download)
    monkeypatch.setattr('backend.app.media_export_quality.require_editing_quality',lambda path:{'duration':9,'playable':True,'width':1920,'height':1080})
    flags={'video':False,'source_video':False,'subtitles':False,'highlights':False,'broll':False,'social':False,'generic':True}
    with TestClient(create_app(project_root=root)) as c:
        r=c.post(f'/api/curation/projects/{p.project_id}/resolve-preparation',json=flags)
        assert r.status_code==200, r.text
        job=r.json()
        for _ in range(100):
            job=c.get('/api/curation/resolve-preparation/'+job['job_id']).json()
            if job['status']!='preparing':break
            time.sleep(.02)
        assert job['status']=='ready', job
        assert job['package']['summary']['generic_broll_count']==1
        assert job['package']['media_issues']==[]


def test_interactive_envato_error_opens_page_and_retry_completes(tmp_path, monkeypatch):
    import time
    from fastapi.testclient import TestClient
    from backend.app.curation_project import ProjectStore
    from backend.app.curation_server import create_app
    from backend.app.envato_auto_download import EnvatoSession
    from backend.app import video_preview
    root=tmp_path/'projects';p=ProjectStore(root,probe_runner=lambda _:{}).create('Test')
    run=root/p.project_id/'run';run.mkdir(exist_ok=True)
    url='https://elements.envato.com/item-ABCDEF'
    (run/'generic-coverage.json').write_text(json.dumps({'items':[{'provider':'envato','provider_id':'envato:abc','title':'Rome','source_page':url,'duration':20}], 'selected':['envato:abc']}))
    calls=[];opened=[]
    async def download(self,*args,**kwargs):
        calls.append(1)
        if len(calls)==1:raise RuntimeError('Envato non ha risposto entro 50 secondi')
        video=run/'envato-ready.mp4';video.write_bytes(b'fixture');return {'media_path':str(video)}
    async def login(self,source):opened.append(source);return {'status':'opened'}
    monkeypatch.setattr(EnvatoSession,'download',download);monkeypatch.setattr(EnvatoSession,'login',login)
    monkeypatch.setattr('backend.app.media_export_quality.require_editing_quality',lambda path:{'duration':9,'playable':True,'width':1920,'height':1080})
    flags={'video':False,'source_video':False,'subtitles':False,'highlights':False,'broll':False,'social':False,'generic':True}
    with TestClient(create_app(project_root=root)) as c:
        r=c.post(f'/api/curation/projects/{p.project_id}/resolve-preparation?interactive=true',json=flags);assert r.status_code==200
        path='/api/curation/resolve-preparation/'+r.json()['job_id']
        for _ in range(200):
            job=c.get(path).json()
            if job['status']=='waiting_user':break
            time.sleep(.01)
        assert job['status']=='waiting_user' and job['issue']['provider']=='envato'
        assert c.post(path+'/open-source').json()['status']=='opened' and opened==[url]
        assert c.post(path+'/decision?choice=retry').status_code==200
        for _ in range(200):
            job=c.get(path).json()
            if job['status']!='preparing':break
            time.sleep(.01)
        assert job['status']=='ready',job
        assert job['package']['summary']['generic_broll_count']==1

def test_cancel_from_api_discards_only_downloaded_this_run(tmp_path, monkeypatch):
    import asyncio,time,hashlib
    from fastapi.testclient import TestClient
    from backend.app.curation_project import ProjectStore
    from backend.app.curation_server import create_app
    from backend.app.envato_auto_download import EnvatoSession
    from backend.app import video_preview
    root=tmp_path/'projects';p=ProjectStore(root,probe_runner=lambda _:{}).create('Test')
    run=root/p.project_id/'run';run.mkdir(exist_ok=True)
    old=run/'user-file.mp4';old.write_bytes(b'keep')
    rows=[{'provider':'envato','provider_id':'envato:'+x,'title':x,'source_page':'https://elements.envato.com/item-ABCDEF','duration':20} for x in ('a','b')]
    (run/'generic-coverage.json').write_text(json.dumps({'items':rows,'selected':['envato:a','envato:b']}))
    async def download(self,url,name,folder,asset_id,progress=None):
        if asset_id.endswith(':b'):
            if progress: progress('Registrazione licenza')
            await asyncio.Event().wait()
        token=hashlib.sha256(asset_id.encode()).hexdigest()[:20];dest=folder/'envato-media'/token/'original.mp4';dest.parent.mkdir(parents=True);dest.write_bytes(b'new')
        (folder/'envato-downloads.json').write_text(json.dumps({'assets':{asset_id:{'media_path':str(dest)}}}))
        return {'media_path':str(dest)}
    monkeypatch.setattr(EnvatoSession,'download',download);monkeypatch.setattr('backend.app.media_export_quality.require_editing_quality',lambda path:{'duration':9,'playable':True,'width':1920,'height':1080})
    flags={'video':False,'source_video':False,'subtitles':False,'highlights':False,'broll':False,'social':False,'generic':True}
    with TestClient(create_app(project_root=root)) as c:
        r=c.post(f'/api/curation/projects/{p.project_id}/resolve-preparation?interactive=true',json=flags);assert r.status_code==200
        path='/api/curation/resolve-preparation/'+r.json()['job_id']
        for _ in range(200):
            job=c.get(path).json()
            if (job.get('media') or {}).get('asset_id')=='generic:envato:b':break
            time.sleep(.01)
        assert (job.get('media') or {}).get('asset_id')=='generic:envato:b'
        result=c.post(path+'/cancel?keep_cached=false').json()
        assert result['status']=='cancelled' and old.read_bytes()==b'keep'
        assert not list((run/'envato-media').rglob('*.mp4'))
        assert not json.loads((run/'envato-downloads.json').read_text())['assets']


def test_cancel_keep_then_resume_reuses_envato_completed_files(tmp_path, monkeypatch):
    import asyncio,time,hashlib
    from fastapi.testclient import TestClient
    from backend.app.curation_project import ProjectStore
    from backend.app.curation_server import create_app
    from backend.app.envato_auto_download import EnvatoSession
    from backend.app import envato_auto_download as auto,video_preview
    root=tmp_path/'projects';p=ProjectStore(root,probe_runner=lambda _:{}).create('Test')
    run=root/p.project_id/'run';run.mkdir(exist_ok=True)
    rows=[{'provider':'envato','provider_id':'envato:'+x,'title':x,'source_page':'https://elements.envato.com/item-ABCDEF','duration':20} for x in ('a','b')]
    (run/'generic-coverage.json').write_text(json.dumps({'items':rows,'selected':['envato:a','envato:b']}));calls=[]
    async def download(self,url,name,folder,asset_id,progress=None):
        calls.append(asset_id)
        if asset_id.endswith(':b') and calls.count(asset_id)==1:
            if progress:progress('Registrazione licenza')
            await asyncio.Event().wait()
        token=hashlib.sha256(asset_id.encode()).hexdigest()[:20];dest=folder/'envato-media'/token/'original.mp4';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b'new')
        reg=folder/'envato-downloads.json';data=json.loads(reg.read_text()) if reg.exists() else {'assets':{}}
        data['assets'][asset_id]={'media_path':str(dest)};reg.write_text(json.dumps(data));return {'media_path':str(dest)}
    monkeypatch.setattr(EnvatoSession,'download',download);monkeypatch.setattr('backend.app.media_export_quality.require_editing_quality',lambda path:{'duration':9,'playable':True,'width':1920,'height':1080})
    monkeypatch.setattr(auto,'valid_video',lambda path:bool(path) and __import__('pathlib').Path(path).is_file())
    flags={'video':False,'source_video':False,'subtitles':False,'highlights':False,'broll':False,'social':False,'generic':True}
    with TestClient(create_app(project_root=root)) as c:
        base=f'/api/curation/projects/{p.project_id}/resolve-preparation?interactive=true'
        first=c.post(base,json=flags).json();path='/api/curation/resolve-preparation/'+first['job_id']
        for _ in range(200):
            job=c.get(path).json()
            if (job.get('media') or {}).get('asset_id')=='generic:envato:b':break
            time.sleep(.01)
        assert c.post(path+'/cancel?keep_cached=true').json()['status']=='cancelled'
        second=c.post(base,json=flags).json();path='/api/curation/resolve-preparation/'+second['job_id']
        for _ in range(200):
            job=c.get(path).json()
            if job['status']!='preparing':break
            time.sleep(.01)
        assert job['status']=='ready',job
        assert job['package']['summary']['generic_broll_count']==2
        assert calls.count('generic:envato:a')==1 and calls.count('generic:envato:b')==2
