import json
import shutil
import subprocess
from pathlib import Path

import pytest


def probe(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'), reason='ffmpeg non disponibile')
def test_creates_light_1080_copy_with_audio_and_keeps_input_until_registered(tmp_path):
    from backend.app.envato_light_media import prepare_light_media
    source = tmp_path / 'source.mov'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=red:size=1920x1200:rate=5', '-f', 'lavfi', '-i', 'sine=frequency=440', '-t', '1', '-c:v', 'mpeg4', '-c:a', 'aac', str(source)], check=True, capture_output=True)
    output = prepare_light_media(source, tmp_path / 'cache')
    data = probe(output)
    video = next(s for s in data['streams'] if s['codec_type'] == 'video')
    assert video['codec_name'] == 'h264'
    assert int(video['width']) <= 1920 and int(video['height']) <= 1080
    assert int(video['nb_frames']) == 5
    assert any(s['codec_type'] == 'audio' for s in data['streams'])
    assert source.exists()


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'), reason='ffmpeg non disponibile')
def test_small_video_is_rejected_and_invalid_input_is_not_deleted(tmp_path):
    from backend.app.envato_light_media import prepare_light_media
    source = tmp_path / 'small.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=black:size=320x240:rate=5', '-t', '1', '-c:v', 'mpeg4', str(source)], check=True, capture_output=True)
    with pytest.raises(ValueError, match='720'):
        prepare_light_media(source, tmp_path / 'cache')
    assert source.exists()
    bad = tmp_path / 'bad.mov'
    bad.write_bytes(b'not a video')
    with pytest.raises(Exception):
        prepare_light_media(bad, tmp_path / 'cache')
    assert bad.read_bytes() == b'not a video'
