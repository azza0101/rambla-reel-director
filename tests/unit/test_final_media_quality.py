import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def videos(tmp_path):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('ffmpeg e ffprobe necessari')
    result = {}
    for name, dimensions in [('low', '640x360'), ('hd', '1280x720'), ('portrait', '720x1280'), ('large', '1920x1200')]:
        target = tmp_path / (name + '.mp4')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        f'color=blue:size={dimensions}:rate=1', '-t', '1', '-c:v', 'libx264',
                        '-preset', 'ultrafast', str(target)], check=True, capture_output=True)
        result[name] = target
    return result


def test_native_resolution_is_required_and_both_orientations_work(videos):
    from backend.app.media_export_quality import require_editing_quality, MediaQualityError
    for name in ('hd', 'portrait'):
        assert require_editing_quality(videos[name])['duration'] > 0
    with pytest.raises(MediaQualityError, match='640.*360.*720'):
        require_editing_quality(videos['low'])
    with pytest.raises(MediaQualityError, match='verific'):
        require_editing_quality(videos['low'].parent / 'missing.mp4')


def test_new_large_download_gets_portable_1080_copy_without_deleting_source(videos, tmp_path):
    from backend.app.media_export_quality import normalize_new_download, require_editing_quality
    output = normalize_new_download(videos['large'], tmp_path / 'converted')
    facts = require_editing_quality(output)
    assert min(facts['width'], facts['height']) <= 1080
    assert max(facts['width'], facts['height']) <= 1920
    assert videos['large'].exists()
    assert normalize_new_download(videos['hd'], tmp_path / 'converted') == videos['hd']


def test_envato_low_source_is_rejected_before_converting_and_kept(videos, tmp_path):
    from backend.app.envato_light_media import prepare_light_media
    from backend.app.media_export_quality import MediaQualityError
    original = videos['low'].read_bytes()
    with pytest.raises(MediaQualityError, match='720'):
        prepare_light_media(videos['low'], tmp_path / 'converted')
    assert videos['low'].read_bytes() == original
    assert not list((tmp_path / 'converted').glob('*.mp4'))


def test_social_retries_old_low_cache_with_best_video_and_keeps_cache_on_failure(videos, tmp_path):
    from backend.app.social_media import media_path, prepare_media
    from backend.app.media_export_quality import MediaQualityError
    source = 'https://www.youtube.com/shorts/abcdef'
    cache = media_path(source, 'youtube_shorts', tmp_path, 'full')
    cache.parent.mkdir(parents=True)
    shutil.copy2(videos['low'], cache)
    before = cache.read_bytes()
    calls = []
    def low_download(command, **kwargs):
        calls.append(command)
        shutil.copy2(videos['low'], Path(command[command.index('-o') + 1]))
    with pytest.raises(MediaQualityError):
        prepare_media(source, 'youtube_shorts', tmp_path, 'full', runner=low_download, python='python')
    assert cache.read_bytes() == before
    assert 'bv*+ba' in calls[0][calls[0].index('-f') + 1]
    def hd_download(command, **kwargs):
        shutil.copy2(videos['hd'], Path(command[command.index('-o') + 1]))
    assert prepare_media(source, 'youtube_shorts', tmp_path, 'full', runner=hd_download, python='python') == cache
    assert cache.read_bytes() == videos['hd'].read_bytes()


def test_user_facing_issue_explains_low_resolution():
    from types import SimpleNamespace
    from backend.app.resolve_media_issues import download_issue
    from backend.app.media_export_quality import MediaQualityError
    candidate = SimpleNamespace(provider='youtube_shorts', asset_id='a', chunk_id='b', title='test', source_page='https://youtube.com/shorts/a')
    issue = download_issue(candidate, MediaQualityError('Video 640x360: richiesti almeno 720p'))
    assert issue['reason'] == 'low_resolution'
    assert '640x360' in issue['message'] and '720' in issue['message']


def test_plain_zip_reports_and_excludes_low_quality_instead_of_packing_it(videos, tmp_path):
    import json
    import zipfile
    from backend.app.media_pack_export import create_media_pack
    root = tmp_path / 'project'
    root.mkdir()
    low = root / 'low.mp4'
    high = root / 'hd.mp4'
    shutil.copy2(videos['low'], low)
    shutil.copy2(videos['hd'], high)
    def clip(path, ident):
        return {'asset_id': ident, 'beat_id': ident, 'provider': 'pexels', 'kind': 'video',
                'title': ident, 'media_path': str(path), 'track_index': 2,
                'record_start_frame': 0, 'record_end_frame': 25, 'source_start_frame': 0,
                'source_end_frame': 25, 'duration_frames': 25}
    out = tmp_path / 'out.zip'
    create_media_pack(out, project_id='x', project_name='test', project_root=root,
                      timeline={'fps':25, 'duration_frames':25, 'clips':[clip(low,'low'), clip(high,'high')]})
    with zipfile.ZipFile(out) as z:
        manifest = json.loads(z.read('manifest.json'))
        assert any(row['label']=='low' and '720' in row['reason'] for row in manifest['missing'])
        assert any(row['title']=='high' for row in manifest['media'])
        assert not any(name.endswith('/low.mp4') for name in z.namelist())


def test_timeline_export_never_uses_preview_as_final_even_if_hd(videos, tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from backend.app.curation_project import ProjectStore
    from backend.app.curation_server import create_app
    import backend.app.curation_artifacts as artifacts
    root = tmp_path / 'projects'
    probe = lambda _: {'duration':1, 'fps':25, 'width':1280, 'height':720, 'has_audio':False}
    store = ProjectStore(root, probe_runner=probe)
    project = store.create('Quality')
    run = root / project.project_id / 'run'
    run.mkdir(exist_ok=True)
    (run / 'selection-plan.json').write_text(json.dumps({'chunks': {'b': {'selected_assets': [{'asset_id':'tiktok:1'}]}}}))
    (run / 'visual-plan.json').write_text(json.dumps({'visual_beats': [{'id':'b', 'start':0, 'end':1}]}))
    candidate = SimpleNamespace(kind='video', provider='tiktok', source_page='https://www.tiktok.com/@a/video/1',
                                local_asset_path=str(videos['hd']), preview_path=str(videos['hd']),
                                source_start_seconds=0, source_end_seconds=1, title='test')
    monkeypatch.setattr(artifacts, 'load_curation_run', lambda _: SimpleNamespace(candidate_index={'tiktok:1':candidate}))
    app = create_app(project_root=root, probe_runner=probe)
    route = next(r for r in app.routes if r.path.endswith('/exports/media-pack.zip'))
    env = dict(zip(route.endpoint.__code__.co_freevars, route.endpoint.__closure__))
    timeline = env['broll_timeline_payload'].cell_contents(project.project_id, allow_unavailable=True, fps_override=25)
    assert not timeline['clips']
    assert 'anteprima' in timeline['unavailable'][0]['reason'].lower()


def test_pexels_discovery_requires_a_real_hd_rendition():
    from backend.app.online_assets import _best_rendition
    low = {'id':1, 'width':640, 'height':360, 'file_type':'video/mp4', 'link':'https://example.test/sd.mp4'}
    high = {'id':2, 'width':1280, 'height':720, 'file_type':'video/mp4', 'link':'https://example.test/hd.mp4'}
    assert _best_rendition([low], 'landscape') is None
    assert _best_rendition([low, high], 'landscape')['id'] == 2


def test_pexels_replaces_low_cache_only_after_hd_download(videos, tmp_path, monkeypatch):
    import asyncio
    import httpx
    from backend.app import stock_export_media as stock
    root = tmp_path / 'run'
    cached = stock.stock_media_path(root, '123')
    cached.parent.mkdir(parents=True)
    shutil.copy2(videos['low'], cached)
    cached.with_suffix('.json').write_text('{}')
    async def metadata(_):
        return {'selected_rendition_url':'https://example.test/hd.mp4'}
    monkeypatch.setattr(stock, 'pexels_metadata', metadata)
    client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=videos['hd'].read_bytes()))
    monkeypatch.setattr(stock.httpx, 'AsyncClient', lambda **kw: client(transport=transport, **kw))
    result = asyncio.run(stock.prepare_pexels_video(root, '123'))
    assert cached.read_bytes() == videos['hd'].read_bytes()
    assert result['duration'] > 0


def test_envato_format_picker_prefers_4k_over_1080_and_720():
    import json
    from backend.app.envato_auto_download import RESOLUTION_SCRIPT
    node = shutil.which('node')
    if not node:
        pytest.skip('node non disponibile')
    script = '''
      let picked = '';
      const options = ['720p', '1920 x 1080', '4K'].map(s => ({
        innerText:s, textContent:s, getBoundingClientRect:()=>({width:1,height:1}), click:()=>{picked=s}
      }));
      const button={getBoundingClientRect:()=>({width:1,height:1}),click:()=>{}};
      global.document={querySelectorAll:(s)=>s.includes('trigger')?[button]:options};
      (async()=>{const result=await (SCRIPT)();process.stdout.write(JSON.stringify({result,picked}));})();
    '''.replace('SCRIPT', RESOLUTION_SCRIPT)
    result = json.loads(subprocess.run([node, '-e', script], capture_output=True, text=True, check=True).stdout)
    assert result['picked'] == '4K'
