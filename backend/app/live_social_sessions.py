"""One visible Playwright page per RAMBLA profile, owned by the UI server."""
import inspect
import logging
import asyncio


class LiveSocialSessions:
    def __init__(self, *, browser_finder=None, driver_factory=None):
        self.browser_finder = browser_finder
        self.driver_factory = driver_factory
        self.driver = None
        self.contexts = {}
        self.pages = {}
        self.start_lock = asyncio.Lock()

    async def __call__(self, profile_dir, start_url, callback):
        from .browser_profiles import BrowserUnavailableError, _installed_browser
        key = str(profile_dir)
        page = self.pages.get(key)
        if page is None or page.is_closed():
            context = self.contexts.get(key)
            page = next((p for p in context.pages if not p.is_closed()), None) if context else None
            if page is not None:
                self.pages[key] = page
        if page is None or page.is_closed():
            old = self.contexts.pop(key, None)
            if old:
                try:
                    await old.close()
                except Exception:
                    pass
            browser = (self.browser_finder or _installed_browser)()
            if not browser:
                raise BrowserUnavailableError('browser_missing: installed Chrome/Edge required')
            try:
                async with self.start_lock:
                    if self.driver is None:
                        if self.driver_factory is None:
                            from playwright.async_api import async_playwright
                            self.driver_factory = async_playwright
                        self.driver = await self.driver_factory().start()
                context = await self.driver.chromium.launch_persistent_context(
                    user_data_dir=key, executable_path=browser,
                    headless=(__import__('pathlib').Path(key).name == 'tiktok'), accept_downloads=False, chromium_sandbox=True, args=['--mute-audio'],
                )
                page = context.pages[0] if context.pages else await context.new_page()
                self.contexts[key] = context
                self.pages[key] = page
            except Exception as exc:
                detail = str(exc)
                logging.getLogger(__name__).error('Visible social session failed: %s', detail)
                locked = any(s in detail.casefold() for s in ('processsingleton', 'profile already in use', 'user data directory is already in use'))
                reason = ('profile_in_use: close the OLD RAMBLA login window once, then OPEN again; '
                          'keep the new managed window open') if locked else 'browser_launch_failed: ' + ' '.join(detail.split())[:280]
                raise BrowserUnavailableError(reason) from exc
        if start_url and callable(getattr(page,'content',None)):
            from .social_page_evidence import challenge_required
            if challenge_required(await page.content()):
                raise BrowserUnavailableError('challenge_required: resolve verification in the existing window; navigation paused')
        if start_url and page.url != start_url:
            await page.goto(start_url, wait_until='domcontentloaded', timeout=25000)
        result = callback(page, self.contexts[key])
        return await result if inspect.isawaitable(result) else result

    async def focus_existing(self, profile_dir):
        """Focus the managed challenge page without a search lock or navigation."""
        key = str(profile_dir)
        context = self.contexts.get(key)
        page = self.pages.get(key)
        if page is None or page.is_closed():
            page = next((p for p in context.pages if not p.is_closed()), None) if context else None
        if page is None: return False
        # Selecting a tab alone does not restore a minimized Chromium window.
        session = None
        try:
            session = await context.new_cdp_session(page)
            window = await session.send('Browser.getWindowForTarget')
            if window.get('bounds', {}).get('windowState') == 'minimized':
                await session.send('Browser.setWindowBounds', {'windowId': window['windowId'], 'bounds': {'windowState': 'normal'}})
        except Exception:
            logging.getLogger(__name__).debug('Window restore unavailable; trying tab focus', exc_info=True)
        finally:
            if session:
                try: await session.detach()
                except Exception: pass
        await page.bring_to_front()
        return True

    async def close_profile(self, profile_dir):
        key=str(profile_dir)
        context=self.contexts.pop(key,None)
        self.pages.pop(key,None)
        if context:await context.close()

    async def close(self):
        for context in self.contexts.values():
            try:
                await context.close()
            except Exception:
                pass
        self.contexts.clear()
        self.pages.clear()
        if self.driver:
            await self.driver.stop()
            self.driver = None

    def is_connected(self, profile_dir):
        context = self.contexts.get(str(profile_dir))
        return context is not None and any(not p.is_closed() for p in context.pages)
