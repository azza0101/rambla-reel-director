from types import SimpleNamespace
from pathlib import Path
import pytest

def test_preview_is_bounded_full_is_explicit_and_cookie_file_removed(tmp_path, monkeypatch):
    from backend.app.social_media import prepare_media
    from backend.app import media_export_quality
    monkeypatch.setattr(media_export_quality, 'require_editing_quality', lambda _: {'duration': 8, 'width': 1280, 'height': 720})
    calls=[]
    def run(command, **kwargs):
        calls.append(command)
        if '-m' in command:
            Path(command[command.index('-o')+1]).write_bytes(b'media')
            cookie=Path(command[command.index('--cookies')+1])
            assert 'session' in cookie.read_text()
        else:
            Path(command[-1]).write_bytes(b'jpeg')
        return SimpleNamespace(returncode=0)
    cookies=[{'domain':'.tiktok.com','path':'/','secure':True,'name':'session','value':'private','expires':-1}]
    source='https://www.tiktok.com/@x/video/123'
    preview=prepare_media(source,'tiktok',tmp_path,'preview',cookies=cookies,runner=run,python='python')
    assert preview.is_file()
    assert '*0-3.5' in calls[0]
    selected_format = calls[0][calls[0].index('-f') + 1]
    assert 'bv*' in selected_format and '+ba' in selected_format
    assert not list(tmp_path.rglob('*.cookies'))
    calls.clear()
    prepare_media(source,'tiktok',tmp_path,'preview',cookies=cookies,runner=run,python='python')
    assert not calls
    prepare_media(source,'tiktok',tmp_path,'full',cookies=cookies,runner=run,python='python')
    assert '--download-sections' not in calls[0]

def test_rejects_non_provider_url(tmp_path):
    from backend.app.social_media import prepare_media
    with pytest.raises(ValueError):
        prepare_media('http://127.0.0.1/private','tiktok',tmp_path,'full')


def test_normal_youtube_is_supported_for_explicit_full_selected_download(tmp_path, monkeypatch):
    from backend.app.social_media import prepare_media
    from backend.app import media_export_quality
    monkeypatch.setattr(media_export_quality, 'require_editing_quality', lambda _: {'duration': 8, 'width': 1280, 'height': 720})
    calls=[]
    def run(command, **kwargs):
        calls.append(command)
        Path(command[command.index('-o')+1]).write_bytes(b'media')
        return SimpleNamespace(returncode=0)

    source='https://www.youtube.com/watch?v=abc123'
    output=prepare_media(source,'youtube',tmp_path,'full',runner=run,python='python')

    assert output.is_file()
    assert '--download-sections' not in calls[0]


def test_cancellable_runner_stops_child_process():
    import sys, threading, time, pytest
    from backend.app.social_media import cancellable_runner
    event=threading.Event();timer=threading.Timer(.3,event.set);timer.start()
    started=time.monotonic()
    try:
        with pytest.raises(RuntimeError,match='interrotto'):
            cancellable_runner(event)([sys.executable,'-c','import time;time.sleep(20)'],check=True,capture_output=True,timeout=30)
    finally:timer.cancel()
    assert time.monotonic()-started < 8
