import asyncio
from pathlib import Path
import shutil
import uuid
import httpx
from backend.app import stock_export_media as stock


def test_download_reports_bytes_and_reuses_completed_file(monkeypatch):
    root=Path('.stock-progress-tests')/uuid.uuid4().hex
    calls=[]
    async def metadata(_):return {'selected_rendition_url':'https://example.test/video.mp4'}
    original=httpx.AsyncClient
    transport=httpx.MockTransport(lambda request: httpx.Response(200,content=b'video-data'))
    monkeypatch.setattr(stock,'pexels_metadata',metadata)
    monkeypatch.setattr(stock.httpx,'AsyncClient',lambda **kw:original(transport=transport,**kw))
    monkeypatch.setattr(stock,'probe_preview',lambda _: {'duration':2,'width':1920})
    try:
        asyncio.run(stock.prepare_pexels_video(root,'123',progress=lambda n,total:calls.append((n,total))))
        assert calls[-1]==(10,10)
        assert stock.stock_media_path(root,'123').read_bytes()==b'video-data'
        calls.clear()
        asyncio.run(stock.prepare_pexels_video(root,'123',progress=lambda *args:calls.append(args)))
        assert calls==[]
    finally:
        if root.exists():shutil.rmtree(root)


def test_stalled_download_retries_then_reports_failure(monkeypatch):
    root=Path('.stock-progress-tests')/uuid.uuid4().hex;requests=[]
    async def metadata(_):return {'selected_rendition_url':'https://example.test/video.mp4'}
    def fail(request):requests.append(request);raise httpx.ReadTimeout('stalled')
    original=httpx.AsyncClient;transport=httpx.MockTransport(fail)
    monkeypatch.setattr(stock,'pexels_metadata',metadata)
    monkeypatch.setattr(stock.httpx,'AsyncClient',lambda **kw:original(transport=transport,**kw))
    try:
        try:asyncio.run(stock.prepare_pexels_video(root,'123'))
        except ValueError as exc:assert '30 secondi' in str(exc)
        else:raise AssertionError('must not report a stalled file as ready')
        assert len(requests)==2
        assert not stock.stock_media_path(root,'123').exists()
    finally:
        if root.exists():shutil.rmtree(root)
