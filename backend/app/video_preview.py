"""Only verified browser media may advertise playback. Thumbnails remain discovery."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess


@lru_cache(maxsize=512)
def _probe(path: str, size: int, mtime: int) -> dict:
    try:
        result = subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',path],check=True,capture_output=True,text=True,timeout=15)
        data = json.loads(result.stdout)
        stream = next(s for s in data['streams'] if s['codec_type']=='video')
        duration = float(data['format']['duration'])
        codec = stream.get('codec_name')
        suffix = Path(path).suffix.lower()
        allowed = (suffix == '.mp4' and codec == 'h264') or (suffix == '.webm' and codec in {'vp8','vp9','av1'})
        return {'playable':allowed and 2.5 <= duration <= 4.05,'duration':duration,'mime':'video/mp4' if suffix=='.mp4' else 'video/webm','codec':codec}
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


def materialize_clip(source: str, directory: Path, identity: str) -> dict:
    directory.mkdir(parents=True,exist_ok=True)
    key = hashlib.sha256((identity+'|preview-v1').encode()).hexdigest()[:24]
    preview = directory/f'{key}.mp4'
    poster = directory/f'{key}.jpg'
    if not probe_preview(str(preview))['playable']:
        subprocess.run(['ffmpeg','-v','error','-y','-i',source,'-t','3.5','-vf',"scale='min(640,iw)':-2",'-an','-c:v','libx264','-pix_fmt','yuv420p','-preset','veryfast','-crf','28','-movflags','+faststart',str(preview)],check=True,capture_output=True,timeout=60)
    facts = probe_preview(str(preview))
    if not facts['playable']:
        raise ValueError('preview is not a 2.5-4 second browser video')
    if not poster.is_file():
        subprocess.run(['ffmpeg','-v','error','-y','-ss','1','-i',str(preview),'-frames:v','1',str(poster)],check=True,capture_output=True,timeout=20)
    return {'preview_path':str(preview),'poster_path':str(poster),'keyframe_path':str(poster),'preview_status':'ready','preview_duration':facts['duration'],'preview_mime':facts['mime']}
