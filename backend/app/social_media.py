"""On-demand social media; bounded hover previews, explicit full downloads."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import urlsplit

HOSTS = {'tiktok': {'www.tiktok.com', 'tiktok.com'},
         'instagram': {'www.instagram.com', 'instagram.com'},
         'youtube_shorts': {'www.youtube.com', 'youtube.com', 'youtu.be'}}


def media_path(source, provider, root, mode):
    if mode not in {'preview', 'full', 'poster', 'hover'} or provider not in HOSTS:
        raise ValueError('Unsupported social media request')
    parsed = urlsplit(source)
    if parsed.scheme != 'https' or parsed.hostname not in HOSTS[provider] or parsed.username or parsed.port:
        raise ValueError('Invalid provider source URL')
    key = hashlib.sha256(source.encode()).hexdigest()[:24]
    return Path(root)/'social-media'/key/(mode + ('.gif' if mode=='hover' else '.jpg' if mode == 'poster' else '.mp4'))


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
                   '--retries', '0', '--max-filesize', '250M', '-f', 'b[ext=mp4][height<=1080]/b[ext=mp4]',
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
        if any(word in detail.lower() for word in ('captcha','confirm you','not a bot','requiring login','sign in')):
            raise RuntimeError('Provider verification required: open the source and complete login/CAPTCHA manually. No automatic retries.') from None
        raise RuntimeError('Provider could not supply this media format. Open the source; download is unavailable.') from None
    except Exception:
        raise RuntimeError('Video unavailable: provider download failed; open the source to check access or CAPTCHA') from None
    finally:
        if cookie_path:
            cookie_path.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)
