"""Bounded, per-provider discovery with durable query and verified-shot caches."""
import asyncio
import copy
import time
import os
from dataclasses import asdict, is_dataclass
from pathlib import Path
from types import SimpleNamespace
from .funnel_cache import JsonCache


async def discover_shot(engine, queries, expanded, budgets, minimum, maximum, orientation):
    if not hasattr(engine, '_discovery_gate'):
        engine._discovery_gate = asyncio.Semaphore(6)
        engine._provider_locks = {}
    root = getattr(getattr(engine,'cache',None), 'root', None)
    cache = JsonCache(Path(root)/'search', 'provider-search-v4') if root else None

    async def search(source, query):
        provider = str(getattr(source, 'provider_name', '') or type(source).__name__)
        try:
            variation_round = max(0, int(__import__('json').loads(os.environ.get('RAMBLA_SOCIAL_SEARCH_OPTIONS','{}') or '{}').get('variation_round') or 0))
        except (TypeError, ValueError):
            variation_round = 0
        key = [provider, query, orientation, minimum, maximum, getattr(engine,'max_results_per_query',8),
               [getattr(s,'provider_name','') for s in (getattr(source,'vertical_sources',None) or [])], variation_round]
        social = provider in {'tiktok', 'instagram'}
        cached = cache.get(key, 3600) if cache and not social else None
        if cached is not None:
            detail = {**cached['attempt'], 'cache_hit': True, 'search_seconds': 0.0}
            return (id(source),query), ([SimpleNamespace(**r) for r in cached['rows']], None, detail)
        # Adapters expose last_attempt: snapshot it under a per-source lock.
        lock = engine._provider_locks.setdefault(id(source), asyncio.Lock())
        async with engine._discovery_gate, lock:
            started=time.perf_counter()
            rows,error=await engine._search_one(source,query,orientation=orientation,min_duration=minimum,max_duration=maximum)
            detail=copy.deepcopy(getattr(source,'last_attempt',{}) or {})
            drain=getattr(source,'drain_vertical_attempts',None)
            if callable(drain):
                detail['vertical_attempts']=[a for a in drain() if a.get('provider') != provider]
            detail.update(cache_hit=False,search_seconds=round(time.perf_counter()-started,4))
            issue=' '.join(str(detail.get(k) or '') for k in ('error','browser_error','browser_error_detail'))
            reason=next((r for r in ('challenge_required','login_required') if r in issue),None)
            callback=getattr(engine,'event_callback',None)
            if callback and (reason or error or detail.get('error') or detail.get('browser_error')):
                callback('provider_attention',None,'Provider requires attention',provider=provider,query=query,reason=reason or 'provider_request_failed')
        if cache and not social and not error and not detail.get('error') and not any(r.get('error') for r in detail.get('vertical_attempts',[])):
            cache.put(key,{'rows':[asdict(r) if is_dataclass(r) else vars(r) for r in rows],'attempt':detail})
        return (id(source),query),(rows,error,detail)

    jobs=[]
    for source in engine.sources:
        provider=str(getattr(source,'provider_name','') or type(source).__name__).casefold()
        for query in expanded[:budgets.get(provider,2)]:
            jobs.append(search(source,query))
    return dict(await asyncio.gather(*jobs))


async def cached_source_video_beat(engine, **kwargs):
    from .quality_video import source_video_beat
    root=getattr(engine.cache,'root',None)
    cache=JsonCache(Path(root)/'verified-shots','verified-shot-v7') if root else None
    key=[kwargs,getattr(engine,'beat_context',{}),os.environ.get('RAMBLA_SOCIAL_EXCLUDED_KEYS','[]'),os.environ.get('RAMBLA_SOCIAL_SEARCH_OPTIONS','{}'),os.environ.get('RAMBLA_RETRIEVAL_RANKING','auto'),[(getattr(s,'provider_name',type(s).__name__),
                  [getattr(v,'provider_name','') for v in (getattr(s,'vertical_sources',None) or [])]) for s in engine.sources]]
    started=time.perf_counter()
    social = any(getattr(s,'provider_name','') in {'tiktok','instagram'} for s in engine.sources)
    old=cache.get(key,300) if cache and not social else None
    if old and all(Path(r.get('preview_path') or '').is_file() for r in old.get('candidates',[])):
        old['cache_hit']=True
        old['cached_timings']=old.get('timings',{})
        old['timings']={k:0.0 for k in old.get('timings',{})}
        old['timings']['total_seconds']=round(time.perf_counter()-started,4)
        for row in old.get('search_attempts',[]):row['cache_hit']=True
        for row in old.get('provider_counts',{}).values():
            row.update(requests=0,previews_downloaded=0,clips_downloaded=0)
        return old
    result=await source_video_beat(engine,**kwargs)
    if cache and not social:
        cache.put(key,result)
    return result
