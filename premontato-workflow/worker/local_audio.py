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
