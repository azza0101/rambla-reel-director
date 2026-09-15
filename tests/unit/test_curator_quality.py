import json
from pathlib import Path
import uuid
import pytest


def root():
    value = Path.cwd() / '.test-debug-cli' / uuid.uuid4().hex
    value.mkdir(parents=True)
    return value


def test_atomic_replace_retries_unique_temp(monkeypatch):
    from backend.app import atomic_io
    directory = root()
    target = directory / 'transcript.json'
    target.write_text('{"old":true}')
    replace = atomic_io.os.replace
    seen = []
    def flaky(src, dst):
        seen.append(src)
        if len(seen) < 3:
            assert json.loads(target.read_text()) == {'old': True}
            raise PermissionError('sharing violation')
        replace(src, dst)
    monkeypatch.setattr(atomic_io.os, 'replace', flaky)
    monkeypatch.setattr(atomic_io.time, 'sleep', lambda _: None)
    atomic_io.write_json(target, {'new': True})
    assert len(seen) == 3 and seen[0].name != 'transcript.json.tmp'
    assert json.loads(target.read_text()) == {'new': True}
    assert not list(directory.glob('*.tmp'))


def test_project_stage_lock_rejects_second_worker_and_releases():
    from backend.app.project_lock import project_stage_lock
    directory = root()
    with project_stage_lock(directory):
        with pytest.raises(RuntimeError, match='already running'):
            with project_stage_lock(directory):
                pytest.fail('concurrent project writer admitted')
    with project_stage_lock(directory):
        pass


def test_discovery_thumbnail_never_claims_playable():
    from backend.app.curation_artifacts import load_curation_run
    directory = root()
    (directory/'semantic-chunks.json').write_text('[{"id":"c1","text":"test"}]')
    (directory/'thumb.jpg').write_bytes(b'not video')
    (directory/'online-candidates.json').write_text(json.dumps([{'parent_beat_id':'c1','candidates':[{'id':'youtube:one','source':'youtube','source_page':'https://youtube.com/watch?v=one','preview_path':str(directory/'thumb.jpg')}]}]))
    candidate = load_curation_run(directory).chunks[0].video_candidates[0]
    assert candidate.preview_status == 'discovery'
    assert candidate.poster_path == str(directory/'thumb.jpg')
    assert candidate.local_asset_path is None


def test_quality_dedupes_same_scene_and_cross_chunk():
    from backend.app.media_quality import diverse_candidates
    candidates = [dict(id='a', source_page='https://a/1', score=.8, perceptual_hash='0'*16), dict(id='b',source_page='https://b/2',score=.7,perceptual_hash='0'*15+'1'), dict(id='c',source_page='https://c/3',score=.6,perceptual_hash='f'*16)]
    selected, rejected = diverse_candidates(candidates, [], limit=4)
    assert [c['id'] for c in selected] == ['a','c']
    assert rejected == 1
    next_chunk, rejected = diverse_candidates(candidates, selected, limit=4)
    assert next_chunk == [] and rejected == 3


@pytest.mark.asyncio
async def test_google_official_image_boundary_and_sanitized_failure():
    import httpx
    from backend.app.image_sources import GoogleImageSource
    async def handler(request):
        assert request.url.params['searchType'] == 'image'
        assert request.url.params['imgSize'] == 'xlarge'
        return httpx.Response(200, json={'items':[{'title':'Chef chopping onions','link':'https://images.example/full.jpg','image':{'contextLink':'https://example/photo','width':1800,'height':1200}}]})
    rows = await GoogleImageSource('secret','engine',transport=httpx.MockTransport(handler)).search('chef chopping onions',limit=3)
    assert rows[0].width == 1800 and rows[0].rights_state == 'review_required'


def test_cross_chunk_duplicate_rate_measures_retained_visuals():
    from backend.app.media_quality import cross_chunk_duplicate_rate
    assert cross_chunk_duplicate_rate([[{"source_page": "a"}], [{"source_page": "a"}, {"source_page": "b"}]]) == 1/3
    assert cross_chunk_duplicate_rate([]) == 0
