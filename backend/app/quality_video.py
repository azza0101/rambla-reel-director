"""Provider-separated clip retrieval. Thumbnails can discover, never verify clips."""
import asyncio
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import httpx
from functools import lru_cache
from .range_media import range_media
from .retrieval_quality import metadata_quality,expand_queries,terms
from .video_preview import materialize_clip,probe_preview
from .media_quality import perceptual_hash,diverse_candidates
from .social_acquisition import download_authenticated_section, fallback_acquisition_state, profile_root_from_env
from .editorial_relevance import decode_retrieval_intent

QUALITY_VERSION='clip-quality-14'
VERTICAL_PROVIDERS={'youtube_shorts','tiktok','instagram'}


def temporal_starts(duration,provider):
    """Single cheap fallback window when no better localization signal exists."""
    duration=float(duration)
    if duration<=3.5:return [0.0]
    usable=max(0.0,duration-3.5)
    if provider in VERTICAL_PROVIDERS:return [round(usable*.12,3)]
    if provider=='pexels':return [round(usable*.22,3)]
    return [round(usable*.35,3)]



@lru_cache(maxsize=64)
def _youtube_metadata(url):
    """Fetch metadata/storyboard descriptors without downloading the video."""
    result=subprocess.run([
        sys.executable,'-m','yt_dlp','--no-playlist','--no-warnings',
        '--socket-timeout','10','--retries','0','--skip-download','--dump-single-json',
        url,
    ],check=True,capture_output=True,text=True,encoding='utf-8',timeout=25)
    payload=json.loads(result.stdout)
    if not isinstance(payload,dict):raise ValueError('yt-dlp returned invalid YouTube metadata')
    return payload


def _best_storyboard_format(payload):
    formats=[
        row for row in (payload.get('formats') or [])
        if isinstance(row,dict)
        and (str(row.get('format_note') or '').casefold()=='storyboard' or str(row.get('format_id') or '').startswith('sb'))
        and isinstance(row.get('fragments'),list) and row.get('fragments')
    ]
    if not formats:return None
    return max(formats,key=lambda row:(int(row.get('width') or 0)*int(row.get('height') or 0),float(row.get('fps') or 0)))


def _storyboard_sample_indices(total,limit=6):
    total=max(0,int(total));limit=max(1,int(limit))
    if total<=limit:return list(range(total))
    # Skip the very first/last frames: intros/outros are disproportionately
    # thumbnails, logos or talking-head setup rather than usable B-roll.
    low=max(0,int(total*.04));high=min(total-1,int(total*.96))
    if high<=low:return [total//2]
    values=[]
    for i in range(limit):
        pos=low+(high-low)*(i+.5)/limit
        idx=max(0,min(total-1,int(round(pos))))
        if idx not in values:values.append(idx)
    return values


def _download_storyboard_grid(url,path,headers):
    if path.is_file() and path.stat().st_size>0:return path
    response=httpx.get(url,headers=headers or None,timeout=12,follow_redirects=True)
    response.raise_for_status()
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_bytes(response.content);temporary.replace(path)
    return path


def _youtube_storyboard_frames(url,directory,identity,max_samples=6):
    """Materialize a tiny, evenly sampled set of YouTube storyboard cells."""
    payload=_youtube_metadata(url)
    fmt=_best_storyboard_format(payload)
    if not fmt:return []
    fps=float(fmt.get('fps') or 0)
    rows=max(1,int(fmt.get('rows') or 1));cols=max(1,int(fmt.get('columns') or 1))
    cell_w=max(1,int(fmt.get('width') or 0));cell_h=max(1,int(fmt.get('height') or 0))
    fragments=[row for row in fmt.get('fragments') or [] if isinstance(row,dict) and str(row.get('url') or '').startswith(('http://','https://'))]
    if fps<=0 or not fragments or cell_w<=0 or cell_h<=0:return []
    capacity=rows*cols
    duration=float(payload.get('duration') or 0)
    estimated=int(math.ceil(duration*fps)) if duration>0 else len(fragments)*capacity
    total=min(max(1,estimated),len(fragments)*capacity)
    indices=_storyboard_sample_indices(total,max_samples)
    root=Path(directory)/'storyboard';root.mkdir(parents=True,exist_ok=True)
    headers=fmt.get('http_headers') if isinstance(fmt.get('http_headers'),dict) else {}
    grids={}
    output=[]
    key=hashlib.sha256((identity+'|storyboard-v1').encode()).hexdigest()[:18]
    for index in indices:
        frag_index=index//capacity;cell_index=index%capacity
        if frag_index>=len(fragments):continue
        grid=grids.get(frag_index)
        if grid is None:
            grid=root/f'{key}-grid-{frag_index:03d}.jpg'
            try:_download_storyboard_grid(fragments[frag_index]['url'],grid,headers)
            except Exception:continue
            grids[frag_index]=grid
        row_index=cell_index//cols;col_index=cell_index%cols
        cell=root/f'{key}-cell-{index:05d}.jpg'
        if not cell.is_file():
            x=col_index*cell_w;y=row_index*cell_h
            try:
                subprocess.run([
                    'ffmpeg','-v','error','-y','-i',str(grid),
                    '-vf',f'crop={cell_w}:{cell_h}:{x}:{y}',
                    '-frames:v','1',str(cell),
                ],check=True,capture_output=True,timeout=8)
            except Exception:
                cell.unlink(missing_ok=True);continue
        output.append({'path':str(cell),'timestamp':round(index/fps,3),'index':index})
    return output


def _choose_storyboard_starts(samples,positive_scores,talking_scores,text_scores,duration,limit=2):
    rows=[]
    for sample in samples:
        sid=str(sample['index'])
        positive=float(positive_scores.get(sid,0) or 0)
        talking=float(talking_scores.get(sid,0) or 0)
        text=float(text_scores.get(sid,0) or 0)
        negative=max(talking,text)
        if positive<.34 or negative>positive+.015:continue
        quality=positive-.45*negative
        rows.append((quality,positive,-negative,float(sample['timestamp'])))
    rows.sort(reverse=True)
    starts=[]
    for _quality,_positive,_negative,timestamp in rows:
        start=max(0.0,min(max(0.0,float(duration)-3.5),timestamp-1.2))
        if all(abs(start-existing)>=5.0 for existing in starts):
            starts.append(round(start,3))
        if len(starts)>=limit:break
    return starts


async def _storyboard_starts(engine,candidate,intent,folder,asset_id,client_id,emit):
    """Return None when storyboard is unavailable, [] when it disproves the candidate.

    A valid-but-empty storyboard is a strong negative signal: do not pay for
    random clip downloads after Qwen already failed to see the requested scene.
    """
    if candidate.provider!='youtube' or float(candidate.duration)<18:return None
    visual=getattr(engine.ranker,'visual',None)
    if visual is None:return None
    emit('Scanning YouTube storyboard',provider='youtube',query=candidate.query,duration=float(candidate.duration))
    try:
        samples=await asyncio.to_thread(
            _youtube_storyboard_frames,candidate.source_page,folder,asset_id,6
        )
    except Exception as exc:
        emit('YouTube storyboard unavailable',provider='youtube',query=candidate.query,error_type=type(exc).__name__)
        return None
    if len(samples)<2:return None
    rows=[
        {
            'id':str(sample['index']),'client_id':client_id,
            'path':sample['path'],'keyframe_path':sample['path'],'kind':'video',
            'description':'YouTube storyboard frame',
        }
        for sample in samples
    ]
    target=_visual_target(intent)
    try:
        positive={r['id']:float(r.get('embedding_score',r.get('score',0)) or 0) for r in visual.rank(target,rows)}
    except Exception as exc:
        emit('YouTube storyboard ranking unavailable',provider='youtube',error_type=type(exc).__name__)
        return None
    ranked=sorted(
        ((score,next(sample for sample in samples if str(sample['index'])==sid)) for sid,score in positive.items()),
        key=lambda item:item[0],reverse=True,
    )
    starts=[]
    for score,sample in ranked:
        if score<.39:continue
        start=max(0.0,min(max(0.0,float(candidate.duration)-3.5),float(sample['timestamp'])-1.2))
        if all(abs(start-existing)>=5 for existing in starts):starts.append(round(start,3))
        if len(starts)>=1:break
    emit('YouTube storyboard localized',provider='youtube',query=candidate.query,windows=starts,samples=len(samples))
    return starts


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
    for second in (.4,1.7,3.0):
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


def _visual_target(intent):
    spec=decode_retrieval_intent(intent)
    return spec.get('visual_target') or spec.get('positive') or str(intent or '')


def _discovery_scores(candidate,intent):
    text=(candidate.title+' '+candidate.description).strip()
    target=_visual_target(intent)
    query_meta=metadata_quality(getattr(candidate,'query','') or target,text)[0]
    intent_meta=metadata_quality(target,text)[0]
    return query_meta,intent_meta


def _discovery_relevant(candidate,intent):
    """Cheap metadata gate for discovery-only cards.

    A source link/thumbnail is useful only if its title/description matches the
    actual Director query, not merely one generic noun. This prevents results
    such as a storm-damaged ferry from surfacing for "passenger ferry luggage".
    """
    query_meta,intent_meta=_discovery_scores(candidate,intent)
    # Strong agreement with the physical shot target can rescue a provider whose
    # stored search query is noisy/aliased. Conversely, one generic query noun
    # alone is not enough.
    return intent_meta>=.60 or query_meta>=.40 or (query_meta>=.20 and intent_meta>=.35)


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


def _canonical_term_set(text):
    aliases={
        'airplane':'plane','aircraft':'plane',
        'ferry':'boat','ship':'boat',
        'travelers':'people','traveler':'people','tourists':'people','tourist':'people','passengers':'people','passenger':'people',
        'signage':'sign','signboard':'sign','signs':'sign',
        'brochures':'brochure','cards':'card',
    }
    return {aliases.get(value,value) for value in terms(str(text or ''))}


def _query_matches_target(query,target):
    q=_canonical_term_set(query);t=_canonical_term_set(target)
    if not q or not t:return True
    return bool(q & t)


def _query_from_target(target,max_words=8):
    stop={'a','an','the','of','or','and','with','in','on','at','to','from','while','only','without','small','slightly','visible'}
    words=[w.lower() for w in __import__('re').findall(r"[A-Za-z]+",str(target or ''))]
    out=[]
    for word in words:
        if word in stop or word in out:continue
        out.append(word)
        if len(out)>=max_words:break
    return ' '.join(out)


async def source_video_beat(engine,*,beat_id,client_id,queries,min_duration,max_duration,orientation,retrieval_intent=None,**ignored):
    intent=retrieval_intent or next((engine.query_intents.get(q) for q in queries if engine.query_intents.get(q)),queries[0])
    visual_target=_visual_target(intent)
    clean_queries=[q for q in queries if _query_matches_target(q,visual_target)]
    if not clean_queries:
        derived=_query_from_target(visual_target)
        clean_queries=[derived] if derived else list(queries[:1])
    output={'beat_id':beat_id,'queries':clean_queries,'candidates':[],'rejected_candidates':[],'errors':[],'search_attempts':[],'preview_cache_hits':0,'selected_cache_hit':False,'proposals':{'proposal_A':None,'proposal_B':None,'proposal_C':None},'quality_version':QUALITY_VERSION}
    def emit(message,**data):
        callback=getattr(engine,'event_callback',None)
        if callback:callback('online_search',None,message,slot_id=beat_id,**data)
    if list(clean_queries)!=list(queries):
        emit('Dropped stale/mismatched search queries',original_queries=list(queries),active_queries=list(clean_queries),visual_target=visual_target)
    priority={'pexels':0,'envato':1,'youtube_shorts':2,'tiktok':3,'instagram':4,'web_video':5,'youtube':6}
    query_budget={'envato':1,'web_video':1,'youtube':2,'pexels':2,'youtube_shorts':1,'tiktok':1,'instagram':1}
    expanded_all=expand_queries(clean_queries,'video')
    for source in sorted(engine.sources,key=lambda s:priority.get(_provider_name(s).casefold(),6)):
        provider_label=_provider_name(source);pool=[];seen=set()
        provider_key=provider_label.casefold()
        provider_queries=expanded_all[:query_budget.get(provider_key,2)]
        for query_index,query in enumerate(provider_queries):
            emit('Searching video source',provider=provider_label,query=query)
            rows,error=await engine._search_one(source,query,orientation=orientation,min_duration=min_duration,max_duration=max_duration)
            attempt={'provider':provider_label,'query':query,'hits':len(rows),'expanded':query not in clean_queries};output['search_attempts'].append(attempt)
            drain=getattr(source,'drain_vertical_attempts',None)
            if callable(drain):
                for extra in drain():
                    extra=dict(extra);extra.setdefault('query',query);extra.setdefault('hits',0);extra['expanded']=query not in clean_queries;output['search_attempts'].append(extra)
                    failure=extra.get('error') or extra.get('browser_error')
                    if failure:output['errors'].append({'provider':extra.get('provider'),'code':'provider_request_failed','error_type':failure})
            if error:
                output['errors'].append(error);attempt['error']=error.get('code') if isinstance(error,dict) else type(error).__name__
            for row in rows:
                key=(row.provider,row.provider_id)
                if key not in seen:pool.append(row);seen.add(key)
            if len(pool)>=6 and query_index>=1:break
        pool=_balanced_discovery_pool(pool,intent,limit=4)
        accepted=[];pending=[]
        for candidate in pool:
            asset_id=f'{candidate.provider}:{candidate.provider_id}';meta,contradictions,missing,generic=metadata_quality(visual_target,candidate.title+' '+candidate.description)
            discovery_relevant=_discovery_relevant(candidate,intent)
            if not discovery_relevant:
                output['rejected_candidates'].append({'id':asset_id,'source':candidate.provider,'source_url':candidate.source_page,'matched_query':candidate.query,'score':0,'quality_reasons':['metadata/title does not match concrete visual target']})
                continue
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
            if candidate.provider in {'envato','web_video'}:
                reason=('Envato search result; open the official item page to license/download'
                        if candidate.provider=='envato'
                        else 'Google Video/News result; open source page for the original report/clip')
                pending.append(_manual_discovery_base(candidate,asset_id,client_id,meta,reason=reason,preview_path=preview.path))
                continue
            duration=float(candidate.duration)
            folder=Path(preview.path).parent/'quality-clips'
            storyboard_starts=await _storyboard_starts(engine,candidate,intent,folder,asset_id,client_id,emit)
            if storyboard_starts==[] and candidate.provider=='youtube':
                output['rejected_candidates'].append({'id':asset_id,'source':candidate.provider,'source_url':candidate.source_page,'matched_query':candidate.query,'score':0,'quality_reasons':['storyboard scan did not find the requested visible scene']})
                continue
            starts=storyboard_starts if storyboard_starts is not None else temporal_starts(duration,candidate.provider)
            measured=[];shape_rejected=False
            for start in starts:
                emit('Materializing bounded clip',provider=candidate.provider,query=candidate.query,source_start_seconds=start,source_end_seconds=start+3.5)
                try:
                    clip=await asyncio.to_thread(materialize_clip,candidate.preview_rendition_url or candidate.selected_rendition_url,folder,asset_id,start_seconds=start) if candidate.provider=='pexels' else await asyncio.to_thread(_social_clip,candidate.source_page,folder,asset_id,start,candidate.provider)
                    if candidate.provider in VERTICAL_PROVIDERS and not _verified_portrait_clip(clip):
                        output['rejected_candidates'].append({'id':asset_id,'source':candidate.provider,'source_url':candidate.source_page,'matched_query':candidate.query,'score':0,'source_start_seconds':clip.get('source_start_seconds'),'source_end_seconds':clip.get('source_end_seconds'),'quality_reasons':['materialized social clip is not portrait']})
                        shape_rejected=True;break
                    frames=await asyncio.to_thread(_frame_samples,clip);frame_rows=[{**base,**clip,'id':asset_id+f':frame:{i}','kind':'video','path':clip['preview_path'],'keyframe_path':frame} for i,frame in enumerate(frames)]
                    emit('Ranking actual clip frames',provider=candidate.provider,query=candidate.query,frames=len(frames),visual_target=visual_target);scored=engine.ranker.rank(intent,frame_rows)
                    frame_values=sorted((float(r.get('score',0)) for r in scored),reverse=True)
                    best_values=frame_values[:2] if len(frame_values)>=2 else frame_values
                    semantic=sum(best_values)/max(1,len(best_values))
                    coherent=sum(r.get('quality_state') in {'accepted','needs_review'} for r in scored)
                    verified=len(scored)==len(frames) and len(scored)>=2 and coherent>=2 and semantic>=.46
                    phone_bonus=.035 if verified and candidate.provider in VERTICAL_PROVIDERS else 0
                    score=min(1.0,semantic+phone_bonus)
                    row={**base,**clip,'kind':'video','score':round(score,4),'semantic_score':round(semantic,4),'phone_native_bonus':phone_bonus,'frame_scores':[r['score'] for r in scored],'embedding_score':sum(r['embedding_score'] for r in scored)/len(scored) if scored and all(r.get('embedding_score') is not None for r in scored) else None,'quality_state':('needs_review' if any(r.get('quality_state')=='needs_review' for r in scored) else 'accepted') if verified else 'metadata_only','clip_verified':verified,'rank_reason':'Sampled clip frames ranked against editorial context'+(' · verified vertical-social bonus' if phone_bonus else ''),'preview_status':'ready','localization_method':'sampled source window; frame relevance checked' if verified else 'sampled source window; relevance unverified','quality_reasons':[reason for r in scored for reason in r.get('quality_reasons',[])],'acquisition_state':'CLIP_READY' if verified else 'PREVIEW_ONLY','manual_reason':None}
                    row['perceptual_hash']=perceptual_hash(Path(frames[0]));measured.append(row);emit('Clip quality measured',provider=candidate.provider,score=row['score'],clip_verified=verified)
                    if verified and row['score']>=.62:
                        emit('Strong clip found; skipping remaining windows',provider=candidate.provider,score=row['score'])
                        break
                except Exception as exc:
                    output['errors'].append({'provider':candidate.provider,'code':'clip_preview_failed','error_type':type(exc).__name__})
                    if not measured:break
            if shape_rejected:
                if candidate.provider in VERTICAL_PROVIDERS:pending.append({**base,**fallback_acquisition_state(has_preview=True,reason='automatic clip was not portrait; source link retained')})
                continue
            if measured:
                best=max(measured,key=lambda r:(r['clip_verified'],r['score']))
                if best['semantic_score']>=.46 and best['clip_verified']:accepted.append(best)
                else:
                    output['rejected_candidates'].append({k:best.get(k) for k in ('id','source','source_url','matched_query','score','semantic_score','frame_scores','source_start_seconds','source_end_seconds','quality_reasons')})
                    if discovery_relevant:pending.append({**base,**fallback_acquisition_state(has_preview=True,reason='automatic clip did not pass relevance verification')})
            elif discovery_relevant:
                pending.append({**base,**fallback_acquisition_state(has_preview=True,reason='automatic clip download unavailable')})
            if len(accepted)>=2:break
        accepted,_=diverse_candidates(sorted(accepted,key=lambda r:(r.get('source') in VERTICAL_PROVIDERS,r['score']),reverse=True),[],limit=3);output['candidates'].extend(accepted[:3]);output.setdefault('discovery_sources',[]).extend(pending[:3])
    output['eligible_candidate_count']=sum(c.get('clip_verified',False) for c in output['candidates']);output['raw_result_count']=sum(r['hits'] for r in output['search_attempts']);output['ranking_warning']=getattr(engine.ranker,'warning',None);return output
