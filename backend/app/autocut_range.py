"""Bounded audio transcription with absolute original-source timestamps."""
from copy import deepcopy
from fractions import Fraction
import subprocess


def validate_range(selection,duration,fps):
    if selection is None:return None
    data=selection.model_dump() if hasattr(selection,'model_dump') else dict(selection)
    rate=Fraction(str(data['fps']))
    if rate<=0 or abs(float(rate)-float(fps))>.002:raise ValueError('FPS IN OUT diversi dal video sorgente')
    a,b=data['in_frame'],data['out_frame']
    if type(a) is not int or type(b) is not int or not 0<=a<b<=round(duration*float(rate))+1:
        raise ValueError('IN OUT fuori dal video originale')
    return {'in_frame':a,'out_frame':b,'fps':str(Fraction(str(fps)).limit_denominator(100000))}


def offset_transcript(raw,selection):
    result=deepcopy(raw);rate=float(Fraction(selection['fps']))
    start,end=selection['in_frame']/rate,selection['out_frame']/rate
    for segment in result['segments']:
        for word in segment.get('words',[]):
            word['start']=min(end,max(start,float(word['start'])+start))
            word['end']=min(end,max(start,float(word['end'])+start))
        segment['words']=[w for w in segment.get('words',[]) if w['end']>w['start']]
        if segment['words']:segment.update(start=segment['words'][0]['start'],end=segment['words'][-1]['end'])
    result['segments']=[s for s in result['segments'] if s['words']]
    result['analysis_range_frames']=dict(selection)
    result['text']=' '.join(w['text'] for s in result['segments'] for w in s['words'])
    return result


def transcribe_range(source,folder,selection,transcribe,runner=subprocess.run):
    rate=float(Fraction(selection['fps']));audio=folder/'selected-source.flac'
    runner(['ffmpeg','-v','error','-y','-ss',str(selection['in_frame']/rate),'-i',str(source),
        '-t',str((selection['out_frame']-selection['in_frame'])/rate),'-vn','-ac','1','-ar','16000','-c:a','flac',str(audio)],
        check=True,capture_output=True,timeout=180)
    return offset_transcript(transcribe(audio,folder),selection)
