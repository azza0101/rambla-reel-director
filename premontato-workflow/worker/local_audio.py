"""Private, fingerprinted 16 kHz mono PCM shared by local audio analyses."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,tempfile,sys
import numpy as np

def ffmpeg_path():
    paths=[Path(sys.executable).parent/'ffmpeg.exe',shutil.which('ffmpeg'),r'C:\Program Files\FFmpeg\ffmpeg.exe']
    result=next((str(p) for p in paths if p and Path(p).is_file()),None)
    if not result:raise RuntimeError('FFmpeg non disponibile')
    return result

def load_pcm16(source):
    path=Path(source['path']);stat=path.stat();seconds=float(source['duration_frames'])/float(source.get('fps') or 25)
    if not 0<seconds<=3600:raise ValueError('Audio locale limitato a clip di massimo un’ora')
    fingerprint={'path':str(path.resolve()),'size':stat.st_size,'mtime':stat.st_mtime_ns,'seconds':seconds,'format':'pcm16-mono-16k-v1'}
    key=hashlib.sha256(json.dumps(fingerprint,sort_keys=True).encode()).hexdigest()
    folder=Path(os.environ.get('PREMONTATO_CACHE_DIR','.premontato-cache'))/'audio-pcm';folder.mkdir(parents=True,exist_ok=True);target=folder/(key+'.npy')
    try:
        # ASD reads short slices; map cached samples without allocating the whole clip.
        data=np.load(target,mmap_mode='r',allow_pickle=False)
        if isinstance(data,np.memmap):
            if data.dtype==np.dtype('<i2') and data.ndim==1 and 0<len(data)<=round((seconds+1)*16000):return data,{'cache_hit':True,'sample_rate':16000}
            # Windows cannot replace a cache file while a rejected mapping is open.
            data._mmap.close()
        elif hasattr(data,'close'):data.close()
    except (OSError,ValueError,EOFError):pass
    command=[ffmpeg_path(),'-nostdin','-hide_banner','-loglevel','error','-threads','2','-i',str(path),'-t',str(seconds),'-map','0:a:0','-vn','-ac','1','-ar','16000','-f','s16le','pipe:1']
    run=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=120,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if run.returncode or not run.stdout or len(run.stdout)%2:raise RuntimeError('Traccia audio non decodificabile')
    data=np.frombuffer(run.stdout,dtype='<i2')
    fd,temporary=tempfile.mkstemp(prefix='.audio-',suffix='.tmp',dir=folder)
    try:
        with os.fdopen(fd,'wb') as stream:np.save(stream,data,allow_pickle=False);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,target)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)
    return data,{'cache_hit':False,'sample_rate':16000}


def render_scene_debug_titles(payload):
    """Persistent alpha movies: Resolve ignores requested durations on still imports."""
    import cv2
    from cache import cache_key
    fps=payload.get('fps');scenes=payload.get('scenes');width=payload.get('width',1920);height=payload.get('height',1080)
    integer=lambda v:isinstance(v,int) and not isinstance(v,bool)
    if not isinstance(fps,(int,float)) or isinstance(fps,bool) or not 1<=fps<=120 or not isinstance(scenes,list) or not 0<len(scenes)<=100 or not integer(width) or not integer(height) or not 64<=width<=8192 or not 64<=height<=8192:raise ValueError('Titoli debug non validi')
    if any(not isinstance(s,dict) or not integer(s.get('number')) or not 1<=s['number']<=10000 or not integer(s.get('frames')) or not 0<s['frames']<=round(3600*fps) for s in scenes) or len({s['number'] for s in scenes})!=len(scenes):raise ValueError('Durata o numero scena non validi')
    # Keep referenced assets outside the disposable analysis cache.
    root=Path(os.environ.get('PREMONTATO_CACHE_DIR','.premontato-cache/shots')).resolve().parent.parent/'assets'/'scene-debug';root.mkdir(parents=True,exist_ok=True)
    scale=min(960/width,960/height,1);w=max(64,round(width*scale));h=max(64,round(height*scale))
    assets={};hits=0
    for scene in scenes:
        label=f"SCENA {scene['number']:02d}";key=cache_key('scene-debug-alpha-v1',label,scene['frames'],fps,w,h);target=root/(key+'.mov')
        if target.is_file() and target.stat().st_size>0:hits+=1
        else:
            image=np.zeros((h,w,4),dtype=np.uint8);font=cv2.FONT_HERSHEY_SIMPLEX;font_scale=max(.5,w/960*1.2);thick=max(1,round(w/480));margin=max(12,round(w*.025));size,_=cv2.getTextSize(label,font,font_scale,thick);origin=(margin,margin+size[1])
            cv2.putText(image,label,origin,font,font_scale,(0,0,0,255),thick+4,cv2.LINE_AA);cv2.putText(image,label,origin,font,font_scale,(255,255,255,255),thick,cv2.LINE_AA)
            fd,png=tempfile.mkstemp(prefix='.scene-',suffix='.png',dir=root);os.close(fd);fd,movie=tempfile.mkstemp(prefix='.scene-',suffix='.mov',dir=root);os.close(fd)
            try:
                if not cv2.imwrite(png,image):raise RuntimeError('Immagine etichetta non generata')
                command=[ffmpeg_path(),'-nostdin','-hide_banner','-loglevel','error','-y','-loop','1','-framerate',str(fps),'-i',png,'-frames:v',str(scene['frames']),'-an','-c:v','qtrle','-pix_fmt','argb','-threads','2',movie]
                run=subprocess.run(command,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=300,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if run.returncode or not Path(movie).stat().st_size:raise RuntimeError('Video etichetta non generato')
                os.replace(movie,target)
            finally:
                for p in [png,movie]:
                    if os.path.exists(p):os.unlink(p)
        assets[str(scene['number'])]=str(target)
    return {'assets':assets,'cache_hits':hits}
