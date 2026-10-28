"""Optional persistent NVDEC reader. Every retained frame is checked against source PTS.
Unsupported media, variable rates and unavailable GPU keep the original decoder.
"""
import os,sys,json,subprocess,shutil
from pathlib import Path
from fractions import Fraction
from collections import OrderedDict
_POOL=OrderedDict();_DLL_HANDLES=[]

def index_bias(timestamp,timebase,origin,fps):
 return -round((float(timestamp)*timebase-origin)*fps)

def check_timestamp(timestamp,timebase,origin,index,fps):
 error=abs(float(timestamp)*timebase-origin-index/fps)
 if error>.51/fps:raise ValueError('Video GPU: timestamp sorgente non allineato')
 return error

def batch_indices(start,count,step,batch=8,bias=0):
 return list(range(start,min(count-max(0,bias),start+batch*step),step))

class Reader:
 def __init__(self,source):
  import PyNvVideoCodec as nvc
  self.path=str(source['path']);self.fps=float(source.get('fps') or 25);self.count=int(source['duration_frames'])
  probe=shutil.which('ffprobe') or r'C:\Program Files\FFmpeg\ffprobe.exe'
  p=subprocess.run([probe,'-v','error','-select_streams','v:0','-show_entries','stream=time_base,start_time,avg_frame_rate,r_frame_rate','-of','json',self.path],capture_output=True,text=True,timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=True)
  info=json.loads(p.stdout)['streams'][0];self.tb=float(Fraction(info['time_base']));self.origin=float(info.get('start_time') or 0)
  rates=[float(Fraction(info[k])) for k in ('avg_frame_rate','r_frame_rate')]
  if any(abs(rate-self.fps)>.001 for rate in rates):raise ValueError('Video GPU: frame rate variabile/non compatibile')
  self.decoder=nvc.SimpleDecoder(self.path,use_device_memory=False,output_color_type=nvc.OutputColorType.RGB)
  self.decoder.seek_to_index(0);first=self.decoder.get_batch_frames(1)
  if not first:raise ValueError('Video GPU vuoto')
  self.bias=index_bias(first[0].timestamp,self.tb,self.origin,self.fps)
  self.timestamp_checks=0
 def convert(self,frame,index,resize=False):
  import numpy as np,cv2
  check_timestamp(frame.timestamp,self.tb,self.origin,index,self.fps);self.timestamp_checks+=1
  rgb=np.from_dlpack(frame)
  if resize:
   h,w=rgb.shape[:2];scale=min(960/w,540/h);nw,nh=round(w*scale),round(h*scale)
   small=cv2.resize(rgb,(nw,nh),interpolation=cv2.INTER_CUBIC)
   if (nw,nh)!=(960,540):
    rgb=np.zeros((540,960,3),dtype=np.uint8);x,y=(960-nw)//2,(540-nh)//2;rgb[y:y+nh,x:x+nw]=small
   else:rgb=small
  return rgb[:,:,::-1].copy()
 def frames(self,indices):
  if not indices:return []
  if any(i<0 or i>=self.count-max(0,self.bias) for i in indices):raise ValueError('Video GPU: indice fuori sorgente')
  frames=self.decoder.get_batch_frames_by_index([i+self.bias for i in indices])
  if len(frames)!=len(indices):raise ValueError('Video GPU: fotogrammi mancanti')
  return [self.convert(f,i) for i,f in zip(indices,frames)]
 def window(self,start,count):
  self.decoder.seek_to_index(start+self.bias);result=[]
  while len(result)<count:
   frames=self.decoder.get_batch_frames(min(5,count-len(result)))
   if not frames:raise ValueError('Video GPU: campione incompleto')
   for frame in frames:result.append(self.convert(frame,start+len(result),resize=True))
  return result

def get_reader(source):
 if os.environ.get('PREMONTATO_GPU_VIDEO','1')=='0':raise RuntimeError('Video GPU disattivato')
 path=Path(source['path']);stat=path.stat();key=(str(path.resolve()),stat.st_size,stat.st_mtime_ns,float(source['fps']),source['duration_frames'])
 if key not in _POOL:
  # Native package and its DLLs live only in the bundled runtime.
  native=Path(sys.executable).parent/'site-packages/PyNvVideoCodec'
  if sys.platform=='win32' and native.is_dir() and not _DLL_HANDLES:_DLL_HANDLES.append(os.add_dll_directory(str(native)))
  _POOL[key]=Reader(source)
  while len(_POOL)>3:_POOL.popitem(last=False)
 _POOL.move_to_end(key);return _POOL[key]

def read_asd_video(source,offset,duration):
 if abs(float(source.get('fps',25))-25)>.001:return None
 try:
  import numpy as np
  return np.stack(get_reader(source).window(offset,round(duration*25)))
 except Exception:return None

def sampled_gpu_frames(source,step):
 reader=get_reader(source)
 for start in range(0,reader.count,step*8):
  ids=batch_indices(start,reader.count,step,8,reader.bias)
  for i,frame in zip(ids,reader.frames(ids)):yield i,frame
  wanted=list(range(start,min(reader.count,start+8*step),step))
  if len(ids)!=len(wanted):raise ValueError('Video GPU: ultimo campione richiede il lettore originale')
