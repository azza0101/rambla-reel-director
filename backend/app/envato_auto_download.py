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
  const button=()=>[...document.querySelectorAll('[data-cy="idp-download-button"], [data-cy="idp-header-download-button"]')].find(visible);
  const trigger=[...document.querySelectorAll('[data-cy="idp-format-dropdown-trigger"]')].find(visible);
  const fullhd=s=>/1080\s*p|1920\s*[x×]\s*1080/i.test(s||'');
  if(trigger){
    trigger.click();await wait(500);
    const options=[...document.querySelectorAll('[data-cy="idp-format-option"]')].filter(visible);
    const hd=options.find(e=>fullhd(e.innerText||e.textContent));
    if(!hd)return {ok:false,error:'Questo video non offre il formato 1080p'};
    hd.click();await wait(800);
    const selected=button();
    if(!selected||!fullhd(selected.innerText||selected.textContent))return {ok:false,error:'Non riesco a verificare il formato 1080p selezionato'};
    return {ok:true};
  }
  const selected=button(),label=selected&&(selected.innerText||selected.textContent)||'';
  const details=document.querySelector('[data-cy="idp-attributes"]');
  if(fullhd(label)||(!/4k|2160|uhd/i.test(label)&&fullhd(details&&(details.innerText||details.textContent))))return {ok:true};
  return {ok:false,error:'Risoluzione 1080p non disponibile o non verificabile'};
}"""


class EnvatoSession:
    def __init__(self,profile):
        self.profile=Path(profile);self.driver=None;self.context=None;self.lock=asyncio.Lock()

    async def _context(self):
        if self.context:return self.context
        from playwright.async_api import async_playwright
        from .browser_profiles import _installed_browser
        browser=_installed_browser()
        if not browser:raise RuntimeError('Chrome o Edge non disponibile')
        self.profile.mkdir(parents=True,exist_ok=True)
        self.driver=await async_playwright().start()
        try:self.context=await self.driver.chromium.launch_persistent_context(str(self.profile),executable_path=browser,headless=False,accept_downloads=True,chromium_sandbox=True)
        except Exception:
            await self.driver.stop();self.driver=None;raise
        return self.context

    async def login(self):
        async with self.lock:
            context=await self._context()
            page=next((p for p in context.pages if not p.is_closed()),None) or await context.new_page()
            await page.goto('https://elements.envato.com/',wait_until='domcontentloaded',timeout=30000)
            await page.bring_to_front()
        return {'status':'opened','detail':'Accedi nella finestra Envato di RMBL; poi torna al programma.'}

    async def download(self,url,project_name,run_root,asset_id):
        if not valid_url(url):raise ValueError('Indirizzo Envato non valido')
        if not str(project_name).strip():raise ValueError('Nome progetto necessario per la licenza Envato')
        async with self.lock:
            context=await self._context();page=await context.new_page()
            try:
                await page.goto(url,wait_until='load',timeout=45000)
                await page.wait_for_timeout(4000)
                if not valid_url(page.url):raise RuntimeError('Accesso Envato richiesto: apri le impostazioni e accedi')
                from .social_page_evidence import challenge_required
                if challenge_required(await page.content()):raise RuntimeError('Verifica Envato richiesta: completala nella finestra di accesso')
                resolution=await page.evaluate(RESOLUTION_SCRIPT)
                if not isinstance(resolution,dict) or not resolution.get('ok'):
                    raise RuntimeError('Envato: '+str((resolution or {}).get('error','formato 1080p non disponibile')))
                event=asyncio.get_running_loop().create_future()
                def got_download(value):
                    if not event.done():event.set_result(value)
                page.on('download',got_download)
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
                await item.save_as(str(source))
                failure=await item.failure()
                if failure:raise RuntimeError('Download Envato interrotto: '+str(failure))
                target=_materialize(source,scratch.parent)
                if not target or not await asyncio.to_thread(valid_video,target):raise RuntimeError('Il file Envato non contiene un video utilizzabile')
                registry=load_registry(Path(run_root));registry['assets'][str(asset_id)]={'media_path':str(target.resolve()),'license_project':str(project_name).strip()}
                write_json(Path(run_root)/'envato-downloads.json',registry)
                return {'status':'ready','asset_id':asset_id,'media_path':str(target.resolve())}
            finally:await page.close()

    async def close(self):
        if self.context:await self.context.close();self.context=None
        if self.driver:await self.driver.stop();self.driver=None
