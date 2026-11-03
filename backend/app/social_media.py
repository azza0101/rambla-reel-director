"""On-demand social media; bounded hover previews, explicit full downloads."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import urlsplit

HOSTS = {'tiktok': {'www.tiktok.com', 'tiktok.com'},
         'instagram': {'www.instagram.com', 'instagram.com'},
         'youtube': {'www.youtube.com', 'youtube.com', 'youtu.be'},
         'youtube_shorts': {'www.youtube.com', 'youtube.com', 'youtu.be'}}


def media_path(source, provider, root, mode):
    if mode not in {'preview', 'full', 'poster', 'hover'} or provider not in HOSTS:
        raise ValueError('Unsupported social media request')
    parsed = urlsplit(source)
    if parsed.scheme != 'https' or parsed.hostname not in HOSTS[provider] or parsed.username or parsed.port:
        raise ValueError('Invalid provider source URL')
    key = hashlib.sha256(source.encode()).hexdigest()[:24]
    return Path(root)/'social-media'/key/(mode + ('.gif' if mode=='hover' else '.jpg' if mode == 'poster' else '.mp4'))


def classify_media_download_error(stderr: str) -> str:
    """Sanitized actionable error categories; never expose URLs, cookies or tokens."""
    detail = str(stderr or "").casefold()
    if any(phrase in detail for phrase in (
        "confirm you", "not a bot", "captcha", "verification required"
    )):
        return "YouTube richiede una verifica anti-bot al downloader; apri la fonte per verificare l'accesso. Non sono previsti tentativi automatici di aggiramento."
    if any(phrase in detail for phrase in (
        "sign in", "login required", "login to confirm", "cookies are no longer valid",
        "authentication required", "members-only", "private video"
    )):
        return "Il downloader non dispone di una sessione YouTube autorizzata per questo video. Aprirlo nel browser non trasferisce automaticamente i cookie a RMBL."
    if any(phrase in detail for phrase in (
        "requested format is not available", "format is not available",
        "no video formats found", "no suitable formats"
    )):
        return "Formato video non disponibile per il downloader. Prova una sorgente o un formato alternativo."
    if any(phrase in detail for phrase in (
        "http error 429", "too many requests"
    )):
        return "YouTube limita temporaneamente le richieste (429). Riprova più tardi."
    if any(phrase in detail for phrase in (
        "http error 403", "forbidden"
    )):
        return "YouTube ha rifiutato il download (403). Il video può essere visibile nel browser ma non accessibile al downloader."
    return "Download YouTube non riuscito: errore tecnico o accesso non disponibile; non è stato rilevato un CAPTCHA."


def prepare_media(source, provider, root, mode, *, cookies=(), runner=subprocess.run, python=None):
    output = media_path(source, provider, root, mode)
    if mode == 'poster':
        raise ValueError('Prepare preview first')
    if output.is_file() and output.stat().st_size:
        return output
    output.parent.mkdir(parents=True, exist_ok=True)
    runtime = python or os.environ.get('RAMBLA_PIPELINE_PYTHON') or str(Path(__file__).resolve().parents[3]/'venv/Scripts/python.exe')
    temporary = output.with_name(mode+'-pending.mp4')
    cookie_path = None
    try:
        command = [runtime, '-m', 'yt_dlp', '--no-playlist', '--no-warnings', '--socket-timeout', '10',
                   '--retries', '0', '--max-filesize', '250M', '-f',
                   'bv*[ext=mp4][height<=1080]+ba[ext=m4a]/b[ext=mp4]/best',
                   '--merge-output-format', 'mp4', '-o', str(temporary)]
        if mode == 'preview':
            command += ['--download-sections', '*0-3.5', '--force-keyframes-at-cuts']
        if cookies:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.cookies', dir=output.parent, delete=False) as handle:
                cookie_path = Path(handle.name)
                handle.write('# Netscape HTTP Cookie File\n')
                for c in cookies:
                    domain = str(c.get('domain', ''))
                    if not any(domain.lstrip('.') == h.removeprefix('www.') for h in HOSTS[provider]):
                        continue
                    values = [domain, 'TRUE' if domain.startswith('.') else 'FALSE', str(c.get('path') or '/'),
                              'TRUE' if c.get('secure') else 'FALSE', str(max(0, int(c.get('expires') or 0))),
                              str(c.get('name', '')), str(c.get('value', ''))]
                    if not any('\n' in v or '\t' in v or '\r' in v for v in values):
                        handle.write('\t'.join(values)+'\n')
            command += ['--cookies', str(cookie_path)]
        command += [source]
        if mode=='hover':
            command=[runtime,'-m','backend.app.social_gif','--source',source,'--provider',provider,'--output',str(output),
                     '--full-cache',str(media_path(source,provider,root,'full'))]
            if cookie_path:command+=['--cookies',str(cookie_path)]
            runner(command,check=True,capture_output=True,timeout=110)
            if not output.is_file():raise RuntimeError('Animated preview unavailable')
            return output
        runner(command, check=True, capture_output=True, timeout=65 if mode == 'preview' else 150)
        if not temporary.is_file() or not temporary.stat().st_size:
            raise RuntimeError('Provider did not return a downloadable video')
        temporary.replace(output)
        if mode == 'preview':
            try:
                runner(['ffmpeg','-v','error','-y','-ss','0.4','-i',str(output),'-frames:v','1',str(media_path(source,provider,root,'poster'))], check=True,capture_output=True,timeout=15)
            except Exception:
                pass
        return output
    except subprocess.CalledProcessError as exc:
        detail=exc.stderr.decode('utf-8',errors='replace') if isinstance(exc.stderr,bytes) else str(exc.stderr or '')
        raise RuntimeError(classify_media_download_error(detail)) from None
    except subprocess.TimeoutExpired:
        raise RuntimeError('Video download timeout: riprova più tardi o usa una fonte alternativa.') from None
    except Exception:
        raise RuntimeError('Download video non riuscito: errore tecnico del downloader. Non è necessariamente un CAPTCHA.') from None
    finally:
        if cookie_path:
            cookie_path.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)
