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
  if len(top)>=2:ranked.append((sum(top)/3,role))
 ranked.sort(reverse=True)
 if not ranked or ranked[0][0]<.38 or len(ranked)>1 and ranked[0][0]-ranked[1][0]<.10:return None
 return ranked[0][1]

_RECOGNIZER=None;_DETECTOR=None

def face_vector(source,start,end,evidence):
 from shot_analyzer import recognition_model_path,model_path
 import cv2,subprocess,shutil
 global _RECOGNIZER,_DETECTOR
 if _RECOGNIZER is None:_RECOGNIZER=cv2.FaceRecognizerSF.create(str(recognition_model_path()),'')
 if _DETECTOR is None:_DETECTOR=cv2.FaceDetectorYN.create(str(model_path()),'',(640,360),.7,.3,5000)
 path=Path(source['path']);stat=path.stat();fps=float(source['fps']);frame=min(source['duration_frames']-1,max(0,(start+end)//2))
 boxes=[f['box'] for f in evidence.get('faces',[]) if f.get('mean',0)>=.5 and f.get('positive',0)>=.5 and len(f.get('box',[]))==4]
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
 result,_=get_or_compute(root,[str(path.resolve()),stat.st_size,stat.st_mtime_ns],'sface-role-v1',{'frame':frame,'boxes':boxes},compute)
 return result
