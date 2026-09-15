"""Tiered photo retrieval with bounded fallback and per-shot quality decisions."""
import asyncio
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import time
import httpx
from .atomic_io import write_json
from .image_sources import PexelsPhotoSource,GoogleImageSource,WikimediaImageSource
from .media_quality import image_quality,diverse_candidates,other_media_history,cross_chunk_duplicate_rate
from .project_config import load_project_credentials,provider_status
from .retrieval_quality import VERSION,expand_queries,QualityRanker


def configured_sources():
    load_project_credentials()
    sources=[]
    if os.environ.get('PEXELS_API_KEY'): sources.append(PexelsPhotoSource(os.environ['PEXELS_API_KEY']))
    if os.environ.get('GOOGLE_API_KEY') and os.environ.get('GOOGLE_CSE_ID'):
        sources.append(GoogleImageSource(os.environ['GOOGLE_API_KEY'],os.environ['GOOGLE_CSE_ID']))
    sources.append(WikimediaImageSource())
    return sources


async def source_images(chunks,output,plan,ranker,client_id,*,sources=None,fetcher=None,event_callback=None):
    started=time.perf_counter();output.mkdir(parents=True,exist_ok=True)
    providers=configured_sources() if sources is None else sources
    ranker=ranker or QualityRanker()
    history=[]; result={'schema_version':VERSION,'chunks':{},'active_providers':[getattr(p,'provider_name',type(p).__name__) for p in providers],
        'provider_status':provider_status(),'errors':[],'duplicates_rejected':0,'cache_reused_chunks':0,'retried_chunks':0}
    if event_callback:event_callback('image_search',0,'Photo provider configuration',**result['provider_status'])
    path=output/'image-candidates.json'
    try: cached=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError): cached={}
    signature=hashlib.sha256(json.dumps({'plan':plan,'version':VERSION,'providers':result['active_providers'],'ranking':type(ranker).__name__,'visual':bool(getattr(ranker,'visual',None))},sort_keys=True).encode()).hexdigest()
    result['quality_signature']=signature
    async def fetch(url):
        if fetcher: return await fetcher(url)
        async with httpx.AsyncClient(timeout=20,follow_redirects=True,headers={'User-Agent':'RAMBLA-Reel-Director/0.3 (https://github.com/azza0101/rambla-reel-director)'}) as client:
            response=await client.get(url);response.raise_for_status();return response.content
    for index,chunk in enumerate(chunks):
        bid=chunk['id']; beat=plan['chunks'][bid]; cross=other_media_history(output,'video',bid)
        row={'status':'searched','visual_action':beat.get('visual_action','BROLL'),'candidates':[],'rejected_candidates':[],
            'search_attempts':[],'queries':[q for s in beat['shots'] for q in s['image_queries']],'raw_count':0,'accepted_count':0,'errors':[],'active_providers':[]}
        result['chunks'][bid]=row
        if row['visual_action']!='BROLL':
            row.update(status='not_requested',zero_result_reason=row['visual_action']);continue
        old=cached.get('chunks',{}).get(bid,{})
        if cached.get('quality_signature')==signature and old.get('candidates') and all(Path(c.get('preview_path','missing')).is_file() for c in old['candidates']):
            row.update(old);row['candidates'],n=diverse_candidates(old['candidates'],history+cross,limit=4)
            row['accepted_count']=len(row['candidates']);row['cache_status']='reused';history.extend(row['candidates']);result['duplicates_rejected']+=n;result['cache_reused_chunks']+=1;continue
        result['retried_chunks']+=1
        for shot in beat['shots']:
            accepted=[];seen=set(); variants=expand_queries(shot['image_queries'],'image')
            # Finish the primary source (including expansions) before secondary/fallback.
            for provider in providers:
                provider_name=getattr(provider,'provider_name',type(provider).__name__)
                row['active_providers'].append(provider_name)
                for query in variants:
                    attempt={'provider':provider_name,'query':query,'shot_id':shot['shot_id'],'expanded':query not in shot['image_queries'],'expanded_from':shot['image_queries'] if query not in shot['image_queries'] else None}
                    row['search_attempts'].append(attempt)
                    if event_callback:event_callback('image_search',100*index/max(1,len(chunks)),'Searching photos',chunk_id=bid,**attempt)
                    try: remote=await provider.search(query,limit=6)
                    except Exception as exc:
                        attempt['error']=getattr(exc,'code',type(exc).__name__);row['errors'].append(attempt.copy());continue
                    attempt['hits']=len(remote);row['raw_count']+=len(remote)
                    pool=[]
                    for c in remote:
                        if (c.provider,c.provider_id) in seen:continue
                        seen.add((c.provider,c.provider_id))
                        if max(c.width,c.height)<1024 or min(c.width,c.height)<480:continue
                        cache=output/'image-cache';cache.mkdir(exist_ok=True)
                        local=cache/(hashlib.sha256((c.provider+':'+c.provider_id).encode()).hexdigest()[:24]+'.jpg')
                        try:
                            if not local.exists():local.write_bytes(await fetch(c.thumbnail_url))
                            quality=image_quality(local)
                            pool.append({**asdict(c),**quality,'id':c.provider+':'+c.provider_id,'client_id':client_id,'path':str(local),'preview_path':str(local),'kind':'image','source':c.provider,'description':c.description or c.title,'shot_id':shot['shot_id'],'shot_description':shot['description'],'matched_query':query})
                        except Exception as exc:row['errors'].append({'provider':c.provider,'code':'preview_failed','error_type':type(exc).__name__})
                    ranked=ranker.rank(shot['description'],pool)
                    strong=[r for r in ranked if r.get('quality_state')!='rejected' and r.get('score',0)>=.48]
                    row['rejected_candidates'].extend({k:r.get(k) for k in ('id','provider','source_page','matched_query','score','embedding_score','metadata_score','quality_reasons')} for r in ranked if r not in strong)
                    accepted,n=diverse_candidates(accepted+strong,history+cross+row['candidates'],limit=2)
                    result['duplicates_rejected']+=n;attempt['accepted']=len(accepted)
                    if len(accepted)>=2:break
                if len(accepted)>=2:break
            row['candidates'].extend(accepted)
        row['candidates'],n=diverse_candidates(row['candidates'],history+cross,limit=4)
        result['duplicates_rejected']+=n;history.extend(row['candidates']);row['accepted_count']=len(row['candidates'])
        row['zero_result_reason']=None if row['candidates'] else 'No sufficiently relevant unique image after primary, secondary and expanded fallback queries'
        row['ranking_warning']=getattr(ranker,'warning',None)
        write_json(path,result)
        if event_callback:event_callback('image_search',100*(index+1)/len(chunks),'Photo quality gate complete',chunk_id=bid,accepted=row['accepted_count'],raw=row['raw_count'],errors=row['errors'],zero_reason=row['zero_result_reason'])
    result['cross_chunk_duplicate_rate']=cross_chunk_duplicate_rate([r['candidates'] for r in result['chunks'].values()])
    result['sourcing_seconds']=round(time.perf_counter()-started,3);write_json(path,result)
    return result
