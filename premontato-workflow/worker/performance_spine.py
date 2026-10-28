"""Experimental audio-spine compiler. No screenplay-specific source ranges.
This module validates model decisions; it does not certify narrative completeness.
"""
def _units(units,duration=None):
 ids={};previous=-1
 for i,u in enumerate(units):
  if u['id'] in ids or not isinstance(u['start'],int) or not isinstance(u['end'],int) or not 0<=u['start']<u['end'] or u['start']<previous or duration is not None and u['end']>duration:raise ValueError('Unita sorgente non valida')
  ids[u['id']]=i;previous=u['start']
 return ids

def validate_ranges(units,blocks):
 ids=_units(units);result=[];end=-1
 for block in blocks:
  if block.get('first') not in ids or block.get('last') not in ids:raise ValueError('Identificatore inventato')
  a,b=ids[block['first']],ids[block['last']]
  if a>b or a<=end:raise ValueError('Intervalli fuori ordine o sovrapposti')
  if result and a==end+1:result[-1]['last']=block['last']
  else:result.append({'first':block['first'],'last':block['last']})
  end=b
 return result

def compile_spine(units,decision,duration,fps):
 ids=_units(units,duration)
 omit=decision.get('omit')
 if not isinstance(omit,list) or len(set(omit))!=len(omit) or any(x not in ids for x in omit):raise ValueError('Omissioni non valide')
 if not isinstance(fps,(int,float)) or fps<=0:raise ValueError('FPS non validi')
 omit=set(omit);groups=[];group=[]
 for u in units:
  if u['id'] in omit:
   if group:groups.append(group);group=[]
  else:group.append(u)
 if group:groups.append(group)
 blocks=[];clock=0
 for group in groups:
  a,b=ids[group[0]['id']],ids[group[-1]['id']]
  lo=max(0,units[a-1]['end'] if a else 0,group[0]['start']-round(fps*.16))
  hi=min(duration,units[b+1]['start'] if b+1<len(units) else duration,group[-1]['end']+round(fps*.32))
  if lo>=hi:raise ValueError('Parole sovrapposte nel confine del blocco')
  blocks.append({'start_frame':lo,'end_frame':hi,'record_frame':clock,'unit_ids':[u['id'] for u in group],'text':' '.join(u.get('text','') for u in group)})
  clock+=hi-lo
 return {'blocks':blocks,'kept_ids':[u['id'] for u in units if u['id'] not in omit],'duration_frames':clock,'missing':decision.get('missing',[]),'verification':'source_intervals_only'}
