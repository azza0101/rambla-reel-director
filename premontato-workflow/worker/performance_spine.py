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


def observed_story(units,start,end,exclusions=None):
 """Lossless observed-performance inventory, before cleanup or camera choices.
 Screenplay labels are deliberately ignored. Identical replies to different
 questions remain separate source events. This is not a certified clean edit:
 direction and false starts require a subsequent context-aware decision.
 """
 _units(units)
 if type(start) is not int or type(end) is not int or not 0<=start<end:raise ValueError('Confine scena non valido')
 if exclusions:raise ValueError('Questa fase non elimina parlato: pulizia separata con prove contestuali')
 events=[]
 for u in units:
  if u['end']<=start or u['start']>=end:continue
  if u['start']<start or u['end']>end:raise ValueError('Confine scena dentro una battuta')
  events.append({'source_unit_id':u['id'],'start_frame':u['start'],'end_frame':u['end'],'text':u.get('text',''),'speaker':u.get('speaker_name'),'speaker_verified':bool(u.get('speaker_reliable',False))})
 return {'basis':'observed_transcript','events':events,'script_filters_applied':False,'duplicate_text_removed':False,'cleanup_pending':True,'visual_actions_verified':False}


def jump_cover(join,total,reaction,fps):
 """Accept only verified listening video spanning a source discontinuity."""
 import math
 if not reaction or not reaction.get('verified_listener') or not reaction.get('different_person'):return None
 start=reaction.get('start_frame',-1);end=reaction.get('end_frame',-1);at=reaction.get('record_frame',-1)
 if any(type(x) is not int for x in (join,total,start,end,at)) or not isinstance(fps,(int,float)) or fps<=0:return None
 length=end-start
 if start<0 or length<math.ceil(1.5*fps) or not 0<=at<join<at+length<=total:return None
 return {**reaction,'kind':'reaction','basis':'verified_listener_jump_cover','audio':'base_unchanged'}


def group_voice_turns(units,voices,fps):
 """Group adjacent observed units without deduplication or guessing unknowns."""
 _units(units)
 if not isinstance(fps,(int,float)) or fps<=0:raise ValueError('FPS non validi')
 if set(voices)!={u['id'] for u in units}:raise ValueError('Etichette voce incomplete')
 turns=[]
 for u in units:
  voice=voices[u['id']]
  if voice is not None and (not isinstance(voice,str) or not voice):raise ValueError('Voce non valida')
  if turns and voice is not None and turns[-1]['voice']==voice and u['start']-turns[-1]['end_frame']<=2*fps:
   turns[-1]['end_frame']=u['end'];turns[-1]['text']+=' '+u.get('text','');turns[-1]['unit_ids'].append(u['id'])
  else:turns.append({'voice':voice,'start_frame':u['start'],'end_frame':u['end'],'text':u.get('text',''),'unit_ids':[u['id']]})
 return turns
