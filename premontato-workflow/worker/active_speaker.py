"""Local, name-free active-speaker evidence. Light-ASD TalkSet, CPU/ONNX.
A short tracked sample is advisory evidence, never an identity or certainty.
"""
from pathlib import Path
import hashlib, os, subprocess, sys, time
import numpy as np
from cache import get_or_compute
from asd_features import mfcc
MODEL_SHA256='87fd38c0d3ebb9b31abff607662820c2622aef6ce54e1f808528f50e1ba77c38'
VERSION='light-asd-talkset-track5-pcm-v2'
_ANALYZER=None

def classify_evidence(faces, frames):
    valid=[f for f in faces if f.get('tracking',0)>=.6 and f.get('height',0)>=.06]
    if frames<12 or not valid:return 'unknown'
    if any((f['mean']>=.5 and f['positive']>=.6) or (f['mean']>=1.0 and f['positive']>=.5) for f in valid):return 'visible'
    if any(f['height']>=.13 for f in valid) and all(f['mean']<-.5 and f['positive']<.25 for f in valid):return 'absent'
    return 'unknown'

def _iou(a,b):
    w=max(0,min(a[0]+a[2],b[0]+b[2])-max(a[0],b[0]));h=max(0,min(a[1]+a[3],b[1]+b[3])-max(a[1],b[1]))
    area=w*h;return area/max(1,a[2]*a[3]+b[2]*b[3]-area)

class ActiveSpeaker:
    def __init__(self):
        import cv2,onnxruntime as ort,shutil
        from shot_analyzer import model_path
        paths=[Path(sys.executable).parent/'models/active-speaker/model.onnx',Path(__file__).resolve().parents[1]/'runtime/models/active-speaker/model.onnx']
        model=next((p for p in paths if p.is_file()),None)
        if model is None or hashlib.sha256(model.read_bytes()).hexdigest()!=MODEL_SHA256:raise RuntimeError('Modello parlante mancante o danneggiato')
        self.ffmpeg=next((str(p) for p in [shutil.which('ffmpeg'),r'C:\Program Files\FFmpeg\ffmpeg.exe'] if p and Path(p).is_file()),None)
        if not self.ffmpeg:raise RuntimeError('FFmpeg non disponibile per il controllo del parlante')
        opt=ort.SessionOptions();opt.intra_op_num_threads=2;opt.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(model),sess_options=opt,providers=['CPUExecutionProvider'])
        cv2.setNumThreads(1);self.detector=cv2.FaceDetectorYN.create(str(model_path()),'',(640,360),.7,.3,5000)
        self.cache=Path(os.environ.get('PREMONTATO_CACHE_DIR','.premontato-cache'))/'active-speaker'

    def analyze(self,source,start,end):
        path=Path(source['path']);stat=path.stat();fps=float(source.get('fps') or 25);count=int(source['duration_frames'])
        if not 0<=start<end<=count or fps<=0:raise ValueError('Intervallo parlante non valido')
        if count/fps<.5:return {'status':'unknown','reason':'clip troppo breve'}
        offset=max(0,min(int((start+end)/2-fps),max(0,count-round(2*fps))))
        duration=min(2,(count-offset)/fps)
        fingerprint={'path':str(path.resolve()),'size':stat.st_size,'mtime':stat.st_mtime_ns}
        options={'offset':offset,'duration':duration,'start':start,'end':end,'fps':fps,'model':MODEL_SHA256}
        result,hit=get_or_compute(self.cache,fingerprint,VERSION,options,lambda:self._run(source,offset,duration,start,end,fps))
        return {**result,'cache_hit':hit}

    def _run(self,source,offset,duration,start,end,fps):
        import cv2
        clock=time.perf_counter()
        command=[self.ffmpeg,'-nostdin','-hide_banner','-loglevel','error','-threads','2','-ss',str(offset/fps),'-i',source['path'],'-t',str(duration)]
        options={'stderr':subprocess.DEVNULL,'timeout':60,'creationflags':getattr(subprocess,'CREATE_NO_WINDOW',0)}
        raw=subprocess.check_output(command+['-an','-filter_threads','1','-vf','scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2,fps=25','-f','rawvideo','-pix_fmt','bgr24','pipe:1'],**options)
        if not raw or len(raw)%(960*540*3):raise RuntimeError('Campione video del parlante non leggibile')
        video=np.frombuffer(raw,np.uint8).reshape(-1,540,960,3)
        from local_audio import load_pcm16
        pcm,_=load_pcm16(source)
        audio=pcm[round(offset/fps*16000):round((offset/fps+duration)*16000)];length=len(video)
        if not len(audio):raise RuntimeError('Audio del parlante non leggibile')
        features=mfcc(audio);features=np.pad(features,((0,max(0,length*4-len(features))),(0,0)),mode='edge')[:length*4][None].astype(np.float32)
        middle=length//2;indices=sorted(set([0,length-1,middle,*range(0,length,5)]));detections={}
        for index in indices:
            _,faces=self.detector.detect(cv2.resize(video[index],(640,360)))
            detections[index]=[] if faces is None else [face[:4]*1.5 for face in faces]
        lo=max(0,round((start-offset)/fps*25));hi=min(length,round((end-offset)/fps*25));rows=[]
        if hi<=lo:return {'status':'unknown','reason':'nessun campione nella battuta'}
        for anchor in detections[middle]:
            positions={middle:anchor}
            for direction in [1,-1]:
                previous=anchor
                for index in sorted([i for i in indices if (i-middle)*direction>0],reverse=direction<0):
                    choices=detections[index];best=max(choices,key=lambda box:_iou(previous,box)) if choices else None
                    if best is not None and _iou(previous,best)>.2:positions[index]=best;previous=best
            keys=sorted(positions);boxes=np.stack([np.interp(np.arange(length),keys,[positions[k][j] for k in keys]) for j in range(4)],axis=1)
            coords=np.column_stack((boxes[:,0]+boxes[:,2]/2,boxes[:,1]+boxes[:,3]/2,np.maximum(boxes[:,2],boxes[:,3])/2))
            coords=np.stack([np.median(np.pad(coords[:,j],(6,6),mode='edge')[k:k+13]) for k in range(length) for j in range(3)]).reshape(length,3)
            crops=[]
            for frame,(cx,cy,side) in zip(video,coords):
                pad=round(side*2);padded=cv2.copyMakeBorder(frame,pad,pad,pad,pad,cv2.BORDER_CONSTANT,value=(110,110,110))
                crop=padded[max(0,int(cy-side+pad)):int(cy+side*1.8+pad),max(0,int(cx-side*1.4+pad)):int(cx+side*1.4+pad)]
                if not crop.size:break
                crops.append(cv2.cvtColor(cv2.resize(crop,(224,224)),cv2.COLOR_BGR2GRAY)[56:168,56:168])
            if len(crops)!=length:continue
            crops=np.asarray(crops,np.float32)[None]
            full=self.session.run(None,{'audio':features,'video':crops})[0];parts=[]
            for k in range(0,length,25):parts.append(self.session.run(None,{'audio':features[:,k*4:min(length,k+25)*4],'video':crops[:,k:min(length,k+25)]})[0])
            values=((full+np.concatenate(parts))*.5)[lo:hi]
            rows.append({'mean':round(float(values.mean()),4),'positive':round(float((values>0).mean()),4),'height':round(float(np.median(boxes[:,3])/540),4),'tracking':round(len(positions)/len(indices),4)})
        return {'status':classify_evidence(rows,hi-lo),'faces':rows,'sample_start_frame':offset,'sample_end_frame':min(int(source['duration_frames']),offset+round(length/25*fps)),'seconds':round(time.perf_counter()-clock,3),'method':VERSION,'sampled':True}

def analyze_candidate(source,start,end):
    global _ANALYZER
    if _ANALYZER is None:_ANALYZER=ActiveSpeaker()
    return _ANALYZER.analyze(source,start,end)
