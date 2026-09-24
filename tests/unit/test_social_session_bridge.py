import asyncio

import httpx
import pytest


def test_clip_worker_uses_live_cookies_and_removes_temporary_file(monkeypatch,tmp_path):
    from pathlib import Path
    from backend.app.social_acquisition import download_authenticated_section
    original=httpx.Client
    monkeypatch.setenv('RAMBLA_SOCIAL_SESSION_URL','http://127.0.0.1:8817')
    monkeypatch.setenv('RAMBLA_SOCIAL_SESSION_TOKEN','test-secret')
    def respond(request):
        assert request.url.path.endswith('/tiktok/session-cookies')
        assert request.headers['X-Rambla-Session']=='test-secret'
        return httpx.Response(200,json={'cookies':[{'domain':'.tiktok.com','name':'session','value':'test','path':'/'}]})
    monkeypatch.setattr(httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(respond)))
    def runner(command,**kw):
        assert '--cookies-from-browser' not in command
        assert '*2.000-5.500' in command
        assert 'session' in Path(command[command.index('--cookies')+1]).read_text()
        Path(command[command.index('-o')+1]).write_bytes(b'clip')
    result=download_authenticated_section('https://www.tiktok.com/@x/video/1','tiktok',tmp_path/'clip.mp4',start=2,duration=3.5,runner=runner)
    assert result.is_file() and not list(tmp_path.glob('*.cookies'))


def test_worker_uses_server_session_and_does_not_open_another_profile(monkeypatch):
    from backend.app.social_browser_source import BrowserSocialSource

    class NoBrowser:
        async def run_in_profile(self, *args, **kwargs):
            pytest.fail('Worker must not launch a second browser')

    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={'rows': [{'provider_id': '123'}], 'diagnostics': {'browser_state': 'search_results'}})

    client = httpx.AsyncClient
    monkeypatch.setenv('RAMBLA_SOCIAL_SESSION_URL', 'http://127.0.0.1:8814')
    monkeypatch.setenv('RAMBLA_SOCIAL_SESSION_TOKEN', 'test-secret')
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: client(transport=httpx.MockTransport(handler)))
    result = asyncio.run(BrowserSocialSource('tiktok', NoBrowser())._browser_search('airplane window', 3))
    assert result['rows'][0]['provider_id'] == '123'
    assert seen[0].url.path == '/api/curation/social/tiktok/session-search'
    assert seen[0].headers['X-Rambla-Session'] == 'test-secret'
    import json
    assert json.loads(seen[0].content) == {'query': 'airplane window', 'limit': 3}


def test_failed_server_session_never_falls_back_to_a_second_browser(monkeypatch):
    from backend.app.social_browser_source import BrowserSocialSource
    client = httpx.AsyncClient
    monkeypatch.setenv('RAMBLA_SOCIAL_SESSION_URL', 'http://127.0.0.1:8814')
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: client(transport=httpx.MockTransport(
        lambda request: httpx.Response(503, json={'detail': 'login_required'})
    )))
    with pytest.raises(RuntimeError, match='login_required'):
        asyncio.run(BrowserSocialSource('tiktok', object())._browser_search('airplane', 3))


def test_session_endpoint_requires_internal_token_and_uses_owner(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from backend.app.curation_server import create_app
    from backend.app.social_browser_source import BrowserSocialSource
    calls = []
    async def search(self, query, limit):
        assert self.profile_manager.owns_live_session
        calls.append((self.provider_name, query, limit))
        return {'rows': [], 'diagnostics': {'browser_state': 'zero_results'}}
    monkeypatch.setattr(BrowserSocialSource, '_browser_search', search)
    monkeypatch.setenv('RAMBLA_SOCIAL_SESSION_TOKEN', 'test-secret')
    with TestClient(create_app(project_root=tmp_path/'p', allowed_media_roots=[tmp_path])) as client:
        url = '/api/curation/social/tiktok/session-search'
        assert client.post(url, json={'query': 'airplane'}).status_code == 403
        assert client.post('/api/curation/social/tiktok/session-cookies').status_code == 403
        assert client.post('/api/curation/social/tiktok/session-cookies',headers={'X-Rambla-Session':'test-secret'}).status_code == 409
        assert calls == []
        response = client.post(url, json={'query': 'airplane', 'limit': 3}, headers={'X-Rambla-Session': 'test-secret'})
        assert response.status_code == 200
        assert calls == [('tiktok', 'airplane', 3)]
