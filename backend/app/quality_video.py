"""Provider-separated clip retrieval. Thumbnails can discover, never verify clips."""
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from functools import lru_cache
from .range_media import range_media
from .retrieval_quality import metadata_quality,expand_queries
from .video_preview import materialize_clip,download_preview_proxy,probe_preview
from .media_quality import perceptual_hash,diverse_candidates

QUALITY_VERSION='clip-quality-9'


def temporal_starts(duration,provider):
    if duration<=3.5:return [0.0]
    fractions=(.03,.18,.36,.54,.72,.93) if provider=='youtube' else (.05,.35,.65,.9)
    return sorted(set(round((duration-3.5)*f,3) for f in fractions))


@lru_cache(maxsize=64)
def _youtube_url(url):
    result=subprocess.run([sys.executable,'-m','yt_dlp','--no-playlist','--no-warnings',
        '--socket-timeout','10','--retries','0','--skip-download','--dump-single-json',
        '-f','bv*[height<=480][ext=mp4][protocol=https]',url],
        check=True,capture_output=True,text=True,encoding='utf-8',timeout=25)
    return json.loads(result.stdout)['url']


def _youtube_clip(url,directory,identity,start):
    directory.mkdir(parents=True,exist_ok=True)
    key=hashlib.sha256((identity+'|preview-v2|'+str(start)).encode()).hexdigest()[:24]
    cached=directory/(key+'.mp4')
    if probe_preview(str(cached))['playable']:
        return materialize_clip(str(cached),directory,identity,start_seconds=start)
    with range_media(_youtube_url(url)) as local_source:
        return materialize_clip(local_source,directory,identity,start_seconds=start,streaming=True)


def _frame_samples(clip):
    path=Path(clip['preview_path']);frames=[]
    for second in (.5,2.5):
        frame=path.with_name(path.stem+f'-{second}.jpg')
        if not frame.exists():
            subprocess.run(['ffmpeg','-v','error','-y','-ss',str(second),'-i',str(path),'-frames:v','1',str(frame)],check=True,capture_output=True,timeout=15)
        frames.append(str(frame))
    return frames


async def source_video_beat(engine,*,beat_id,client_id,queries,min_duration,max_duration,orientation,retrieval_intent=None,**ignored):
    output={'beat_id':beat_id,'queries':queries,'candidates':[],'rejected_candidates':[],'errors':[],
        'search_attempts':[],'preview_cache_hits':0,'selected_cache_hit':False,
        'proposals':{'proposal_A':None,'proposal_B':None,'proposal_C':None},'quality_version':QUALITY_VERSION}
    def emit(message,**data):
        callback=getattr(engine,'event_callback',None)
        if callback:callback('online_search',None,message,slot_id=beat_id,**data)
    # Separate budgets mean Social results cannot starve Stock.
    for source in sorted(engine.sources,key=lambda s:0 if type(s).__name__=='PexelsSource' else 1):
        pool=[];seen=set()
        for query_index,query in enumerate(expand_queries(queries,'video')):
            emit('Searching video source',provider=type(source).__name__,query=query)
            rows,error=await engine._search_one(source,query,orientation=orientation,min_duration=min_duration,max_duration=max_duration)
            output['search_attempts'].append({'provider':type(source).__name__,'query':query,'hits':len(rows),'expanded':query not in queries})
            if error:output['errors'].append(error)
            for row in rows:
                if row.provider_id not in seen:pool.append(row);seen.add(row.provider_id)
            if len(pool)>=8 and query_index>=1:break
        intent=retrieval_intent or next((engine.query_intents.get(q) for q in queries if engine.query_intents.get(q)),queries[0])
        pool.sort(key=lambda c:metadata_quality(c.query,c.title+' '+c.description)[0],reverse=True)
        accepted=[];pending=[]
        for candidate in pool[:4]:
            asset_id=f'{candidate.provider}:{candidate.provider_id}'
            meta,contradictions,missing,generic=metadata_quality(intent,candidate.title+' '+candidate.description)
            # Discovery metadata can prioritize sources, never reject actual footage.
            try: preview=await engine.cache.materialize_preview(candidate)
            except Exception as exc:
                output['errors'].append({'provider':candidate.provider,'code':'poster_failed','error_type':type(exc).__name__});continue
            output['preview_cache_hits']+=int(preview.cache_hit)
            base={'id':asset_id,'client_id':client_id,'source':candidate.provider,'provider':candidate.provider,
                'provider_id':candidate.provider_id,'source_page':candidate.source_page,'source_url':candidate.source_page,
                'title':candidate.title,'description':candidate.description or candidate.title,'query':candidate.query,'matched_query':candidate.query,
                'width':candidate.width,'height':candidate.height,'orientation':candidate.orientation,
                'rights_state':candidate.rights_state,'license_name':'Pexels License' if candidate.provider=='pexels' else None,
                'license_url':'https://www.pexels.com/license/' if candidate.provider=='pexels' else None,'attribution':candidate.creator_name,
                'path':str(preview.path),'preview_path':str(preview.path),'poster_path':str(preview.path),'keyframe_path':str(preview.path),
                'kind':'image','preview_status':'preview_pending','quality_state':'source_found','score':round(meta*.6,4),
                'source_start_seconds':None,'source_end_seconds':None,'clip_verified':False,'selected_full_download':False}
            duration=float(candidate.duration)
            starts=temporal_starts(duration,candidate.provider)
            measured=[]
            for start in starts:
                emit('Materializing bounded clip',provider=candidate.provider,query=candidate.query,source_start_seconds=start,source_end_seconds=start+3.5)
                try:
                    folder=Path(preview.path).parent/'quality-clips'
                    if candidate.provider=='pexels':
                        clip=await asyncio.to_thread(materialize_clip,candidate.preview_rendition_url or candidate.selected_rendition_url,folder,asset_id,start_seconds=start)
                    else: clip=await asyncio.to_thread(_youtube_clip,candidate.source_page,folder,asset_id,start)
                    frames=await asyncio.to_thread(_frame_samples,clip)
                    frame_rows=[{**base,**clip,'id':asset_id+f':frame:{i}','kind':'video','path':clip['preview_path'],'keyframe_path':frame} for i,frame in enumerate(frames)]
                    emit('Ranking actual clip frames',provider=candidate.provider,query=candidate.query,frames=len(frames))
                    scored=engine.ranker.rank(intent,frame_rows)
                    score=sum(r['score'] for r in scored)/max(1,len(scored))
                    verified=len(scored)==len(frames) and bool(scored) and all(r.get('quality_state') in {'accepted','needs_review'} for r in scored)
                    row={**base,**clip,'kind':'video','score':round(score,4),'frame_scores':[r['score'] for r in scored],
                        'embedding_score':sum(r['embedding_score'] for r in scored)/len(scored) if scored and all(r.get('embedding_score') is not None for r in scored) else None,
                        'quality_state':('needs_review' if any(r.get('quality_state')=='needs_review' for r in scored) else 'accepted') if verified else 'metadata_only','clip_verified':verified,
                        'rank_reason':'Sampled clip frames ranked against supplied shot','preview_status':'ready',
                        'localization_method':'sampled source window; frame relevance checked' if verified else 'sampled source window; relevance unverified',
                        'quality_reasons':[reason for r in scored for reason in r.get('quality_reasons',[])]}
                    row['perceptual_hash']=perceptual_hash(Path(frames[0]));measured.append(row)
                    emit('Clip quality measured',provider=candidate.provider,score=row['score'],clip_verified=verified)
                except Exception as exc:
                    output['errors'].append({'provider':candidate.provider,'code':'clip_preview_failed','error_type':type(exc).__name__})
                    if not measured:break
            if measured:
                best=max(measured,key=lambda r:(r['clip_verified'],r['score']))
                if best['score']>=.50 and best['clip_verified']:accepted.append(best)
                else:output['rejected_candidates'].append({k:best.get(k) for k in ('id','source','source_url','matched_query','score','frame_scores','source_start_seconds','source_end_seconds','quality_reasons')})
            else:
                pending.append(base)
            if len(accepted)>=3:break
        accepted,_=diverse_candidates(sorted(accepted,key=lambda r:-r['score']),[],limit=3)
        # Pending entries are leads, not final/selectable clip suggestions.
        output['candidates'].extend(accepted[:3])
        output.setdefault('discovery_sources',[]).extend(pending)
    output['eligible_candidate_count']=sum(c.get('clip_verified',False) for c in output['candidates'])
    output['raw_result_count']=sum(r['hits'] for r in output['search_attempts'])
    output['ranking_warning']=getattr(engine.ranker,'warning',None)
    return output
