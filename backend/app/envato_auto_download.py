"""Dedicated Envato browser session and per-asset licensed downloads."""
import asyncio
import hashlib
import json
import subprocess
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse
from .envato_download_bridge import _materialize, load_registry, DOWNLOAD_SUFFIXES
from .envato_site_flow import SCRIPT
from .atomic_io import write_json


def valid_url(url):
    try:
        parsed=urlparse(str(url))
        return parsed.scheme=='https' and parsed.hostname in ('elements.envato.com','app.envato.com') and not parsed.username and not parsed.password and parsed.port in (None,443)
    except ValueError:return False


@lru_cache(maxsize=256)
def _probe_video(path, size, mtime):
    try:
        result=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type','-of','json',path],capture_output=True,text=True,check=True,timeout=20)
        data=json.loads(result.stdout)
        return float(data.get('format',{}).get('duration') or 0)>0 and any(s.get('codec_type')=='video' for s in data.get('streams',[]))
    except (OSError,ValueError,TypeError,subprocess.SubprocessError):return False


def valid_video(path):
    try:
        p=Path(path)
        if not p.is_file() or p.suffix.lower() not in DOWNLOAD_SUFFIXES-{'.zip'}:return False
        st=p.stat()
        return st.st_size>0 and _probe_video(str(p.resolve()),st.st_size,st.st_mtime_ns)
    except OSError:return False



RESOLUTION_SCRIPT = r"""async () => {
  const wait=ms=>new Promise(r=>setTimeout(r,ms));
  const visible=e=>{if(!e)return false;const r=e.getBoundingClientRect();return r.width>0&&r.height>0};
  const trigger=[...document.querySelectorAll('[data-cy="idp-format-dropdown-trigger"]')].find(visible);
  if(!trigger)return {ok:true,resolution:'default'};
  trigger.click();await wait(500);
  const options=[...document.querySelectorAll('[data-cy="idp-format-option"]')].filter(visible);
  if(!options.length)return {ok:false,error:'Non riesco a leggere i formati Envato'};
  const score=e=>{
    const text=(e.innerText||e.textContent||'').toLowerCase();
    const dimensions=text.match(/(\d{3,5})\s*[x×]\s*(\d{3,5})/);
    const label=text.match(/(\d{3,4})\s*p/);
    const height=dimensions?Math.min(+dimensions[1],+dimensions[2]):label?+label[1]:/\b4k\b/.test(text)?2160:/\bhd\b/.test(text)?720:0;
    if(height===1080)return 0;
    if(height>0&&height<1080)return 10000-height;
    if(height>1080)return 20000+height;
    return 99999;
  };
  const sorted=options.map((el,i)=>({el,i,score:score(el)})).sort((a,b)=>a.score-b.score||a.i-b.i);
  const chosen=sorted[0];const name=(chosen.el.innerText||chosen.el.textContent||'').trim();
  chosen.el.click();await wait(800);
  return {ok:true,resolution:name||'default'};
}"""

def session_evidence(provider, url, html):
    from .social_page_evidence import inspect_search_html, challenge_required
    parsed = urlparse(str(url))
    host = (parsed.hostname or '').lower()
    if not (host == ('tiktok.com' if provider == 'tiktok' else 'envato.com') or host.endswith('.' + ('tiktok.com' if provider == 'tiktok' else 'envato.com'))):
        return 'unknown'
    evidence = inspect_search_html(html)
    if challenge_required(html): return 'verification_required'
    if provider == 'tiktok' and evidence.signed_in: return 'connected'
    if provider == 'envato':
        from html.parser import HTMLParser
        class AccountLinks(HTMLParser):
            connected = False
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                href = urlparse(attrs.get('href', '')).path.rstrip('/').lower()
                marker = (attrs.get('data-testid','') + ' ' + attrs.get('data-cy','')).lower()
                if tag == 'a' and href in {'/account/downloads','/user/downloads','/account/licenses'}: self.connected = True
                if marker in {'user-menu', 'account-menu', 'profile-menu'}: self.connected = True
        links=AccountLinks(); links.feed(html)
        if links.connected: return 'connected'
    if evidence.login_required or parsed.path.startswith(('/login','/sign-in','/accounts/login')):
        return 'login_required'
    if provider == 'envato' and 'href="/login"' in html: return 'login_required'
    return 'unknown'


class EnvatoSession:
    def __init__(self,profile):
        self.profile=Path(profile);self.driver=None;self.context=None;self.headless=None;self.lock=asyncio.Lock()

    async def _context(self, *, headless=True):
        if self.context and self.headless == headless and self.context.pages:return self.context
        if self.context:
            try:await self.context.close()
            finally:self.context=None
        if self.driver:
            await self.driver.stop();self.driver=None
        from playwright.async_api import async_playwright
        from .browser_profiles import _installed_browser
        browser=_installed_browser()
        if not browser:raise RuntimeError('Chrome o Edge non disponibile')
        self.profile.mkdir(parents=True,exist_ok=True)
        self.driver=await async_playwright().start()
        try:
            self.context=await self.driver.chromium.launch_persistent_context(str(self.profile),executable_path=browser,headless=headless,accept_downloads=True,chromium_sandbox=True,args=['--mute-audio'])
            self.headless=headless
        except Exception:
            await self.driver.stop();self.driver=None;raise
        return self.context

    async def login(self,url='https://elements.envato.com/'):
        async with self.lock:
            context=await self._context(headless=False)
            page=next((p for p in context.pages if not p.is_closed()),None) or await context.new_page()
            await page.goto(url,wait_until='domcontentloaded',timeout=30000)
            await page.bring_to_front()
        return {'status':'opened','detail':'Accedi nella finestra dedicata di RMBL; poi torna al programma.'}

    async def session_status(self, provider):
        if self.lock.locked(): return {'status': 'checking'}
        async with self.lock:
            try:
                if not self.profile.is_dir() and not self.context:
                    return {'status': 'login_required'}
                context = self.context
                if context and self.headless is False:
                    page = next((p for p in context.pages if not p.is_closed()), None)
                    if not page: return {'status': 'unknown'}
                else:
                    context = await self._context(headless=True)
                    page = await context.new_page()
                    try:
                        await page.goto('https://www.tiktok.com/' if provider == 'tiktok' else 'https://elements.envato.com/', wait_until='domcontentloaded', timeout=20000)
                        await page.wait_for_timeout(1500)
                        return {'status': session_evidence(provider, page.url, await page.content())}
                    finally:
                        await page.close()
                        await self.close()
                return {'status': session_evidence(provider, page.url, await page.content())}
            except Exception:
                return {'status': 'unknown'}

    async def download(self,url,project_name,run_root,asset_id,progress=None):
        if not valid_url(url):raise ValueError('Indirizzo Envato non valido')
        if not str(project_name).strip():raise ValueError('Nome progetto necessario per la licenza Envato')
        async with self.lock:
            context=await self._context();page=await context.new_page()
            def notify(phase):
                if progress: progress(phase)
            try:
                notify('Apertura pagina Envato')
                await page.goto(url,wait_until='domcontentloaded',timeout=45000)
                try:
                    await page.wait_for_selector('[data-cy="idp-format-dropdown-trigger"], [data-cy="idp-download-button"], [data-cy="idp-header-download-button"], [data-testid="button-download"], [data-testid="button-download-for-free"], [data-testid="action-bar-button-download"], [data-testid="subscribed-onboarding-modal-cta"]',state='attached',timeout=15000)
                except Exception:
                    pass
                if not valid_url(page.url):raise RuntimeError('Accesso Envato richiesto: apri le impostazioni e accedi')
                from .social_page_evidence import challenge_required
                if challenge_required(await page.content()):raise RuntimeError('Verifica Envato richiesta: completala nella finestra di accesso')
                notify('Scelta formato video')
                resolution=await page.evaluate(RESOLUTION_SCRIPT)
                if not isinstance(resolution,dict) or not resolution.get('ok'):
                    raise RuntimeError('Envato: '+str((resolution or {}).get('error','formato 1080p non disponibile')))
                event=asyncio.get_running_loop().create_future()
                def got_download(value):
                    if not event.done():event.set_result(value)
                page.on('download',got_download)
                notify('Registrazione licenza Envato')
                try:reply=await asyncio.wait_for(page.evaluate(SCRIPT,str(project_name).strip()),timeout=75)
                except asyncio.TimeoutError:raise RuntimeError('Envato non ha risposto: verifica accesso e riprova') from None
                if not isinstance(reply,dict) or not reply.get('ok'):
                    raise RuntimeError('Envato: '+str((reply or {}).get('errore','download non avviato'))+'. Verifica accesso e abbonamento nelle impostazioni.')
                try:item=await asyncio.wait_for(event,timeout=90)
                except asyncio.TimeoutError:raise RuntimeError('Envato non ha avviato il download: verifica accesso e licenza') from None
                suffix=Path(item.suggested_filename).suffix.lower()
                if suffix not in DOWNLOAD_SUFFIXES:raise RuntimeError('Formato scaricato da Envato non supportato')
                token=hashlib.sha256(str(asset_id).encode()).hexdigest()[:20]
                scratch=Path(run_root)/'envato-media'/token/'incoming'
                scratch.mkdir(parents=True,exist_ok=True);source=scratch/('download'+suffix)
                notify('Download del file in corso')
                await item.save_as(str(source))
                failure=await item.failure()
                if failure:raise RuntimeError('Download Envato interrotto: '+str(failure))
                notify('Verifica del video scaricato')
                target=_materialize(source,scratch / "verified")
                if not target or not await asyncio.to_thread(valid_video,target):raise RuntimeError('Il file Envato non contiene un video utilizzabile')
                final=scratch.parent / target.name
                target.replace(final)
                target=final
                try:source.unlink(missing_ok=True)
                except OSError:pass
                registry=load_registry(Path(run_root));registry['assets'][str(asset_id)]={'media_path':str(target.resolve()),'license_project':str(project_name).strip()}
                write_json(Path(run_root)/'envato-downloads.json',registry)
                return {'status':'ready','asset_id':asset_id,'media_path':str(target.resolve())}
            finally:await page.close()

    async def close(self):
        if self.context:await self.context.close();self.context=None
        if self.driver:await self.driver.stop();self.driver=None
