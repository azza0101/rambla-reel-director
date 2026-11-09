import asyncio
import json
from types import SimpleNamespace


def test_manual_envato_search_keeps_provider_results_without_title_filter(monkeypatch):
    from backend.app.envato_source import EnvatoRemoteCandidate
    from backend.app.quality_video import source_video_beat
    query = 'livno bosnia duman'
    candidate = EnvatoRemoteCandidate(provider='envato', provider_id='test', query=query,
        source_page='https://elements.envato.com/example-ABCDEF', creator_name=None, creator_page=None,
        title='Aerial drone view of Tekija in Blagaj', description='Aerial drone view of Tekija in Blagaj',
        duration=20, width=640, height=360, orientation='landscape', preview_url='https://example.com/img.jpg',
        selected_rendition_url='https://elements.envato.com/example-ABCDEF', rendition_width=640,
        rendition_height=360, rights_state='subscription_license_required', provider_rank=0)
    seen = []
    async def search(source, text, **kwargs):
        seen.append(text)
        return [candidate], None
    engine=SimpleNamespace(sources=[SimpleNamespace(provider_name='envato')],query_intents={},
        _search_one=search, ranker=SimpleNamespace(),beat_context={})
    monkeypatch.setenv('RAMBLA_SOCIAL_SEARCH_OPTIONS',json.dumps({'query_overrides': {'*':query}}))
    result=asyncio.run(source_video_beat(engine,beat_id='b:shot:s1',client_id='test',queries=['other'],
        min_duration=1,max_duration=180,orientation=None,retrieval_intent='other'))
    assert seen == [query]
    assert any(row['provider_id']=='test' for row in result['discovery_sources'])
