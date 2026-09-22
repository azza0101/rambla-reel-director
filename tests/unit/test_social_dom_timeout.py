import asyncio,subprocess
import pytest
from backend.app import browser_profiles as m

@pytest.mark.parametrize('html,usable',[(b'<html><body>ok</body></html>',True),(b'<html><body>loading',False),(b'',False)])
def test_dom_timeout_preserves_only_complete_output(monkeypatch,tmp_path,html,usable):
 monkeypatch.setattr(m,'_installed_browser',lambda:'chrome')
 def run(command,**kw):
  assert '--timeout=15000' in command
  raise subprocess.TimeoutExpired(command,25,output=html)
 monkeypatch.setattr(m.subprocess,'run',run)
 async def callback(page,ctx):return await page.content()
 call=m._default_chromium_dom_runner(tmp_path,'https://www.tiktok.com/search/video?q=nature',callback)
 if usable:assert 'ok' in asyncio.run(call)
 else:
  with pytest.raises(m.BrowserUnavailableError,match='search_timeout.*login state unknown'):asyncio.run(call)
