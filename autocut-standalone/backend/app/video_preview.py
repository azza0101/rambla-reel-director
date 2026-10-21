"""Only verified browser media may advertise playback. Thumbnails remain discovery."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess
import uuid
import time


def download_preview_proxy(source: str, directory: Path, identity: str, *, max_bytes=32*1024*1024, max_seconds=30) -> Path:
    """Scoped low-resolution proxy; Python TLS avoids Windows FFmpeg SSPI failure."""
    import httpx
    target=directory/(hashlib.sha256((identity+'|proxy|'+source).encode()).hexdigest()[:24]+'-proxy.mp4')
    if target.is_file() and target.stat().st_size:return target
    temporary=target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp')
    deadline=time.monotonic()+max_seconds
    try:
        with httpx.stream('GET',source,timeout=25,follow_redirects=True) as response:
            response.raise_for_status()
            if int(response.headers.get('content-length',0))>max_bytes:raise ValueError('preview proxy exceeds 32 MB bound')
            total=0
            with temporary.open('wb') as stream:
                for chunk in response.iter_bytes():
                    if time.monotonic()>deadline:raise TimeoutError('preview proxy time budget exceeded')
                    total+=len(chunk)
                    if total>max_bytes:raise ValueError('preview proxy exceeds 32 MB bound')
                    stream.write(chunk)
        temporary.replace(target)
    finally:temporary.unlink(missing_ok=True)
    return target


@lru_cache(maxsize=512)
def _probe(path: str, size: int, mtime: int) -> dict:
    try:
        result = subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',path],check=True,capture_output=True,text=True,timeout=15)
        data = json.loads(result.stdout)
        stream = next(s for s in data['streams'] if s['codec_type']=='video')
        duration = float(data['format']['duration'])
        codec = stream.get('codec_name')
        width = int(stream.get('width') or 0)
        height = int(stream.get('height') or 0)
        suffix = Path(path).suffix.lower()
        allowed = (suffix == '.mp4' and codec == 'h264') or (suffix == '.webm' and codec in {'vp8','vp9','av1'})
        return {'playable':allowed and 2.5 <= duration <= 4.05,'duration':duration,'mime':'video/mp4' if suffix=='.mp4' else 'video/webm','codec':codec,'width':width,'height':height}
    except (OSError,ValueError,KeyError,StopIteration,subprocess.SubprocessError):
        return {'playable':False}


def probe_preview(value: str | None) -> dict:
    if not value:
        return {'playable':False}
    path = Path(value)
    if path.suffix.lower() not in {'.mp4','.webm'} or not path.is_file():
        return {'playable':False}
    stat = path.stat()
    return dict(_probe(str(path),stat.st_size,stat.st_mtime_ns))


def materialize_clip(source: str, directory: Path, identity: str, *, start_seconds: float = 0.0, streaming: bool = False) -> dict:
    directory.mkdir(parents=True,exist_ok=True)
    key = hashlib.sha256((identity+'|preview-v2|'+str(start_seconds)).encode()).hexdigest()[:24]
    preview = directory/f'{key}.mp4'
    poster = directory/f'{key}.jpg'
    if not probe_preview(str(preview))['playable']:
        if source.startswith(('https://','http://')) and not streaming:
            source=str(download_preview_proxy(source,directory,identity))
        subprocess.run(['ffmpeg','-v','error','-y','-ss',str(start_seconds),'-i',source,'-t','3.5','-vf',"scale='min(640,iw)':-2",'-an','-c:v','libx264','-pix_fmt','yuv420p','-preset','veryfast','-crf','28','-movflags','+faststart',str(preview)],check=True,capture_output=True,timeout=60)
    facts = probe_preview(str(preview))
    if not facts['playable']:
        raise ValueError('preview is not a 2.5-4 second browser video')
    if not poster.is_file():
        subprocess.run(['ffmpeg','-v','error','-y','-ss','1','-i',str(preview),'-frames:v','1',str(poster)],check=True,capture_output=True,timeout=20)
    return {'preview_path':str(preview),'poster_path':str(poster),'keyframe_path':str(poster),'preview_status':'ready','preview_duration':facts['duration'],'preview_mime':facts['mime'],'preview_width':facts.get('width',0),'preview_height':facts.get('height',0),'source_start_seconds':start_seconds,'source_end_seconds':start_seconds+facts['duration']}
