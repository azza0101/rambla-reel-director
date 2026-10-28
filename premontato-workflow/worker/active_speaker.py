"""Local, name-free active-speaker evidence. Light-ASD TalkSet, CPU/ONNX.
A short tracked sample is advisory evidence, never an identity or certainty.
"""
from pathlib import Path
import hashlib, os, subprocess, sys, time
import numpy as np
from cache import get_or_compute, get_cache, cache_key, write_cache
from asd_features import mfcc
MODEL_SHA256='87fd38c0d3ebb9b31abff607662820c2622aef6ce54e1f808528f50e1ba77c38'
VERSION='light-asd-talkset-track5-pcm-v3'
SAMPLE_VERSION=VERSION+'-scores-v1'
_ANALYZER=None

def _smooth_coords(coords):
    padded=np.pad(coords,((6,6),(0,0)),mode='edge')
    return np.median(np.lib.stride_tricks.sliding_window_view(padded,13,axis=0),axis=-1)

def _crop_face(frame,cx,cy,side):
    """Same padded-coordinate slice, without copying the whole padded frame."""
    height,width=frame.shape[:2];pad=round(side*2)
    y0,y1,_=slice(max(0,int(cy-side+pad)),int(cy+side*1.8+pad)).indices(height+2*pad)
    x0,x1,_=slice(max(0,int(cx-side*1.4+pad)),int(cx+side*1.4+pad)).indices(width+2*pad)
    shape=(max(0,y1-y0),max(0,x1-x0),*frame.shape[2:])
    if not shape[0] or not shape[1]:return np.empty(shape,dtype=frame.dtype)
    y0-=pad;y1-=pad;x0-=pad;x1-=pad
    if 0<=y0<y1<=height and 0<=x0<x1<=width:return frame[y0:y1,x0:x1]
    crop=np.full(shape,110,dtype=frame.dtype)
    sy0,sy1=max(0,y0),min(height,y1);sx0,sx1=max(0,x0),min(width,x1)
    if sy1>sy0 and sx1>sx0:crop[sy0-y0:sy1-y0,sx0-x0:sx1-x0]=frame[sy0:sy1,sx0:sx1]
    return crop

def _empty_work():
    return {'decoded_samples':0,'detected_frames':0,'tracked_faces':0,'inference_calls':0}

def _valid_sample(sample):
    try:
        frames=sample['frames'];tracks=sample['tracks']
        if type(frames) is not int or frames<=0 or not isinstance(tracks,list):return False
        for track in tracks:
            scores=np.asarray(track['scores'],dtype=np.float32)
            if scores.shape!=(frames,) or not np.isfinite(scores).all():return False
            if len(track['box'])!=4 or not np.isfinite([track['height'],track['tracking'],*track['box']]).all():return False
        return True
    except (KeyError,TypeError,ValueError,OverflowError):return False

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
        clock=time.perf_counter()
        path=Path(source['path']);stat=path.stat();fps=float(source.get('fps') or 25);count=int(source['duration_frames'])
        if not 0<=start<end<=count or fps<=0:raise ValueError('Intervallo parlante non valido')
        if count/fps<.5:return {'status':'unknown','reason':'clip troppo breve','elapsed_seconds':round(time.perf_counter()-clock,6),'cache_hit':False,'sample_cache_hit':False,'stage_seconds':{},'work':_empty_work()}
        offset=max(0,min(int((start+end)/2-fps),max(0,count-round(2*fps))))
        duration=min(2,(count-offset)/fps)
        fingerprint={'path':str(path.resolve()),'size':stat.st_size,'mtime':stat.st_mtime_ns}
        options={'offset':offset,'duration':duration,'start':start,'end':end,'fps':fps,'model':MODEL_SHA256}
        result,hit=get_or_compute(self.cache,fingerprint,VERSION,options,lambda:self._run(source,offset,duration,start,end,fps))
        # `seconds` remains the historical computation time in a v3 cache entry.
        return {**result,'cache_hit':hit,'sample_cache_hit':not hit and bool(result.get('sample_cache_hit')),
                'elapsed_seconds':round(time.perf_counter()-clock,6),
                'stage_seconds':{} if hit else result.get('stage_seconds',{}),
                'work':_empty_work() if hit else result.get('work',_empty_work())}

    def _run(self,source,offset,duration,start,end,fps):
        clock=time.perf_counter();path=Path(source['path']);stat=path.stat()
        fingerprint={'path':str(path.resolve()),'size':stat.st_size,'mtime':stat.st_mtime_ns}
        options={'offset':offset,'duration':duration,'fps':fps,'count':int(source['duration_frames']),'model':MODEL_SHA256}
        root=self.cache/'samples'
        try:sample=get_cache(root,fingerprint,SAMPLE_VERSION,options)
        except (KeyError,TypeError):sample=None
        hit=_valid_sample(sample)
        if not hit:
            sample=self._compute_sample(source,offset,duration,start,end,fps)
            if not sample.get('empty_request'):
                write_cache(root,cache_key(fingerprint,SAMPLE_VERSION,options),sample)
        length=sample['frames'];lo=max(0,round((start-offset)/fps*25));hi=min(length,round((end-offset)/fps*25))
        telemetry={'sample_cache_hit':hit,'stage_seconds':{} if hit else sample['stage_seconds'],'work':_empty_work() if hit else sample['work']}
        if hi<=lo:return {'status':'unknown','reason':'nessun campione nella battuta',**telemetry}
        rows=[]
        for track in sample['tracks']:
            # Preserve float32 reductions and interval-specific rounding after JSON reload.
            values=np.asarray(track['scores'],dtype=np.float32)[lo:hi]
            rows.append({'mean':round(float(values.mean()),4),'positive':round(float((values>0).mean()),4),
                         'height':track['height'],'tracking':track['tracking'],'box':list(track['box'])})
        return {'status':classify_evidence(rows,hi-lo),'faces':rows,'sample_start_frame':offset,
                'sample_end_frame':min(int(source['duration_frames']),offset+round(length/25*fps)),
                'seconds':round(time.perf_counter()-clock,3),'method':VERSION,'sampled':True,**telemetry}

    def _compute_sample(self,source,offset,duration,start,end,fps):
        import cv2
        stages={};work=_empty_work();clock=time.perf_counter()
        command=[self.ffmpeg,'-nostdin','-hide_banner','-loglevel','error','-threads','2','-ss',str(offset/fps),'-i',source['path'],'-t',str(duration)]
        options={'stderr':subprocess.DEVNULL,'timeout':60,'creationflags':getattr(subprocess,'CREATE_NO_WINDOW',0)}
        from video_reader import read_asd_video
        video=read_asd_video(source,offset,duration)
        if video is None:
            raw=subprocess.check_output(command+['-an','-filter_threads','1','-vf','scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2,fps=25','-f','rawvideo','-pix_fmt','bgr24','pipe:1'],**options)
            if not raw or len(raw)%(960*540*3):raise RuntimeError('Campione video del parlante non leggibile')
            video=np.frombuffer(raw,np.uint8).reshape(-1,540,960,3)
        stages['decode']=time.perf_counter()-clock;work['decoded_samples']=1;clock=time.perf_counter()
        from local_audio import load_pcm16
        pcm,_=load_pcm16(source)
        stages['pcm_load']=time.perf_counter()-clock;clock=time.perf_counter()
        audio=pcm[round(offset/fps*16000):round((offset/fps+duration)*16000)];length=len(video)
        if not len(audio):raise RuntimeError('Audio del parlante non leggibile')
        features=mfcc(audio);features=np.pad(features,((0,max(0,length*4-len(features))),(0,0)),mode='edge')[:length*4][None].astype(np.float32)
        stages['audio_features']=time.perf_counter()-clock;clock=time.perf_counter()
        middle=length//2;indices=sorted(set([0,length-1,middle,*range(0,length,5)]));detections={}
        for index in indices:
            _,faces=self.detector.detect(cv2.resize(video[index],(640,360)))
            detections[index]=[] if faces is None else [face[:4]*1.5 for face in faces]
        stages['face_detection']=time.perf_counter()-clock;work['detected_frames']=len(indices)
        stages['tracking_crops']=0.;stages['inference']=0.
        lo=max(0,round((start-offset)/fps*25));hi=min(length,round((end-offset)/fps*25));tracks=[]
        # Keep the existing no-inference path for requests rounded to an empty slice.
        if hi<=lo:return {'frames':length,'empty_request':True,'stage_seconds':stages,'work':work}
        for anchor in detections[middle]:
            clock=time.perf_counter()
            positions={middle:anchor}
            for direction in [1,-1]:
                previous=anchor
                for index in sorted([i for i in indices if (i-middle)*direction>0],reverse=direction<0):
                    choices=detections[index];best=max(choices,key=lambda box:_iou(previous,box)) if choices else None
                    if best is not None and _iou(previous,best)>.2:positions[index]=best;previous=best
            keys=sorted(positions);boxes=np.stack([np.interp(np.arange(length),keys,[positions[k][j] for k in keys]) for j in range(4)],axis=1)
            coords=np.column_stack((boxes[:,0]+boxes[:,2]/2,boxes[:,1]+boxes[:,3]/2,np.maximum(boxes[:,2],boxes[:,3])/2))
            coords=_smooth_coords(coords)
            crops=[]
            for frame,(cx,cy,side) in zip(video,coords):
                crop=_crop_face(frame,cx,cy,side)
                if not crop.size:break
                crops.append(cv2.cvtColor(cv2.resize(crop,(224,224)),cv2.COLOR_BGR2GRAY)[56:168,56:168])
            if len(crops)!=length:
                stages['tracking_crops']+=time.perf_counter()-clock
                continue
            crops=np.asarray(crops,np.float32)[None]
            stages['tracking_crops']+=time.perf_counter()-clock;clock=time.perf_counter()
            full=self.session.run(None,{'audio':features,'video':crops})[0];parts=[]
            for k in range(0,length,25):parts.append(self.session.run(None,{'audio':features[:,k*4:min(length,k+25)*4],'video':crops[:,k:min(length,k+25)]})[0])
            stages['inference']+=time.perf_counter()-clock;work['inference_calls']+=1+len(parts);work['tracked_faces']+=1
            scores=(full+np.concatenate(parts))*.5
            tracks.append({'scores':scores.tolist(),'height':round(float(np.median(boxes[:,3])/540),4),'tracking':round(len(positions)/len(indices),4),'box':[round(float(x),2) for x in np.median(boxes,axis=0)]})
        return {'frames':length,'tracks':tracks,'stage_seconds':{key:round(value,6) for key,value in stages.items()},'work':work}

def analyze_candidate(source,start,end):
    global _ANALYZER
    from runtime_trace import record_asd
    clock=time.perf_counter()
    try:
        if _ANALYZER is None:_ANALYZER=ActiveSpeaker()
        result=_ANALYZER.analyze(source,start,end)
    except Exception:
        record_asd({},time.perf_counter()-clock,error=True);raise
    record_asd(result,time.perf_counter()-clock)
    return result


def verify_listener(source,start,end,answer_start,answer_end):
    answer=analyze_candidate(source,answer_start,answer_end)
    if answer.get('status')!='visible':return {'verified':False,'reason':'answer speaker uncertain'}
    responding=[face for face in answer.get('faces',[]) if classify_evidence([face],25)=='visible' and len(face.get('box',[]))==4]
    listening=analyze_candidate(source,start,end)
    inactive=[face for face in listening.get('faces',[]) if face.get('tracking',0)>=.6 and face.get('height',0)>=.1 and face.get('mean',0)<-.5 and face.get('positive',1)<.25 and len(face.get('box',[]))==4]
    stable=any(_iou(a['box'],b['box'])>=.35 for a in responding for b in inactive)
    return {'verified':stable,'method':'local_answer_speaker_and_inactive_face_continuity','answer_status':answer['status'],'listener_status':listening.get('status'),'cache_hit':bool(answer.get('cache_hit') and listening.get('cache_hit'))}
