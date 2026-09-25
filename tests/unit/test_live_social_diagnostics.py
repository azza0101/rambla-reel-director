def test_live_attempts_are_visible_before_other_shots_complete():
    from backend.app.live_retrieval_diagnostics import overlay_live_rows
    rows = [{'parent_beat_id': 'other', 'search_attempts': []}]
    events = [{'data': {'slot_id': 'beat_007:shot:s1', 'search_attempts': [
        {'provider': 'tiktok', 'query': 'hens garden', 'hits': 12}]}}]
    merged = overlay_live_rows(rows, events)
    assert len(merged) == 2
    assert merged[1]['parent_beat_id'] == 'beat_007'
    assert merged[1]['search_attempts'][0]['hits'] == 12
    assert rows == [{'parent_beat_id': 'other', 'search_attempts': []}]
    assert len(overlay_live_rows(merged, events)) == 2


def test_social_thumbnail_fetches_overlap_and_report_phase(monkeypatch,tmp_path):
    import asyncio
    from types import SimpleNamespace as NS
    from backend.app.quality_video import _rank_social_discovery
    active=0; peak=0; events=[]
    class Cache:
        async def materialize_preview(self,c):
            nonlocal active,peak
            active+=1;peak=max(peak,active)
            await asyncio.sleep(.01)
            active-=1
            return NS(path=tmp_path/c.provider_id,cache_hit=True)
    class Ranker:
        def rank(self,intent,rows):return [dict(r,score=.8) for r in rows]
    pool=[NS(provider='tiktok',provider_id=str(i),title='hens',description='',query='hens',creator_name=str(i)) for i in range(5)]
    engine=NS(cache=Cache(),ranker=Ranker(),event_callback=lambda *a,**k:events.append((a,k)))
    asyncio.run(_rank_social_discovery(engine,pool,'hens',{'beat_id':'b:shot:s','errors':[],'rejected_candidates':[]},{},client_id='c'))
    assert 1 < peak <= 4
    assert any('Ranking' in e[0][2] for e in events)
