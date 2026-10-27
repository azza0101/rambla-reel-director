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
 routes={};unassigned=[]
 for i,(clip,u) in enumerate(units):
  per={}
  for j,b in enumerate(targets):per[b['scene_id']]=max(per.get(b['scene_id'],-1),float(scores[i,j]))
  ranked=sorted(per.items(),key=lambda x:x[1],reverse=True)
  sid,score=ranked[0];margin=score-(ranked[1][1] if len(ranked)>1 else 0)
  routes[(clip['key'],u['id'])]=sid if len(core(u['text']))>=2 and score>=.67 and margin>=.08 else None
 # Short replies inherit nearby anchored context within the same performance only.
 for clip in prepared['clips']:
  rows=clip['units'];anchors=[i for i,u in enumerate(rows) if routes[(clip['key'],u['id'])]]
  for i,u in enumerate(rows):
   if routes[(clip['key'],u['id'])]:continue
   near=sorted(anchors,key=lambda j:abs(rows[j]['start']-u['start']))
   if near and abs(rows[near[0]]['start']-u['start'])<=payload['fps']*8:
    routes[(clip['key'],u['id'])]=routes[(clip['key'],rows[near[0]]['id'])]
 jobs=[]
 for scene in scenes:
  selected=[]
  for source in payload['sources']:
   key=source.get('take_id',source['media_id']);clip=next(c for c in prepared['clips'] if c['key']==key)
   rows=[u for u in clip['units'] if routes[(key,u['id'])]==scene['scene_id']]
   if len(rows)<2:continue
   if not rows:continue
   words=[w for seg in source['segments'] for w in seg.get('words',[])]
   segments=[{'text':u['text'],'start_frame':u['start'],'end_frame':u['end'],'words':[w for w in words if w['start_frame']>=u['start'] and w['end_frame']<=u['end']]} for u in rows]
   selected.append({**source,'segments':segments})
  jobs.append({'scene':scene,'sources':selected,'status':'ready' if selected else 'no_coverage'})
 for clip,u in units:
  if not routes[(clip['key'],u['id'])]:unassigned.append({'take_id':clip['key'],'start_frame':u['start'],'end_frame':u['end'],'text':u['text']})
 return {'jobs':jobs,'unassigned':unassigned}
