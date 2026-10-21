"""Local relative volume is editorial context, never an automatic exclusion."""
import array,copy,math,statistics,subprocess,sys
from pathlib import Path
from .cut_pass import words_of


def annotate_relative_volume(raw,source,runner=subprocess.run):
    result=copy.deepcopy(raw)
    if not Path(source).is_file():return result
    words=words_of(raw);start=words[0]['start'];end=max(w['end'] for w in words)
    try:
        audio=runner(['ffmpeg','-v','error','-ss',str(start),'-i',str(source),'-t',str(end-start),
            '-vn','-ac','1','-ar','16000','-f','s16le','pipe:1'],capture_output=True,check=True,timeout=90).stdout
        samples=array.array('h');samples.frombytes(audio)
        if sys.byteorder!='little':samples.byteswap()
        levels=[]
        for w in words:
            a=max(0,round((w['start']-start)*16000));b=min(len(samples),round((w['end']-start)*16000))
            part=samples[a:b:4]
            levels.append(10*math.log10(max(1,sum(x*x for x in part)/max(1,len(part)))))
        reference=sorted(levels)[min(len(levels)-1,int(len(levels)*.75))]
        flat=[w for s in result['segments'] for w in s['words']]
        for w,level in zip(flat,levels):w['relative_speech_db']=round(level-reference,1)
        result['volume_context_version']=1
    except (OSError,subprocess.SubprocessError,ValueError):
        result['volume_context_warning']='Volume relativo non disponibile; nessuna parola esclusa per volume.'
    return result
