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
    monkeypatch.setattr(video_preview,'probe_full_video',lambda path:{'duration':9})
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
    monkeypatch.setattr(video_preview,'probe_full_video',lambda path:{'duration':9})
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
