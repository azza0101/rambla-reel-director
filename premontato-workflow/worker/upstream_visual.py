"""Source visual observations before lexical/ASD candidate pruning. No voice guessing."""
import subprocess,shutil,time
from pathlib import Path
from cache import get_or_compute
from visual_inventory import LocalInventory,sample_frames,summarize

def dominant_face(faces):
 rows=sorted(faces,key=lambda f:float(f[2]*f[3]),reverse=True)
 if not rows or rows[0][3]<54:return None
 if len(rows)>1 and rows[0][2]*rows[0][3]<4*rows[1][2]*rows[1][3]:return None
 return rows[0]

def consensus_role(roles):
 known=[r for r in roles if r is not None]
 return known[0] if len(known)>=2 and len(set(known))==1 else None

def may_rescue_question(reference,candidate,semantic,context,voice,candidate_voice,visible_role):
 from sequence_director import contextual_question_match
 return voice is not None and voice==candidate_voice==visible_role and contextual_question_match(reference,candidate,semantic,context)

_DETECTOR=None;_RECOGNIZER=None

def direct_face(source,frame,root):
 from shot_analyzer import model_path,recognition_model_path
 path=Path(source['path']);st=path.stat();models=[]
 for p in (model_path(),recognition_model_path()):
  p=Path(p);s=p.stat();models.append([str(p.resolve()),s.st_size,s.st_mtime_ns])
 def compute():
  import cv2,numpy as np
  global _DETECTOR,_RECOGNIZER
  if _DETECTOR is None:_DETECTOR=cv2.FaceDetectorYN.create(str(model_path()),'',(640,360),.7,.3,5000)
  if _RECOGNIZER is None:_RECOGNIZER=cv2.FaceRecognizerSF.create(str(recognition_model_path()),'')
  try:
   from video_reader import get_reader
   raw=get_reader(source).frames([frame])[0];h,w=raw.shape[:2];scale=min(960/w,540/h);small=cv2.resize(raw,(round(w*scale),round(h*scale)));img=np.zeros((540,960,3),np.uint8);y,x=(540-small.shape[0])//2,(960-small.shape[1])//2;img[y:y+small.shape[0],x:x+small.shape[1]]=small
  except Exception:
   ffmpeg=shutil.which('ffmpeg') or r'C:\Program Files\FFmpeg\ffmpeg.exe'
   raw=subprocess.check_output([ffmpeg,'-nostdin','-v','error','-ss',str(frame/source['fps']),'-i',str(path),'-frames:v','1','-vf','scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2','-f','rawvideo','-pix_fmt','bgr24','pipe:1'],stderr=subprocess.DEVNULL,timeout=45,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));img=np.frombuffer(raw,np.uint8).reshape(540,960,3)
  _,faces=_DETECTOR.detect(cv2.resize(img,(640,360)))
  face=dominant_face(list(faces) if faces is not None else [])
  if face is None:return None
  face=face.copy();face[:14]*=1.5
  return _RECOGNIZER.feature(_RECOGNIZER.alignCrop(img,face)).flatten().tolist()
 value,hit=get_or_compute(Path(root)/'upstream-face-frames',[str(path.resolve()),st.st_size,st.st_mtime_ns],'dominant-independent-frame-v1',{'frame':frame,'fps':source['fps'],'models':models},compute)
 return value,hit

class UpstreamVisual:
 def __init__(self,config,root,gallery,face_budget=480,object_budget=24):
  if type(face_budget) is not int or not 0<=face_budget<=600 or type(object_budget) is not int or not 0<=object_budget<=48:raise ValueError('Budget indice visivo non valido')
  self.root=root;self.gallery=gallery;self.face_budget=face_budget;self.object_budget=object_budget;self.used_faces=0;self.used_objects=0;self.hits=0;self.object_hits=0;self.seconds=0.;self.errors=[];self.memo={};self.vectors={};self.client=LocalInventory(config,root) if config else None
 def __enter__(self):return self
 def __exit__(self,*args):
  if self.client:self.client.close()
 def observe(self,source,start,end,objects=False):
  from speaker_identity import match_role
  # Identity-only observations must not suppress a later object request.
  # Frame embeddings remain shared, so enrichment does not decode them twice.
  key=(source['media_id'],start,end,bool(objects))
  if key in self.memo:return self.memo[key]
  started=time.perf_counter()
  roles=[];samples=[];frames=sample_frames(start,end)
  for frame in frames:
   fk=(source['media_id'],frame)
   if fk not in self.vectors and self.used_faces<self.face_budget:
    self.used_faces+=1
    try:v,hit=direct_face(source,frame,self.root);self.vectors[fk]=v;self.hits+=int(hit)
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:self.errors.append(type(error).__name__);self.vectors[fk]=None
   vector=self.vectors.get(fk);roles.append(match_role(vector,self.gallery) if vector else None)
   if objects and self.client and self.used_objects<self.object_budget:
    self.used_objects+=1
    try:
     row=self.client.observe(source,frame);samples.append(row);self.object_hits+=int(row.get('cache_hit',False))
    except (OSError,ValueError,RuntimeError,KeyError,subprocess.SubprocessError) as error:self.errors.append(type(error).__name__)
  # A short glance down can defeat the centre frame. Inspect the two internal
  # quarter points only when identity is still unknown, never to outvote a
  # contradiction between known identities. No extra model inference required.
  if consensus_role(roles) is None and len({r for r in roles if r is not None})<=1:
   extras=[f for f in sample_frames(start,end,5) if f not in frames]
   for frame in extras:
    fk=(source['media_id'],frame)
    if fk not in self.vectors and self.used_faces<self.face_budget:
     self.used_faces+=1
     try:v,hit=direct_face(source,frame,self.root);self.vectors[fk]=v;self.hits+=int(hit)
     except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:self.errors.append(type(error).__name__);self.vectors[fk]=None
    vector=self.vectors.get(fk);roles.append(match_role(vector,self.gallery) if vector else None)
  result={'visible_role':consensus_role(roles),'identity_frame_roles':roles,'objects_requested':bool(objects),'inventory':{'complete':len(samples)==len(frames),'samples':samples,'summary':summarize(samples)},'basis':'independent_frame_identity_before_candidate_filter','speaker_inferred_from_images':False}
  self.memo[key]=result;self.seconds+=time.perf_counter()-started;return result
 def diagnostics(self):return {'face_frames':self.used_faces,'face_budget':self.face_budget,'face_budget_exhausted':self.used_faces>=self.face_budget,'face_cache_hits':self.hits,'object_frames':self.used_objects,'object_cache_hits':self.object_hits,'seconds':self.seconds,'intervals':len(self.memo),'known_intervals':sum(v['visible_role'] is not None for v in self.memo.values()),'errors':self.errors,'before_content_pruning':True}
