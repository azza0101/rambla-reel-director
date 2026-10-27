"""Local visual scene retrieval; no cloud calls and no timeline timing inference."""
import math,os,re
from pathlib import Path
from cache import cache_key,get_cache,write_cache
VERSION='catalog-visual-v1'
# Retrieval policy can evolve without invalidating costly image embeddings.
POLICY_VERSION='catalog-visual-v2'
def sample_indices(length,fps,seconds=5,max_frames=24):
 if length<=0 or not math.isfinite(float(fps)) or fps<=0: raise ValueError('Invalid video bounds')
 step=max(1,round(fps*seconds));ids=list(range(0,length,step))
 if ids[-1]!=length-1:ids.append(length-1)
 if len(ids)>max_frames:ids=[ids[round(i*(len(ids)-1)/(max_frames-1))] for i in range(max_frames)]
 return sorted(set(ids))
def scene_queries(scenes):
 rows=[]
 for s in scenes:
  heading=s.get('heading','');actions=[b['text'] for b in s.get('beats',[]) if b.get('kind')=='action' and b.get('text','').strip()]
  sentences=[part.strip() for a in actions for part in re.split(r'(?<=[.!?;])\s+',a) if part.strip()]
  texts=[heading+' '+a for a in sentences] or [heading]
  for text in texts[:24]:rows.append({'scene_id':s['scene_id'],'text':text[:1500],'specificity':'setting' if not sentences or re.search(r'\b(sono|si trovano|are|is)\s+(all.interno|nel|nella|in|inside|at)\b',text,re.I) else 'action'})
 return rows

def rank_visual_scenes(queries,text_vectors,image_vectors,frames):
 def norm(v):
  mag=math.sqrt(sum(x*x for x in v));return [x/max(mag,1e-12) for x in v]
 tv=[norm(v) for v in text_vectors];iv=[norm(v) for v in image_vectors]
 if len(tv)!=len(queries) or len(iv)!=len(frames):raise ValueError('Visual evidence mismatch')
 scores={}
 for q,v in zip(queries,tv):
  values=[sum(a*b for a,b in zip(v,image)) for image in iv]
  if q['scene_id'] not in scores:scores[q['scene_id']]=values
  else:scores[q['scene_id']]=[max(a,b) for a,b in zip(scores[q['scene_id']],values)]
 ranked=sorted([{'scene_id':sid,'score':sum(values)/max(1,len(values))} for sid,values in scores.items()],key=lambda x:(-x['score'],x['scene_id']))
 if not ranked or not frames:return {'scene_id':None,'basis':'visual','candidates':ranked,'evidence':[],'reason':'NO_FRAMES'}
 best=ranked[0];specificity=next((q.get('specificity','action') for q in queries if q['scene_id']==best['scene_id']),'action');margin=best['score']-(ranked[1]['score'] if len(ranked)>1 else 0)
 support=sum(all(scores[best['scene_id']][i]>=values[i]+.02 for sid,values in scores.items() if sid!=best['scene_id']) for i in range(len(frames)))/len(frames)
 accepted=best['score']>=.30 and margin>=.035 and (support>=.6 or best['score']>=.38 and margin>=.05 and support>=.5)
 return {'scene_id':best['scene_id'] if accepted else None,'basis':'visual','specificity':specificity,'status':'review','score':round(best['score'],4),'margin':round(margin,4),'support':support,'candidates':ranked[:3],'reason':'VISUAL_MATCH' if accepted else 'VISUAL_AMBIGUOUS','evidence':[{'frame':f,'score':round(scores[best['scene_id']][i],4)} for i,f in enumerate(frames)]}

def extract_catalog_frames(payload):
 import cv2
 source=payload['source'];p=Path(source['path']);stat=p.stat();fingerprint=[str(p.resolve()),stat.st_size,stat.st_mtime_ns]
 root=Path(os.environ.get('PREMONTATO_CACHE_DIR','.premontato-cache'))/'catalog-frames'
 options={'fps':source['fps'],'length':source['duration_frames'],'seconds':5,'max_frames':5 if payload.get('reference') else 2 if payload.get('preview') else 24,'width':640}
 cached=get_cache(root,fingerprint,VERSION,options)
 if cached and all(Path(f['path']).is_file() for f in cached['frames']):return {**cached,'cache_hit':True}
 key=cache_key(fingerprint,VERSION,options);dest=root/key;dest.mkdir(parents=True,exist_ok=True)
 cap=cv2.VideoCapture(str(p));frames=[]
 try:
  if not cap.isOpened():raise ValueError('Video non leggibile')
  for index in sample_indices(source['duration_frames'],source['fps'],max_frames=options['max_frames']):
   cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,img=cap.read()
   if not ok:continue
   h,w=img.shape[:2]
   if w>640:img=cv2.resize(img,(640,max(1,round(h*640/w))),interpolation=cv2.INTER_AREA)
   target=dest/(str(index)+'.jpg')
   if not cv2.imwrite(str(target),img,[cv2.IMWRITE_JPEG_QUALITY,80]):raise ValueError('Impossibile salvare anteprima')
   frames.append({'frame':index,'path':str(target)})
 finally:cap.release()
 if not frames:raise ValueError('Nessun frame decodificabile')
 value={'frames':frames,'fingerprint':fingerprint};write_cache(root,cache_key(fingerprint,VERSION,options),value);return {**value,'cache_hit':False}

def preview_catalog_frames(payload):
 import base64
 result=extract_catalog_frames({**payload,'preview':True})
 return {'frames':[{'frame':f['frame'],'data_url':'data:image/jpeg;base64,'+base64.b64encode(Path(f['path']).read_bytes()).decode('ascii')} for f in result['frames'][:2]]}

# Contrastive roles describe composition rather than a particular production or file.
def role_queries():
 return [{'role':role,'text':text} for role,texts in {
  'broll':[
   'An insert shot: close-up of objects, products, food, tools or decorations. No visible conversation. B-roll detail footage.',
   'A close-up detail of hands using an object or of feet and clothing, without showing a conversation.',
   'An atmospheric establishing B-roll shot of a street or building, with no main character performing an action.'
  ],
  'dialogue':[
   'A scene showing a man and a woman talking to each other, with their faces visible.',
   'An actor in a medium shot or close-up, speaking or listening to another person. Dialogue scene.'
  ],
  'action':[
   'A person at an entrance, waiting, knocking, opening a door or entering a building. A narrative action scene.',
   'A person performing an action in a scene, moving through an entrance or interacting with another person.'
  ]}.items() for text in texts]

def rank_visual_role(queries,text_vectors,image_vectors):
 def norm(v):
  mag=math.sqrt(sum(x*x for x in v));return [x/max(mag,1e-12) for x in v]
 tv=[norm(v) for v in text_vectors];iv=[norm(v) for v in image_vectors];scores={}
 for q,v in zip(queries,tv):
  values=[sum(a*b for a,b in zip(v,image)) for image in iv]
  role=q['role'];scores[role]=[max(a,b) for a,b in zip(scores[role],values)] if role in scores else values
 if not iv:return {'category':None,'support':0}
 winners=[]
 for i in range(len(iv)):
  ranked=sorted(((r,v[i]) for r,v in scores.items()),key=lambda r:-r[1]);winners.append(ranked[0][0] if ranked[0][1]>=.25 and (len(ranked)==1 or ranked[0][1]-ranked[1][1]>=.025) else None)
 support=winners.count('broll')/len(iv)
 return {'category':'broll' if support>=.8 or support>=.5 and all(w in (None,'broll') for w in winners) else None,'support':support,'roles':winners,'scores':{r:sum(v)/len(iv) for r,v in scores.items()}}


def rank_visual_neighbors(image_vectors,references):
 def norm(v):
  mag=math.sqrt(sum(x*x for x in v));return [x/max(mag,1e-12) for x in v]
 images=[norm(v) for v in image_vectors];by_scene={}
 for ref in references:
  vectors=[norm(v) for v in ref.get('vectors',[])]
  if not vectors:continue
  values=[max(sum(a*b for a,b in zip(image,v)) for v in vectors) for image in images]
  sid=ref['scene_id'];by_scene[sid]=[max(a,b) for a,b in zip(by_scene[sid],values)] if sid in by_scene else values
 ranked=sorted([{'scene_id':sid,'score':sum(v)/len(v)} for sid,v in by_scene.items() if v],key=lambda r:(-r['score'],r['scene_id']))
 if not ranked:return {'scene_id':None,'anchors':[],'candidates':[]}
 best=ranked[0];margin=best['score']-(ranked[1]['score'] if len(ranked)>1 else 0)
 values=by_scene[best['scene_id']];support=sum(v>=.7 for v in values)/len(values)
 accepted=best['score']>=.7 and margin>=.035 and support>=.6
 return {'scene_id':best['scene_id'] if accepted else None,'score':best['score'],'margin':margin,'support':support,'candidates':ranked,'anchors':[{k:r[k] for k in ('media_id','scene_id','side','basis') if k in r} for r in references if r['scene_id']==best['scene_id']]}
