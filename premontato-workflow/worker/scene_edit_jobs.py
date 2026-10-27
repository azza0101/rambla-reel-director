"""Scene-local speech routing before independent edit planning."""
import copy

def route_scenes(payload,encoder=None):
 from staged_dialogue import prepare_dialogue,core
 if encoder is None:
  from transcript_align import get_semantic_encoder
  encoder=get_semantic_encoder()
 scenes=payload['scenes'];beats=[b for s in scenes for b in s['beats'] if b.get('kind')=='dialogue'];prepared=prepare_dialogue({'beats':beats,'sources':payload['sources'],'fps':payload['fps']})
 targets=[b for b in beats if len(core(b['text']))>=2]
 if not targets:return {'jobs':[],'unassigned':[]}
 units=[(c,u) for c in prepared['clips'] for u in c['units']]
 scores=encoder.encode([u['text'] for c,u in units])@encoder.encode([b['text'] for b in targets]).T
 routes={};quality={};unassigned=[]
 for i,(clip,u) in enumerate(units):
  per={}
  for j,b in enumerate(targets):per[b['scene_id']]=max(per.get(b['scene_id'],-1),float(scores[i,j]))
  ranked=sorted(per.items(),key=lambda x:x[1],reverse=True)
  sid,score=ranked[0];margin=score-(ranked[1][1] if len(ranked)>1 else 0)
  quality[(clip['key'],u['id'])]=(score,margin,len(core(u['text'])))
  routes[(clip['key'],u['id'])]=sid if len(core(u['text']))>=2 and score>=.67 and margin>=.08 else None
 # Short replies inherit nearby anchored context within the same performance only.
 for clip in prepared['clips']:
  rows=clip['units'];anchors=[i for i,u in enumerate(rows) if routes[(clip['key'],u['id'])]]
  for i,u in enumerate(rows):
   if routes[(clip['key'],u['id'])]:continue
   near=sorted(anchors,key=lambda j:abs(rows[j]['start']-u['start']))
   if near and abs(rows[near[0]]['start']-u['start'])<=payload['fps']*8:
    routes[(clip['key'],u['id'])]=routes[(clip['key'],rows[near[0]]['id'])]
 # A generic reply cannot move an interior clip to an unrelated catalogued scene.
 # Cross-scene portions require multiple independent, strong semantic anchors.
 for clip in prepared['clips']:
  source=next(s for s in payload['sources'] if s.get('take_id',s['media_id'])==clip['key'])
  context=source.get('catalog_context') or {};primary=(context.get('scene') or {}).get('scene_id') if context.get('media_id')==source['media_id'] else None
  if not primary:continue
  anchors={};specific=set();positions={s['scene_id']:i for i,s in enumerate(scenes)}
  generic=set(core('vieni entra andiamo andare vai va ecco dai qui qua lì là subito aspetta vado facciamo'))
  for u in clip['units']:
   key=(clip['key'],u['id']);sid=routes[key];score,margin,n=quality[key]
   if sid and sid!=primary and score>=.80 and margin>=.16 and n>=4:anchors.setdefault(sid,set()).add(u['text'])
   content=set(core(u['text']))-generic
   adjacent=abs(positions.get(sid,-100)-positions.get(primary,100))<=1
   if sid and sid!=primary and ((adjacent and len(content)>=2 and score>=.67 and margin>=.08) or (len(content)>=4 and score>=.75 and margin>=.12)):specific.add(sid)
  for u in clip['units']:
   key=(clip['key'],u['id']);sid=routes[key]
   if sid and sid!=primary and len(anchors.get(sid,set()))<2 and sid not in specific:routes[key]=None
 jobs=[]
 for scene in scenes:
  selected=[]
  for source in payload['sources']:
   key=source.get('take_id',source['media_id']);clip=next(c for c in prepared['clips'] if c['key']==key)
   rows=[u for u in clip['units'] if routes[(key,u['id'])]==scene['scene_id']]
   if not rows:continue
   words=[w for seg in source['segments'] for w in seg.get('words',[])]
   segments=[{'text':u['text'],'start_frame':u['start'],'end_frame':u['end'],'words':[w for w in words if w['start_frame']>=u['start'] and w['end_frame']<=u['end']]} for u in rows]
   selected.append({**source,'segments':segments})
  jobs.append({'scene':scene,'sources':selected,'status':'ready' if selected else 'no_coverage'})
 for clip,u in units:
  if not routes[(clip['key'],u['id'])]:unassigned.append({'take_id':clip['key'],'start_frame':u['start'],'end_frame':u['end'],'text':u['text']})
 return {'jobs':jobs,'unassigned':unassigned}

def expand_missing(payload,encoder=None):
 from staged_dialogue import prepare_dialogue
 if encoder is None:
  from transcript_align import get_semantic_encoder
  encoder=get_semantic_encoder()
 scene=payload['scene'];missing=set(payload['missing']);originals=payload['sources'];existing=payload['selected_sources'];allowed={s['media_id'] for s in existing}
 sources=[s for s in originals if s['media_id'] in allowed or ((s.get('catalog_context') or {}).get('scene') or {}).get('scene_id')==scene['scene_id']]
 if not sources:return {'sources':existing,'expanded_media':0}
 prepared=prepare_dialogue({'beats':scene['beats'],'sources':sources,'fps':payload['fps']});flat=[(c,u) for c in prepared['clips'] for u in c['units']]
 queries=[]
 for i,b in enumerate(scene['beats']):
  if b['beat_id'] not in missing:continue
  neighbors=' '.join(x['text'] for x in scene['beats'][max(0,i-1):i+2] if x.get('kind')=='dialogue')
  queries.append(b['text']+' '+neighbors)
 if not queries or not flat:return {'sources':existing,'expanded_media':0}
 sims=encoder.encode(queries)@encoder.encode([u['text'] for c,u in flat]).T
 selected={}
 for scores in sims:
  seen=set()
  for k in sorted(range(len(flat)),key=lambda k:float(scores[k]),reverse=True):
   clip,u=flat[k]
   if float(scores[k])<.45:break
   if clip['key'] in seen:continue
   seen.add(clip['key']);rows=clip['units'];at=rows.index(u)
   for v in rows[max(0,at-2):at+3]:selected.setdefault(clip['key'],{})[(v['start'],v['end'])]=v
   if len(seen)>=2:break
 result=[];expanded=0
 for source in sources:
  key=source.get('take_id',source['media_id']);old=next((s for s in existing if s.get('take_id',s['media_id'])==key),None);rows=selected.get(key,{})
  if not rows:
   if old:result.append(old)
   continue
  segments={(s['start_frame'],s['end_frame']):s for s in (old or {}).get('segments',[])}
  words=[w for s in source['segments'] for w in s.get('words',[])]
  before=len(segments)
  for bounds,u in rows.items():segments.setdefault(bounds,{'text':u['text'],'start_frame':u['start'],'end_frame':u['end'],'words':[w for w in words if w['start_frame']>=u['start'] and w['end_frame']<=u['end']]})
  if len(segments)>before:expanded+=1
  result.append({**source,'segments':sorted(segments.values(),key=lambda s:s['start_frame'])})
 return {'sources':result,'expanded_media':expanded}
