from tests.unit.test_cut_pass_routes import tmp_path
import asyncio
from pathlib import Path
from types import SimpleNamespace
import pytest
from backend.app.envato_auto_download import EnvatoSession,valid_url


def test_only_envato_https_item_urls_are_allowed():
    assert valid_url('https://elements.envato.com/item-123')
    assert valid_url('https://app.envato.com/stock-video/abc')
    for url in ('http://elements.envato.com/item','https://envato.com.evil.test/x','https://evil.test/x','https://user@elements.envato.com/x','https://elements.envato.com:broken/x'):
        assert not valid_url(url)


def test_download_uses_exact_event_and_attaches_asset(tmp_path,monkeypatch):
    import backend.app.social_page_evidence as evidence
    import backend.app.envato_auto_download as auto
    monkeypatch.setattr(evidence,'challenge_required',lambda html:False)
    monkeypatch.setattr(auto,'valid_video',lambda path:True)
    class Download:
        suggested_filename='file.mp4'
        async def save_as(self,path):Path(path).write_bytes(b'valid video')
        async def failure(self):return None
    class Page:
        url='https://elements.envato.com/item'
        async def goto(self,*a,**k):pass
        async def wait_for_timeout(self,*a):pass
        async def content(self):return 'signed in'
        def on(self,event,cb):self.cb=cb
        async def evaluate(self,script,name):self.cb(Download());return {'ok':True}
        async def close(self):pass
    page=Page()
    class Context:
        async def new_page(self):return page
    session=EnvatoSession(tmp_path/'profile')
    async def context():return Context()
    session._context=context
    result=asyncio.run(session.download(page.url,'My project',tmp_path/'run','beat-1'))
    assert result['status']=='ready'
    assert Path(result['media_path']).read_bytes()==b'valid video'
    import json
    registry=json.loads((tmp_path/'run/envato-downloads.json').read_text('utf-8'))
    assert registry['assets']['beat-1']['license_project']=='My project'


def test_failed_licensing_never_creates_registry(tmp_path,monkeypatch):
    import backend.app.social_page_evidence as evidence
    monkeypatch.setattr(evidence,'challenge_required',lambda html:False)
    class Page:
        url='https://elements.envato.com/item'
        async def goto(self,*a,**k):pass
        async def wait_for_timeout(self,*a):pass
        async def content(self):return ''
        def on(self,*a):pass
        async def evaluate(self,*a):return {'ok':False,'errore':'accesso richiesto'}
        async def close(self):pass
    class Context:
        async def new_page(self):return Page()
    session=EnvatoSession(tmp_path/'profile')
    async def context():return Context()
    session._context=context
    with pytest.raises(RuntimeError,match='accesso richiesto'):
        asyncio.run(session.download('https://elements.envato.com/item','Project',tmp_path/'run','beat-1'))
    assert not (tmp_path/'run/envato-downloads.json').exists()
def test_full_length_mov_is_valid_media_and_missing_video_is_rejected(tmp_path):
    import shutil,subprocess
    from backend.app.envato_auto_download import valid_video
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):pytest.skip('ffmpeg tools unavailable')
    media=tmp_path/'full.mov'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=black:size=64x64:rate=2','-t','6','-c:v','mpeg4',str(media)],check=True,capture_output=True)
    assert valid_video(media)
    invalid=tmp_path/'bad.mp4';invalid.write_bytes(b'not a video')
    assert not valid_video(invalid)

def test_auto_api_accepts_only_existing_envato_asset_and_runs_job(tmp_path,monkeypatch):
    import time
    from fastapi.testclient import TestClient
    from types import SimpleNamespace
    import backend.app.curation_artifacts as artifacts
    import backend.app.envato_auto_download as auto
    from backend.app.curation_project import ProjectStore
    from backend.app.curation_server import create_app
    store=ProjectStore(tmp_path,probe_runner=lambda path:{})
    project=store.create('Project test')
    candidate=SimpleNamespace(provider='envato',source_page='https://elements.envato.com/item')
    monkeypatch.setattr(artifacts,'load_curation_run',lambda run:SimpleNamespace(candidate_index={'asset-123':candidate}))
    async def download(self,url,project_name,run_root,asset_id):
        assert project_name=='Project test' and asset_id=='asset-123'
        return {'status':'ready','asset_id':asset_id}
    monkeypatch.setattr(auto.EnvatoSession,'download',download)
    with TestClient(create_app(project_root=tmp_path)) as client:
        base='/api/curation/projects/'+project.project_id+'/envato/auto'
        assert client.post(base+'/start',json={'asset_id':'unknown-123'}).status_code==404
        response=client.post(base+'/start',json={'asset_id':'asset-123'})
        assert response.status_code==200
        token=response.json()['token']
        for _ in range(30):
            result=client.get(base+'/'+token).json()
            if result['status']=='ready':break
            time.sleep(.02)
        assert result['status']=='ready' and result['asset_id']=='asset-123'
