import asyncio


def test_green_connection_requires_successful_search_and_open_session(monkeypatch, tmp_path):
    from backend.app.browser_profiles import BrowserProfileManager
    from backend.app.social_browser_source import BrowserSocialSource
    class Runner:
        connected = True
        def is_connected(self, path): return self.connected
        async def __call__(self,path,url,callback):
            class Page:
                url='https://www.tiktok.com/'
                async def content(self):return '<a data-e2e="profile-icon">Me</a>'
            assert url is None
            return await callback(Page(),None)
    runner = Runner()
    manager = BrowserProfileManager(tmp_path, playwright_runner=runner)
    assert manager.status()['tiktok']['connection_ready'] is False
    async def search(*args):
        return {'rows':[{}], 'diagnostics':{'browser_state':'search_results'}}
    monkeypatch.setattr(BrowserSocialSource, '_browser_search', search)
    asyncio.run(manager.check_search('tiktok'))
    assert manager.status()['tiktok']['connection_ready'] is True
    assert manager.status()['instagram']['connection_ready'] is False
    runner.connected = False
    assert manager.status()['tiktok']['connection_ready'] is False
