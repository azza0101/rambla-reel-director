import asyncio
from types import SimpleNamespace
from pathlib import Path


def test_youtube_settings_and_login_route(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.curation_server import create_app
    from backend.app.desktop_controls_ui import PANEL, JS
    from backend.app.envato_auto_download import EnvatoSession
    seen=[]
    async def login(self,url=''):
        seen.append((self.profile.name,url)); return {'status':'opened','detail':'Accesso YouTube aperto'}
    monkeypatch.setattr(EnvatoSession,'login',login)
    assert 'rmblYouTubeLogin' in PANEL and '/api/curation/youtube/login' in JS
    with TestClient(create_app(project_root=tmp_path/'projects')) as client:
        assert client.post('/api/curation/youtube/login').status_code==200
    assert seen == [('youtube','https://www.youtube.com/')]


def test_youtube_cookie_reader_uses_dedicated_profile(tmp_path, monkeypatch):
    from backend.app.curation_server import create_app
    from backend.app.envato_auto_download import EnvatoSession
    root=tmp_path/'projects'; (tmp_path/'browser-profiles'/'youtube').mkdir(parents=True)
    seen=[]
    async def context(self, **kwargs):
        seen.append(self.profile.name)
        async def cookies(urls):
            assert urls==['https://www.youtube.com/']
            return [{'domain':'.youtube.com','name':'SID','value':'private'}]
        return SimpleNamespace(cookies=cookies)
    monkeypatch.setattr(EnvatoSession,'_context',context)
    app=create_app(project_root=root)
    result=asyncio.run(app.state.youtube_cookie_reader('https://www.youtube.com/shorts/test'))
    assert seen==['youtube'] and result[0]['name']=='SID'
    try: asyncio.run(app.state.youtube_cookie_reader('https://evil.test/x'))
    except ValueError: pass
    else: assert False, 'untrusted URL accepted'


def test_youtube_login_request_does_not_claim_captcha():
    import subprocess
    from backend.app.social_media import prepare_media
    def runner(*a,**kw):raise subprocess.CalledProcessError(1,a,stderr=b'Sign in to confirm you are not a bot')
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        try:prepare_media('https://www.youtube.com/watch?v=test','youtube',Path(temp),'full',runner=runner,python='python')
        except RuntimeError as exc:
            assert 'accesso' in str(exc).lower() and 'captcha' not in str(exc).lower()
        else:assert False

def test_export_passes_youtube_session_cookies(tmp_path, monkeypatch):
    import json
    import backend.app.curation_artifacts as artifacts
    import backend.app.transcript_intents as intents
    import backend.app.social_media as social
    from backend.app.curation_project import ProjectStore
    from backend.app.curation_server import create_app
    from backend.app.envato_auto_download import EnvatoSession
    root=tmp_path/'projects'; project=ProjectStore(root,probe_runner=lambda _:{}).create('Example')
    run=root/project.project_id/'run'; run.mkdir(exist_ok=True)
    (run/'selection-plan.json').write_text(json.dumps({'chunks':{'beat':{'selected_assets':[{'asset_id':'one'}]}}}))
    (tmp_path/'browser-profiles'/'youtube').mkdir(parents=True)
    candidate=SimpleNamespace(asset_id='one',chunk_id='beat',provider='youtube_shorts',kind='video',title='Video',source_page='https://www.youtube.com/shorts/abc',local_asset_path=None,preview_path=None)
    monkeypatch.setattr(artifacts,'load_curation_run',lambda _:SimpleNamespace(candidate_index={'one':candidate}))
    monkeypatch.setattr(intents,'has_selected_intent',lambda *a:True)
    class Context:
        async def cookies(self,urls):return [{'domain':'.youtube.com','name':'SID','value':'private'}]
    async def getcontext(self,**kw):return Context()
    monkeypatch.setattr(EnvatoSession,'_context',getcontext)
    seen=[]
    def prepare(source,provider,run,mode,*,cookies):seen.extend(cookies)
    monkeypatch.setattr(social,'prepare_media',prepare)
    app=create_app(project_root=root)
    assert asyncio.run(app.state.prepare_selected_timeline_media(project.project_id)) == []
    assert len(seen)==1 and seen[0]['name']=='SID'

def test_youtube_session_state_requires_visible_account_element():
    from backend.app.envato_auto_download import session_evidence
    assert session_evidence('youtube','https://www.youtube.com/', '<script>id="avatar-btn"</script>') == 'unknown'
    assert session_evidence('youtube','https://www.youtube.com/', '<button id="avatar-btn" aria-label="Account"></button>') == 'connected'

def test_closed_visible_youtube_session_recovers_headless(tmp_path, monkeypatch):
    from backend.app.curation_server import create_app
    from backend.app.envato_auto_download import EnvatoSession
    root=tmp_path/'projects'; (tmp_path/'browser-profiles'/'youtube').mkdir(parents=True)
    class Dead:
        pages=[]
        async def cookies(self,urls):raise RuntimeError('Target page, context or browser has been closed')
        async def close(self):pass
    class Live:
        async def cookies(self,urls):return [{'name':'SID'}]
        async def close(self):pass
    old_init=EnvatoSession.__init__
    def init(self,profile):
        old_init(self,profile)
        if self.profile.name=='youtube':self.context=Dead();self.headless=False
    async def context(self,**kw):self.context=Live();self.headless=True;return self.context
    monkeypatch.setattr(EnvatoSession,'__init__',init)
    monkeypatch.setattr(EnvatoSession,'_context',context)
    app=create_app(project_root=root)
    assert asyncio.run(app.state.youtube_cookie_reader('https://www.youtube.com/shorts/test')) == [{'name':'SID'}]


def test_session_error_only_marks_the_affected_clip(tmp_path, monkeypatch):
    import json
    import backend.app.curation_artifacts as artifacts
    import backend.app.transcript_intents as intents
    from backend.app.curation_project import ProjectStore
    from backend.app.curation_server import create_app
    from backend.app.envato_auto_download import EnvatoSession
    root=tmp_path/'projects'; project=ProjectStore(root,probe_runner=lambda _:{}).create('Example')
    run=root/project.project_id/'run';run.mkdir(exist_ok=True)
    (run/'selection-plan.json').write_text(json.dumps({'chunks':{'beat':{'selected_assets':[{'asset_id':'one'}]}}}))
    (tmp_path/'browser-profiles'/'youtube').mkdir(parents=True)
    candidate=SimpleNamespace(asset_id='one',chunk_id='beat',provider='youtube',kind='video',title='Video',source_page='https://www.youtube.com/watch?v=test',local_asset_path=None,preview_path=None)
    monkeypatch.setattr(artifacts,'load_curation_run',lambda _:SimpleNamespace(candidate_index={'one':candidate}))
    monkeypatch.setattr(intents,'has_selected_intent',lambda *a:True)
    class BrowserError(Exception):pass
    async def context(self,**kw):raise BrowserError('Target closed')
    monkeypatch.setattr(EnvatoSession,'_context',context)
    app=create_app(project_root=root)
    issues=asyncio.run(app.state.prepare_selected_timeline_media(project.project_id))
    assert [row['asset_id'] for row in issues] == ['one']

def test_cookie_reader_retries_if_browser_closes_during_read(tmp_path):
    from backend.app.envato_auto_download import EnvatoSession
    class Page:
        def is_closed(self):return False
    class Dead:
        pages=[Page()]
        async def cookies(self,urls):raise RuntimeError('Target closed')
        async def close(self):pass
    class Live:
        async def cookies(self,urls):return [{'name':'SID'}]
        async def close(self):pass
    session=EnvatoSession(tmp_path/'profile');session.context=Dead();session.headless=False
    async def context(**kwargs):session.context=Live();session.headless=True;return session.context
    session._context=context
    assert asyncio.run(session.read_session_cookies('https://www.youtube.com/')) == [{'name':'SID'}]

def test_youtube_failure_does_not_force_interactive_popup(tmp_path,monkeypatch):
    import asyncio,json
    import backend.app.curation_artifacts as artifacts
    import backend.app.transcript_intents as intents
    import backend.app.social_media as social
    from backend.app.curation_project import ProjectStore
    from backend.app.curation_server import create_app
    root=tmp_path/'projects';p=ProjectStore(root,probe_runner=lambda _:{}).create('Test')
    run=root/p.project_id/'run';run.mkdir(exist_ok=True)
    (run/'selection-plan.json').write_text(json.dumps({'chunks':{'beat':{'selected_assets':[{'asset_id':'one'}]}}}))
    candidate=SimpleNamespace(asset_id='one',chunk_id='beat',provider='youtube_shorts',kind='video',title='Clip',source_page='https://www.youtube.com/shorts/test',local_asset_path=None,preview_path=None)
    monkeypatch.setattr(artifacts,'load_curation_run',lambda _:SimpleNamespace(candidate_index={'one':candidate}))
    monkeypatch.setattr(intents,'has_selected_intent',lambda *a:True)
    def prepare(*args,**kwargs):raise RuntimeError('YouTube richiede accesso')
    monkeypatch.setattr(social,'prepare_media',prepare)
    def report(*args):pass
    async def issue(row):raise AssertionError('YouTube must not force a popup')
    report.interactive=True;report.issue=issue
    app=create_app(project_root=root)
    errors=asyncio.run(app.state.prepare_selected_timeline_media(p.project_id,report=report))
    assert [e['asset_id'] for e in errors]==['one']
