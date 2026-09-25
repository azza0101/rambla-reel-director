from types import SimpleNamespace
from pathlib import Path
import pytest

def test_preview_is_bounded_full_is_explicit_and_cookie_file_removed(tmp_path):
    from backend.app.social_media import prepare_media
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
