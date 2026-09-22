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
from .video_preview import materialize_clip,probe_preview
from .media_quality import perceptual_hash,diverse_candidates
from .social_acquisition import download_authenticated_section, fallback_acquisition_state, profile_root_from_env

QUALITY_VERSION='clip-quality-13'
VERTICAL_PROVIDERS={'youtube_shorts','tiktok','instagram'}


def temporal_starts(duration,provider):
    if duration<=3.5:return [0.0]
    if provider=='youtube': fractions=(.03,.18,.36,.54,.72,.93)
    elif provider in VERTICAL_PROVIDERS: fractions=(.05,.34,.63,.9)
    else: fractions=(.05,.35,.65,.9)
    return sorted(set(round((duration-3.5)*f,3) for f in fractions))


@lru_cache(maxsize=128)
def _direct_media_url(url,provider):
    selector=('bv*[height<=480][ext=mp4][protocol=https]'
              if provider in {'youtube','youtube_shorts'}
              else 'b[height<=720][ext=mp4]/best[height<=720]/best')
    result=subprocess.run([sys.executable,'-m','yt_dlp','--no-playlist','--no-warnings',
        '--socket-timeout','10','--retries','0','--skip-download','--dump-single-json',
        '-f',selector,url],check=True,capture_output=True,text=True,encoding='utf-8',timeout=25)
    payload=json.loads(result.stdout)
    media=payload.get('url')
    if not media:raise ValueError('yt-dlp did not expose a direct media URL')
    return media


@lru_cache(maxsize=64)
def _youtube_url(url):
    return _direct_media_url(url,'youtube')


def _youtube_clip(url,directory,identity,start):
    directory.mkdir(parents=True,exist_ok=True)
    with range_media(_youtube_url(url)) as local_source:
        return materialize_clip(local_source,directory,identity,start_seconds=start,streaming=True)


def _range_clip(url,directory,identity,start,provider):
    directory.mkdir(parents=True,exist_ok=True)
    key=hashlib.sha256((identity+'|range-preview-v3|'+str(start)).encode()).hexdigest()[:24]
    cached=directory/(key+'.mp4')
    if probe_preview(str(cached))['playable']:
        facts=probe_preview(str(cached));poster=directory/(key+'.jpg')
        if not poster.is_file():subprocess.run(['ffmpeg','-v','error','-y','-ss','1','-i',str(cached),'-frames:v','1',str(poster)],check=True,capture_output=True,timeout=20)
        return {'preview_path':str(cached),'poster_path':str(poster),'keyframe_path':str(poster),'preview_status':'ready','preview_duration':facts['duration'],'preview_mime':facts['mime'],'preview_width':facts.get('width',0),'preview_height':facts.get('height',0),'source_start_seconds':start,'source_end_seconds':start+facts['duration']}
    with range_media(_direct_media_url(url,provider)) as local_source:return materialize_clip(local_source,directory,identity,start_seconds=start,streaming=True)


def _section_clip(url,directory,identity,start,provider):
    """Use authenticated yt-dlp first, then the public bounded section path."""
    directory.mkdir(parents=True,exist_ok=True);key=hashlib.sha256((identity+'|social-section-v2|'+str(start)).encode()).hexdigest()[:24];raw=directory/(key+'-source.mp4')
    if not raw.is_file() or raw.stat().st_size==0:
        end=start+3.5
        profile_root=profile_root_from_env();profile_dir=profile_root/provider
        authenticated=False
        if profile_dir.is_dir():
            try:
                download_authenticated_section(url,provider,raw,start=start,duration=3.5,profile_root=profile_root)
                authenticated=True
            except Exception:
                raw.unlink(missing_ok=True)
        if not authenticated:
            subprocess.run([sys.executable,'-m','yt_dlp','--no-playlist','--no-warnings','--socket-timeout','10','--retries','0','--download-sections',f'*{start:.3f}-{end:.3f}','--force-keyframes-at-cuts','-f','b[height<=720]/best[height<=720]/best','--merge-output-format','mp4','-o',str(raw),url],check=True,capture_output=True,text=True,encoding='utf-8',timeout=45)
    clip=materialize_clip(str(raw),directory,identity+f':{provider}:section:{start:.3f}',start_seconds=0);clip['source_start_seconds']=start;clip['source_end_seconds']=start+float(clip['preview_duration']);return clip


def _social_clip(url,directory,identity,start,provider):
    if provider=='youtube':return _youtube_clip(url,directory,identity,start)
    if provider=='youtube_shorts':return _range_clip(url,directory,identity,start,provider)
    if provider in {'tiktok','instagram'}:return _section_clip(url,directory,identity,start,provider)
    return _range_clip(url,directory,identity,start,provider)


def _frame_samples(clip):
    path=Path(clip['preview_path']);frames=[]
    for second in (.5,2.5):
        frame=path.with_name(path.stem+f'-{second}.jpg')
        if not frame.exists():subprocess.run(['ffmpeg','-v','error','-y','-ss',str(second),'-i',str(path),'-frames:v','1',str(frame)],check=True,capture_output=True,timeout=15)
        frames.append(str(frame))
    return frames


def _provider_name(source):return str(getattr(source,'provider_name','') or type(source).__name__)


def _verified_portrait_clip(clip):
    """Final vertical gate: trust the materialized media, never search metadata."""
    facts=probe_preview(clip.get('preview_path'))
    width=int(facts.get('width') or clip.get('preview_width') or 0)
    height=int(facts.get('height') or clip.get('preview_height') or 0)
    return bool(facts.get('playable')) and width>0 and height>width


def _discovery_scores(candidate,intent):
    text=(candidate.title+' '+candidate.description).strip()
    query_meta=metadata_quality(getattr(candidate,'query','') or intent,text)[0]
    intent_meta=metadata_quality(intent,text)[0]
    return query_meta,intent_meta


def _discovery_relevant(candidate,intent):
    """Cheap metadata gate for discovery-only cards.

    A source link/thumbnail is useful only if its title/description matches the
    actual Director query, not merely one generic noun. This prevents results
    such as a storm-damaged ferry from surfacing for "passenger ferry luggage".
    """
    query_meta,intent_meta=_discovery_scores(candidate,intent)
    return query_meta>=.40 or (query_meta>=.25 and intent_meta>=.35)


def _discovery_priority(candidate,intent):
    query_meta,intent_meta=_discovery_scores(candidate,intent)
    vertical=1 if candidate.provider in VERTICAL_PROVIDERS and candidate.orientation=='portrait' else 0
    authenticity=float(getattr(candidate,'source_authenticity',0) or 0)
    # Relevance must beat format preference. Vertical is only a tie-breaker.
    return (max(query_meta,intent_meta),query_meta,intent_meta,vertical,authenticity,-int(getattr(candidate,'provider_rank',0) or 0))


def _balanced_discovery_pool(pool,intent,limit=8):
    """Round-robin actual providers after relevance ordering.

    YouTube long-form and vertical providers share one adapter. Without this
    balancing, several vertical hits can consume the materialization budget
    before a better normal-YouTube result is even checked.
    """
    groups={}
    for candidate in sorted(pool,key=lambda c:_discovery_priority(c,intent),reverse=True):
        groups.setdefault(candidate.provider,[]).append(candidate)
    provider_order=sorted(
        groups,
        key=lambda provider:_discovery_priority(groups[provider][0],intent),
        reverse=True,
    )
    output=[]
    index=0
    while len(output)<limit:
        added=False
        for provider in provider_order:
            rows=groups[provider]
            if index<len(rows):
                output.append(rows[index]);added=True
                if len(output)>=limit:return output
        if not added:break
        index+=1
    return output


def _manual_discovery_base(candidate,asset_id,client_id,meta,*,reason,preview_path=None):
    remote_preview=str(getattr(candidate,'preview_url','') or '')
    has_preview=bool(preview_path or remote_preview)
    state=fallback_acquisition_state(has_preview=has_preview,reason=reason)
    return {'id':asset_id,'client_id':client_id,'source':candidate.provider,'provider':candidate.provider,'provider_id':candidate.provider_id,'source_page':candidate.source_page,'source_url':candidate.source_page,'title':candidate.title,'description':candidate.description or candidate.title,'query':candidate.query,'matched_query':candidate.query,'width':candidate.width,'height':candidate.height,'orientation':candidate.orientation,'rights_state':candidate.rights_state,'license_name':None,'license_url':None,'attribution':candidate.creator_name,'path':str(preview_path) if preview_path else None,'preview_path':str(preview_path) if preview_path else None,'poster_path':str(preview_path) if preview_path else None,'keyframe_path':str(preview_path) if preview_path else None,'preview_url':remote_preview or None,'kind':'video','preview_status':'preview_pending' if has_preview else 'manual','quality_state':'source_found','score':round(meta*.6,4),'source_start_seconds':None,'source_end_seconds':None,'selected_full_download':False,'source_authenticity':getattr(candidate,'source_authenticity',None),**state}


async def source_video_beat(engine,*,beat_id,client_id,queries,min_duration,max_duration,orientation,retrieval_intent=None,**ignored):
    output={'beat_id':beat_id,'queries':queries,'candidates':[],'rejected_candidates':[],'errors':[],'search_attempts':[],'preview_cache_hits':0,'selected_cache_hit':False,'proposals':{'proposal_A':None,'proposal_B':None,'proposal_C':None},'quality_version':QUALITY_VERSION}
    def emit(message,**data):
        callback=getattr(engine,'event_callback',None)
        if callback:callback('online_search',None,message,slot_id=beat_id,**data)
    priority={'pexels':0,'youtube_shorts':1,'tiktok':2,'instagram':3,'web_video':4,'youtube':5}
    for source in sorted(engine.sources,key=lambda s:priority.get(_provider_name(s).casefold(),6)):
        provider_label=_provider_name(source);pool=[];seen=set()
        for query_index,query in enumerate(expand_queries(queries,'video')):
            emit('Searching video source',provider=provider_label,query=query)
            rows,error=await engine._search_one(source,query,orientation=orientation,min_duration=min_duration,max_duration=max_duration)
            attempt={'provider':provider_label,'query':query,'hits':len(rows),'expanded':query not in queries};output['search_attempts'].append(attempt)
            drain=getattr(source,'drain_vertical_attempts',None)
            if callable(drain):
                for extra in drain():
                    extra=dict(extra);extra.setdefault('query',query);extra.setdefault('hits',0);extra['expanded']=query not in queries;output['search_attempts'].append(extra)
                    failure=extra.get('error') or extra.get('browser_error')
                    if failure:output['errors'].append({'provider':extra.get('provider'),'code':'provider_request_failed','error_type':failure})
            if error:
                output['errors'].append(error);attempt['error']=error.get('code') if isinstance(error,dict) else type(error).__name__
            for row in rows:
                key=(row.provider,row.provider_id)
                if key not in seen:pool.append(row);seen.add(key)
            if len(pool)>=8 and query_index>=1:break
        intent=retrieval_intent or next((engine.query_intents.get(q) for q in queries if engine.query_intents.get(q)),queries[0])
        pool=_balanced_discovery_pool(pool,intent,limit=8)
        accepted=[];pending=[]
        for candidate in pool:
            asset_id=f'{candidate.provider}:{candidate.provider_id}';meta,contradictions,missing,generic=metadata_quality(intent,candidate.title+' '+candidate.description)
            discovery_relevant=_discovery_relevant(candidate,intent)
            if candidate.provider in VERTICAL_PROVIDERS and candidate.orientation!='portrait':
                output['rejected_candidates'].append({'id':asset_id,'source':candidate.provider,'source_url':candidate.source_page,'matched_query':candidate.query,'score':0,'quality_reasons':['vertical-social candidate is not portrait']});continue
            try:
                preview=await engine.cache.materialize_preview(candidate)
            except Exception as exc:
                output['errors'].append({'provider':candidate.provider,'code':'poster_failed','error_type':type(exc).__name__})
                if discovery_relevant:
                    pending.append(_manual_discovery_base(candidate,asset_id,client_id,meta,reason=f'preview unavailable ({type(exc).__name__})'))
                continue
            output['preview_cache_hits']+=int(preview.cache_hit)
            base={'id':asset_id,'client_id':client_id,'source':candidate.provider,'provider':candidate.provider,'provider_id':candidate.provider_id,'source_page':candidate.source_page,'source_url':candidate.source_page,'title':candidate.title,'description':candidate.description or candidate.title,'query':candidate.query,'matched_query':candidate.query,'width':candidate.width,'height':candidate.height,'orientation':candidate.orientation,'rights_state':candidate.rights_state,'license_name':'Pexels License' if candidate.provider=='pexels' else None,'license_url':'https://www.pexels.com/license/' if candidate.provider=='pexels' else None,'attribution':candidate.creator_name,'path':str(preview.path),'preview_path':str(preview.path),'poster_path':str(preview.path),'keyframe_path':str(preview.path),'preview_url':getattr(candidate,'preview_url',None),'kind':'video','preview_status':'preview_pending','quality_state':'source_found','score':round(meta*.6,4),'source_start_seconds':None,'source_end_seconds':None,'clip_verified':False,'selected_full_download':False,'source_authenticity':getattr(candidate,'source_authenticity',None),'acquisition_state':'PREVIEW_ONLY','manual_reason':None}
            duration=float(candidate.duration);starts=temporal_starts(duration,candidate.provider);measured=[];shape_rejected=False
            for start in starts:
                emit('Materializing bounded clip',provider=candidate.provider,query=candidate.query,source_start_seconds=start,source_end_seconds=start+3.5)
                try:
                    folder=Path(preview.path).parent/'quality-clips';clip=await asyncio.to_thread(materialize_clip,candidate.preview_rendition_url or candidate.selected_rendition_url,folder,asset_id,start_seconds=start) if candidate.provider=='pexels' else await asyncio.to_thread(_social_clip,candidate.source_page,folder,asset_id,start,candidate.provider)
                    if candidate.provider in VERTICAL_PROVIDERS and not _verified_portrait_clip(clip):
                        output['rejected_candidates'].append({'id':asset_id,'source':candidate.provider,'source_url':candidate.source_page,'matched_query':candidate.query,'score':0,'source_start_seconds':clip.get('source_start_seconds'),'source_end_seconds':clip.get('source_end_seconds'),'quality_reasons':['materialized social clip is not portrait']})
                        shape_rejected=True;break
                    frames=await asyncio.to_thread(_frame_samples,clip);frame_rows=[{**base,**clip,'id':asset_id+f':frame:{i}','kind':'video','path':clip['preview_path'],'keyframe_path':frame} for i,frame in enumerate(frames)]
                    emit('Ranking actual clip frames',provider=candidate.provider,query=candidate.query,frames=len(frames));scored=engine.ranker.rank(intent,frame_rows);semantic=sum(r['score'] for r in scored)/max(1,len(scored));verified=len(scored)==len(frames) and bool(scored) and all(r.get('quality_state') in {'accepted','needs_review'} for r in scored)
                    phone_bonus=.035 if verified and candidate.provider in VERTICAL_PROVIDERS else 0
                    score=min(1.0,semantic+phone_bonus)
                    row={**base,**clip,'kind':'video','score':round(score,4),'semantic_score':round(semantic,4),'phone_native_bonus':phone_bonus,'frame_scores':[r['score'] for r in scored],'embedding_score':sum(r['embedding_score'] for r in scored)/len(scored) if scored and all(r.get('embedding_score') is not None for r in scored) else None,'quality_state':('needs_review' if any(r.get('quality_state')=='needs_review' for r in scored) else 'accepted') if verified else 'metadata_only','clip_verified':verified,'rank_reason':'Sampled clip frames ranked against editorial context'+(' · verified vertical-social bonus' if phone_bonus else ''),'preview_status':'ready','localization_method':'sampled source window; frame relevance checked' if verified else 'sampled source window; relevance unverified','quality_reasons':[reason for r in scored for reason in r.get('quality_reasons',[])],'acquisition_state':'CLIP_READY' if verified else 'PREVIEW_ONLY','manual_reason':None}
                    row['perceptual_hash']=perceptual_hash(Path(frames[0]));measured.append(row);emit('Clip quality measured',provider=candidate.provider,score=row['score'],clip_verified=verified)
                except Exception as exc:
                    output['errors'].append({'provider':candidate.provider,'code':'clip_preview_failed','error_type':type(exc).__name__})
                    if not measured:break
            if shape_rejected:
                if candidate.provider in VERTICAL_PROVIDERS:pending.append({**base,**fallback_acquisition_state(has_preview=True,reason='automatic clip was not portrait; source link retained')})
                continue
            if measured:
                best=max(measured,key=lambda r:(r['clip_verified'],r['score']))
                if best['semantic_score']>=.50 and best['clip_verified']:accepted.append(best)
                else:
                    output['rejected_candidates'].append({k:best.get(k) for k in ('id','source','source_url','matched_query','score','semantic_score','frame_scores','source_start_seconds','source_end_seconds','quality_reasons')})
                    if discovery_relevant:pending.append({**base,**fallback_acquisition_state(has_preview=True,reason='automatic clip did not pass relevance verification')})
            elif discovery_relevant:
                pending.append({**base,**fallback_acquisition_state(has_preview=True,reason='automatic clip download unavailable')})
            if len(accepted)>=3:break
        accepted,_=diverse_candidates(sorted(accepted,key=lambda r:(r.get('source') in VERTICAL_PROVIDERS,r['score']),reverse=True),[],limit=3);output['candidates'].extend(accepted[:3]);output.setdefault('discovery_sources',[]).extend(pending[:3])
    output['eligible_candidate_count']=sum(c.get('clip_verified',False) for c in output['candidates']);output['raw_result_count']=sum(r['hits'] for r in output['search_attempts']);output['ranking_warning']=getattr(engine.ranker,'warning',None);return output
