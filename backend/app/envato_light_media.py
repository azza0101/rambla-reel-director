"""Create a verified, portable editing copy of an Envato download."""
from __future__ import annotations

import json
import subprocess
from fractions import Fraction
import uuid
from pathlib import Path


def _probe(path: Path) -> dict:
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
        capture_output=True, text=True, check=True, timeout=60,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    data = json.loads(result.stdout)
    video = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None)
    if not video:
        raise ValueError('Il file Envato non contiene video')
    duration = float(video.get('duration') or data.get('format', {}).get('duration') or 0)
    if duration <= 0:
        raise ValueError('Durata del video Envato non valida')
    return {'video': video, 'duration': duration,
            'audio': any(s.get('codec_type') == 'audio' for s in data.get('streams', []))}


def assert_unchanged_frame_timing(source: Path, output: Path) -> None:
    """Compare presentation timestamps without decoding or changing the media."""
    def timestamps(path):
        data=subprocess.run(['ffprobe','-v','error','-select_streams','v:0',
            '-show_entries','packet=pts_time','-show_packets','-of','json',str(path)],
            capture_output=True,text=True,check=True,timeout=180)
        try:
            packets=json.loads(data.stdout)['packets']
            if any(p.get('pts_time') in (None,'N/A') for p in packets): raise ValueError()
            return sorted(float(p['pts_time']) for p in packets)
        except (KeyError,ValueError,TypeError) as exc:
            raise ValueError('Tempi dei fotogrammi non verificabili') from exc
    before,after=timestamps(source),timestamps(output)
    if not before or len(before)!=len(after):
        raise ValueError('Numero o tempi dei fotogrammi non verificabili')
    origin_before,origin_after=before[0],after[0]
    if any(abs((a-origin_before)-(b-origin_after)) > .002 for a,b in zip(before,after)):
        raise ValueError('Copia non valida: i tempi dei fotogrammi sono cambiati')


def prepare_light_media(source: Path, destination: Path) -> Path:
    """Return a verified H.264 MP4; never remove or change source."""
    source = Path(source)
    destination = Path(destination)
    from .media_export_quality import require_editing_quality
    require_editing_quality(source)
    before = _probe(source)
    destination.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    temporary = destination / ('rambla-1080-' + token + '.working.mp4')
    final = destination / ('rambla-1080-' + token + '.mp4')
    scale = "scale=w='min(iw,if(gte(iw,ih),1920,1080))':h='min(ih,if(gte(iw,ih),1080,1920))':force_original_aspect_ratio=decrease:force_divisible_by=2"
    try:
        subprocess.run(
            ['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(source),
             '-map', '0:v:0', '-map', '0:a?', '-vf', scale, '-c:v', 'libx264',
             '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p',
             '-fps_mode', 'passthrough', '-c:a', 'aac', '-b:a', '192k',
             '-movflags', '+faststart', str(temporary)],
            capture_output=True, check=True, timeout=3600,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        after = _probe(temporary)
        require_editing_quality(temporary)
        src_video, dst_video = before['video'], after['video']
        width, height = int(dst_video['width']), int(dst_video['height'])
        if (dst_video.get('codec_name') != 'h264' or max(width, height) > 1920 or min(width, height) > 1080
                or width > int(src_video['width']) or height > int(src_video['height'])
                or before['audio'] != after['audio']
                or abs(before['duration'] - after['duration']) > max(.1, before['duration'] * .001)):
            raise ValueError('Copia Envato non valida: durata, audio o dimensioni non corrispondono')
        def frame_rate(video, key):
            try:
                value=Fraction(str(video.get(key) or '0'))
                return value if value > 0 else None
            except (ValueError, ZeroDivisionError):
                return None
        for key in ('r_frame_rate', 'avg_frame_rate'):
            source_rate, output_rate = frame_rate(src_video, key), frame_rate(dst_video, key)
            if source_rate is None or output_rate is None or abs(float(source_rate/output_rate)-1) > 0.0005:
                raise ValueError('Copia non valida: gli FPS originali sono cambiati o non verificabili')
        def frame_count(path, video):
            value=video.get('nb_frames')
            if value not in (None, 'N/A'):
                return int(value)
            measured=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-count_frames',
                '-show_entries','stream=nb_read_frames','-of','json',str(path)],capture_output=True,
                text=True,check=True,timeout=3600)
            try: return int(json.loads(measured.stdout)['streams'][0]['nb_read_frames'])
            except (KeyError,ValueError,IndexError,TypeError) as exc:
                raise ValueError('Numero di fotogrammi originali non verificabile') from exc
        if frame_count(source, src_video) != frame_count(temporary, dst_video):
            raise ValueError('Copia Envato non valida: numero di fotogrammi diverso')
        assert_unchanged_frame_timing(source, temporary)
        temporary.replace(final)
        return final
    finally:
        temporary.unlink(missing_ok=True)
