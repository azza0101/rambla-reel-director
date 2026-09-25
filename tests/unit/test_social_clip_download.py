from dataclasses import replace
from types import SimpleNamespace
from fastapi.testclient import TestClient
from backend.app.curation import CurationCandidate


def test_download_only_serves_verified_local_clip_inside_project(monkeypatch, tmp_path):
    from backend.app import debug_server as server
    root = tmp_path/'projects'
    client = TestClient(server.create_app(project_root=root, allowed_media_roots=[tmp_path]))
    pid = client.post('/api/curation/projects',json={'name':'Download'}).json()['project_id']
    folder = root/pid/'run'; folder.mkdir(parents=True,exist_ok=True)
    clip = folder/'clip.mp4'; clip.write_bytes(b'video-test')
    candidate = CurationCandidate('clip','beat','video','tiktok','https://www.tiktok.com/@x/video/1','Wing','',.8,'review_required','portrait',preview_path=str(clip),preview_status='ready',clip_verified=True)
    items = {'clip':candidate}
    monkeypatch.setattr(server,'load_curation_run',lambda _: SimpleNamespace(candidate_index=items))
    url = f'/api/curation/projects/{pid}/media/clip/download'
    response = client.get(url)
    assert response.status_code == 200 and response.content == b'video-test'
    assert 'attachment' in response.headers['content-disposition']
    items['clip'] = replace(candidate,clip_verified=False)
    assert client.get(url).status_code == 404
    outside = tmp_path/'outside.mp4'; outside.write_bytes(b'private')
    items['clip'] = replace(candidate,preview_path=str(outside))
    assert client.get(url).status_code == 403


def test_on_demand_media_uses_candidate_url_and_keeps_unverified_state(monkeypatch,tmp_path):
    from backend.app import debug_server as server, social_media
    root=tmp_path/'projects'
    client=TestClient(server.create_app(project_root=root,allowed_media_roots=[tmp_path]))
    pid=client.post('/api/curation/projects',json={'name':'Social'}).json()['project_id']
    candidate=CurationCandidate('tt','beat','video','tiktok','https://www.tiktok.com/@x/video/123','Wing','',.5,'review_required','portrait')
    monkeypatch.setattr(server,'load_curation_run',lambda _:SimpleNamespace(candidate_index={'tt':candidate}))
    calls=[]
    def prepare(source,provider,folder,mode,**kwargs):
        calls.append((source,mode))
        p=social_media.media_path(source,provider,folder,mode)
        p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'mp4');return p
    monkeypatch.setattr(social_media,'prepare_media',prepare)
    url=f'/api/curation/projects/{pid}/social-media/tt'
    assert client.get(url+'/full').status_code==404
    prepared=client.post(url+'/preview').json()
    assert prepared['verified'] is False
    assert client.get(prepared['url']).content==b'mp4'
    full=client.post(url+'/full').json()
    assert 'attachment' in client.get(full['url']).headers['content-disposition']
    assert calls==[(candidate.source_page,'preview'),(candidate.source_page,'full')]
    assert client.post(url+'/invalid').status_code==404
