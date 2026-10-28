"""Conservative local role/face consistency from independently observed speech anchors."""
from pathlib import Path
import os,hashlib,numpy as np
from cache import get_or_compute

def match_role(vector,gallery):
 v=np.asarray(vector,dtype=float);v=v/max(1e-12,np.linalg.norm(v));scores={}
 for row in gallery:
  x=np.asarray(row['vector'],dtype=float);x=x/max(1e-12,np.linalg.norm(x));score=float(v@x)
  if score>=.38:scores.setdefault(row['role'],{})[row['media_id']]=max(score,scores.get(row['role'],{}).get(row['media_id'],-1))
 ranked=[]
 for role,values in scores.items():
  top=sorted(values.values(),reverse=True)[:3]
  if len(top)>=2:ranked.append((sum(top)/len(top),role))
 ranked.sort(reverse=True)
 if not ranked or ranked[0][0]<.38 or len(ranked)>1 and ranked[0][0]-ranked[1][0]<.10:return None
 return ranked[0][1]

def identity_boxes(evidence,active_only=True):
 valid=[f for f in evidence.get('faces',[]) if len(f.get('box',[]))==4 and f.get('tracking',0)>=.6]
 if not active_only:return [valid[0]['box']] if len(valid)==1 else []
 active=[f for f in valid if f.get('mean',0)>=.5 and f.get('positive',0)>=.5]
 active.sort(key=lambda f:f['mean']*f['positive'],reverse=True)
 if not active or len(active)>1 and active[0]['mean']*active[0]['positive']-active[1]['mean']*active[1]['positive']<.35:return []
 return [active[0]['box']]

_RECOGNIZER=None;_DETECTOR=None

def face_vector(source,start,end,evidence,active_only=True):
 from shot_analyzer import recognition_model_path,model_path
 import cv2,subprocess,shutil
 global _RECOGNIZER,_DETECTOR
 if _RECOGNIZER is None:_RECOGNIZER=cv2.FaceRecognizerSF.create(str(recognition_model_path()),'')
 if _DETECTOR is None:_DETECTOR=cv2.FaceDetectorYN.create(str(model_path()),'',(640,360),.7,.3,5000)
 path=Path(source['path']);stat=path.stat();fps=float(source['fps']);frame=min(source['duration_frames']-1,max(0,(start+end)//2))
 boxes=identity_boxes(evidence,active_only)
 if not boxes:return None
 def compute():
  try:
   from video_reader import get_reader
   image=get_reader(source).frames([frame])[0];h,w=image.shape[:2];scale=min(960/w,540/h);small=cv2.resize(image,(round(w*scale),round(h*scale)));image=np.zeros((540,960,3),dtype=np.uint8);y,x=(540-small.shape[0])//2,(960-small.shape[1])//2;image[y:y+small.shape[0],x:x+small.shape[1]]=small
  except Exception:
   ffmpeg=shutil.which('ffmpeg') or r'C:\Program Files\FFmpeg\ffmpeg.exe'
   raw=subprocess.check_output([ffmpeg,'-v','error','-ss',str(frame/fps),'-i',str(path),'-frames:v','1','-vf','scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2','-f','rawvideo','-pix_fmt','bgr24','pipe:1'],stderr=subprocess.DEVNULL,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));image=np.frombuffer(raw,np.uint8).reshape(540,960,3)
  _,faces=_DETECTOR.detect(cv2.resize(image,(640,360)))
  if faces is None:return None
  from active_speaker import _iou
  face=max(faces,key=lambda f:max(_iou(f[:4]*1.5,b) for b in boxes))
  if max(_iou(face[:4]*1.5,b) for b in boxes)<.35:return None
  face=face.copy();face[:14]*=1.5
  return _RECOGNIZER.feature(_RECOGNIZER.alignCrop(image,face)).flatten().tolist()
 root=Path(os.environ.get('PREMONTATO_CACHE_DIR','.premontato-cache'))/'speaker-faces'
 result,_=get_or_compute(root,[str(path.resolve()),stat.st_size,stat.st_mtime_ns],'sface-role-v2-active-winner',{'frame':frame,'boxes':boxes},compute)
 return result


def consensus_gallery(observations):
 """Resolve face-to-voice enrollment by independent-source quality consensus.
 Multiple utterances from the same clip supply at most one vote per voice.
 Conflicting visual identities stay unresolved rather than polluting both roles.
 """
 clusters=[]
 for row in observations:
  v=np.asarray(row['vector'],dtype=float)
  if v.ndim!=1 or not len(v) or not np.isfinite(v).all() or np.linalg.norm(v)<1e-8:raise ValueError('Volto non valido')
  v=v/np.linalg.norm(v);quality=float(row.get('quality',1.))
  if not np.isfinite(quality) or quality<=0:continue
  candidates=[(float(v@c['center']),c) for c in clusters if len(c['center'])==len(v)]
  similarity,cluster=max(candidates,key=lambda x:x[0]) if candidates else (-1,None)
  if similarity<.45:
   cluster={'center':v,'rows':[]};clusters.append(cluster)
  cluster['rows'].append({**row,'quality':quality})
  # Do not move the first prototype through a chain of weak pairwise matches.
 result=[]
 for cluster in clusters:
  by={}
  for r in cluster['rows']:
   key=(r['role'],r['media_id']);by[key]=max(by.get(key,0),r['quality'])
  scores={}
  for (role,mid),q in by.items():scores[role]=scores.get(role,0)+q
  ranked=sorted(scores,key=scores.get,reverse=True)
  if not ranked:continue
  winner=ranked[0];total=sum(scores.values());media={mid for role,mid in by if role==winner}
  if len(media)<2 or scores[winner]/total<.70:continue
  result.extend(r for r in cluster['rows'] if r['role']==winner)
 return result
