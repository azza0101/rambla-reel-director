import asyncio


def test_only_missing_visible_thumbnails_are_hydrated_with_bounded_work():
    from backend.app.social_browser_source import hydrate_search_thumbnails
    class Locator:
        def __init__(self, ready): self.ready=ready; self.scrolled=0
        async def evaluate(self, expression): return self.ready
        async def scroll_into_view_if_needed(self, **kwargs): self.scrolled+=1
    cards=[Locator(True),Locator(False),Locator(False)]
    class List:
        async def count(self): return len(cards)
        def nth(self,i): return cards[i]
    class Page:
        def locator(self, selector): return List()
        async def wait_for_timeout(self, ms): pass
    asyncio.run(hydrate_search_thumbnails(Page(),'tiktok',2))
    assert [c.scrolled for c in cards]==[0,1,0]
