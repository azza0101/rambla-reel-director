import asyncio
from types import SimpleNamespace


def test_login_check_and_search_reuse_page_until_user_closes_browser():
    from backend.app.live_social_sessions import LiveSocialSessions
    launches = []

    class Page:
        url = 'about:blank'
        closed = False
        html = ''
        async def content(self): return self.html
        def is_closed(self): return self.closed
        async def goto(self, url, **kwargs): self.url = url
        async def bring_to_front(self): pass

    class Context:
        def __init__(self): self.pages = [Page()]
        async def close(self): self.pages[0].closed = True

    async def launch(**kwargs):
        launches.append(kwargs)
        return Context()

    class Driver:
        async def start(self):
            return SimpleNamespace(chromium=SimpleNamespace(launch_persistent_context=launch), stop=self.stop)
        async def stop(self): pass

    async def exercise():
        sessions = LiveSocialSessions(browser_finder=lambda: 'chrome.exe', driver_factory=Driver)
        async def capture(page, context): return page
        first = await sessions('profile', 'https://www.tiktok.com/', capture)
        second = await sessions('profile', 'https://www.tiktok.com/search/video?q=nature', capture)
        third = await sessions('profile', 'https://www.tiktok.com/search/video?q=airplane', capture)
        assert first is second is third
        assert len(launches) == 1
        assert launches[0]['headless'] is False
        assert launches[0]['chromium_sandbox'] is True
        assert launches[0]['executable_path'] == 'chrome.exe'
        import pytest
        from backend.app.browser_profiles import BrowserUnavailableError
        first.html='<div>Verify you are human</div>'
        previous=first.url
        with pytest.raises(BrowserUnavailableError,match='challenge_required'):
            await sessions('profile','https://www.tiktok.com/search/video?q=bus',capture)
        assert first.url==previous
        first.closed = True
        fourth = await sessions('profile', 'https://www.tiktok.com/', capture)
        assert fourth is not first
        await sessions.close()
        assert fourth.closed

    asyncio.run(exercise())


def test_open_only_focuses_existing_session_without_navigating_away(tmp_path):
    from backend.app.browser_profiles import BrowserProfileManager
    calls = []
    class Runner:
        def is_connected(self, path): return True
        async def __call__(self, directory, url, callback):
            calls.append(url)
            class Page:
                async def bring_to_front(self): calls.append('focused')
            return await callback(Page(), None)
    manager = BrowserProfileManager(tmp_path, playwright_runner=Runner())
    asyncio.run(manager.open_login_async('tiktok'))
    assert calls == [None, 'focused']

def test_verify_is_passive_and_captcha_never_navigates(tmp_path):
    from backend.app.browser_profiles import BrowserProfileManager
    class Page:
        url='https://www.tiktok.com/'
        html='<a data-e2e="profile-icon">Me</a>'
        async def content(self):return self.html
    page=Page();calls=[]
    class Runner:
        def is_connected(self,path):return True
        async def __call__(self,path,url,callback):
            calls.append(url)
            return await callback(page,None)
    manager=BrowserProfileManager(tmp_path,playwright_runner=Runner())
    async def exercise():
        assert (await manager.check_search('tiktok'))['ready']
        page.html='<div>Verify you are human</div>'
        result=await manager.check_search('tiktok')
        assert not result['ready'] and result['browser_state']=='challenge_required'
        assert not (await manager.check_search('tiktok'))['ready']
    asyncio.run(exercise())
    assert calls==[None,None,None]

def test_captcha_pauses_remaining_queries_without_public_fallback(tmp_path):
    from backend.app.social_browser_source import BrowserSocialSource
    calls=[]
    class Fallback:
        async def search(self,*a,**k):calls.append('fallback');return []
    source=BrowserSocialSource('tiktok',None,fallback=Fallback())
    async def blocked(*a):calls.append('browser');raise RuntimeError('challenge_required: complete manually')
    source._browser_search=blocked
    async def exercise():
        for query in ['bus','bus pov']:
            await source.search(query,orientation=None,min_duration=1,max_duration=100,limit=6)
        assert calls==['browser']
        assert source.last_attempt['browser_state']=='challenge_required'
        assert source.last_attempt['fallback_used'] is False
    asyncio.run(exercise())

def test_passive_sidebar_profile_enables_search(tmp_path):
    from backend.app.browser_profiles import BrowserProfileManager
    class Page:
        url='https://www.tiktok.com/'
        async def content(self):return '<nav><a href="/messages">Messaggi <b>34</b></a><a href="/@myprofile"><img src="avatar.jpg">Profilo</a></nav>'
    class Runner:
        def is_connected(self,path):return True
        async def __call__(self,path,url,callback):
            assert url is None
            return await callback(Page(),None)
    r=asyncio.run(BrowserProfileManager(tmp_path,playwright_runner=Runner()).check_search('tiktok'))
    assert r['ready'] and r['login_state']=='verified'


def test_other_creator_link_does_not_prove_login():
    from backend.app.social_page_evidence import inspect_search_html
    assert not inspect_search_html('<a href="/@creator">Some creator</a><a href="/messages">Messages</a>').signed_in
    assert not inspect_search_html('<div hidden><a href="/@me">Profile</a></div><a href="/messages">Messages</a>').signed_in

def test_unknown_login_on_open_tiktok_allows_explicit_search_but_not_green_badge(tmp_path):
    from backend.app.browser_profiles import BrowserProfileManager
    class Page:
        url='https://www.tiktok.com/'
        html='<main>Per te <button>Cerca</button></main>'
        async def content(self):return self.html
    page=Page()
    class Runner:
        def is_connected(self,path):return True
        async def __call__(self,path,url,callback):
            assert url is None
            return await callback(page,None)
    manager=BrowserProfileManager(tmp_path,playwright_runner=Runner())
    async def exercise():
        r=await manager.check_search('tiktok')
        assert r['ready'] and r['browser_state']=='session_unconfirmed'
        assert r['login_state']=='unknown'
        assert not manager.status()['tiktok']['connection_ready']
        page.html='<main>Verify you are human</main>'
        assert not (await manager.check_search('tiktok'))['ready']
        page.html='<input type="password">'
        assert not (await manager.check_search('tiktok'))['ready']
        page.html=''
        assert not (await manager.check_search('tiktok'))['ready']
    asyncio.run(exercise())

def test_focus_connected_session_does_not_wait_for_search_lock(tmp_path):
    from backend.app.browser_profiles import BrowserProfileManager
    class Runner:
        def is_connected(self,path):return True
        async def focus_existing(self,path):return True
    async def exercise():
        manager=BrowserProfileManager(tmp_path,playwright_runner=Runner())
        async with manager._locks['tiktok']:
            result=await asyncio.wait_for(manager.open_login_async('tiktok'),timeout=.1)
        assert result['status']=='focused'
    asyncio.run(exercise())


def test_focus_restores_minimized_window_without_navigation():
    from backend.app.live_social_sessions import LiveSocialSessions
    calls=[]
    class CDP:
        async def send(self,method,args=None):
            calls.append((method,args))
            return {'windowId':7,'bounds':{'windowState':'minimized'}}
        async def detach(self):pass
    class Page:
        def is_closed(self):return False
        async def bring_to_front(self):calls.append('front')
    page=Page()
    class Context:
        pages=[page]
        async def new_cdp_session(self,p):assert p is page;return CDP()
    async def exercise():
        sessions=LiveSocialSessions();sessions.pages['profile']=page;sessions.contexts['profile']=Context()
        assert await sessions.focus_existing('profile')
        assert ('Browser.setWindowBounds',{'windowId':7,'bounds':{'windowState':'normal'}}) in calls
        assert calls[-1]=='front'
    asyncio.run(exercise())
