"""Preserve physical source continuity and screenplay action between dialogue anchors."""
import re

def _rows(decision):return [decision,*decision.get('alternatives',[])]
def _source(row,sources):return next((s for s in sources if s['media_id']==row['media_id'] and s.get('take_id')==row.get('take_id')),None)
def _duration(row):return sum(r['end_frame']-r['start_frame'] for r in row.get('source_ranges',[row]))
def _movement(beat):return beat.get('kind')=='action' and not re.fullmatch(r'[\s.,…]*(pausa|silenzio|attesa|reazione)[\s.,…]*',beat.get('text',''),re.I)

def preserve_continuity(decisions,sources,beats,fps):
 positions={b['beat_id']:i for i,b in enumerate(beats) if b.get('beat_id')};actions=0;warnings=[]
 for decision in decisions:
  decision.pop('action_after',None);decision.pop('reaction_overlay',None)
 for i,left in enumerate(decisions):
  right=decisions[i+1] if i+1<len(decisions) else None
  start=positions.get(left['beat_id']);stop=positions.get(right['beat_id'],len(beats)) if right else len(beats)
  movement=[b for b in beats[start+1:stop] if _movement(b)] if start is not None else []
  if not movement:continue
  candidates=[]
  for a in _rows(left):
   if a.get('shot_size')!='wide':continue
   source=_source(a,sources)
   if not source:continue
   options=[b for b in _rows(right) if b['media_id']==a['media_id'] and b.get('take_id')==a.get('take_id')] if right else [None]
   for b in options:
    lo=a['end_frame'];hi=b['start_frame'] if b else source.get('end_frame',source['duration_frames'])
    if b is not None and b is not right:
     # Handles on an alternate take can begin inside the first word group.
     # End action before that group, so its opening is not played twice.
     words=sorted([w for seg in source.get('segments',[]) for w in seg.get('words',[]) if w['end_frame']>w['start_frame']],key=lambda w:w['start_frame'])
     index=next((k for k,w in enumerate(words) if w['start_frame']<=hi<w['end_frame']),None)
     if index is not None:
      onset=words[index]['start_frame']
      while index>0 and words[index]['start_frame']-words[index-1]['end_frame']<=round(.24*fps) and hi-words[index-1]['start_frame']<=round(.8*fps):index-=1;onset=words[index]['start_frame']
      hi=min(hi,onset)
    # Take boundaries and spoken production cues delimit available action coverage.
    for seg in source.get('segments',[]):
     for word in seg.get('words',[]):
      if lo<=word['start_frame']<hi and re.fullmatch(r'(stop|taglia|cut|azione|motore)[.!?,]*',word.get('text','').strip(),re.I):hi=word['start_frame']
    if lo<hi<=source.get('end_frame',source['duration_frames']) and hi-lo<=30*fps:candidates.append((a is left,source.get('take_index',0),a,b,lo,hi))
  if candidates:
   _,_,a,b,lo,hi=max(candidates,key=lambda x:(x[0],x[1]));left['action_after']=[{'kind':'action','beat_id':movement[0]['beat_id'],'action_beats':[m['beat_id'] for m in movement],'media_id':a['media_id'],'take_id':a['take_id'],'start_frame':lo,'end_frame':hi,'shot_size':'wide','basis':'script_between_anchors' if right else 'script_take_tail'}];actions+=1
  else:warnings.append('Azione senza raccordo sorgente affidabile: '+movement[0].get('text',''))
 for left,right in zip(decisions,decisions[1:]):
  if left.get('action_after') or left['media_id']!=right['media_id']:continue
  boundary=right['start_frame'];end=left['end_frame']
  if end==boundary:continue
  if left.get('manual') or right.get('manual') or left.get('take_id')!=right.get('take_id') or boundary<end or boundary-end>30*fps:raise ValueError('Continuità inquadratura non risolvibile: scegli una copertura alternativa invece del jump cut')
  left['end_frame']=boundary;left['source_ranges']=[{'start_frame':left['start_frame'],'end_frame':boundary}]
  left.setdefault('rationale_codes',[]).append('SOURCE_CONTINUITY_PRESERVED')
  left['pacing']['duration_frames']=_duration(left)
 return {'action_count':actions,'warnings':warnings}
