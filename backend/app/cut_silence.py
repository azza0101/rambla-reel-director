"""Measured silence in source audio, independent of imperfect ASR word boundaries."""
import re
import subprocess


def detect_silences(source,duration):
    result=subprocess.run(['ffmpeg','-hide_banner','-nostats','-i',str(source),'-vn',
        '-af','silencedetect=noise=-40dB:d=0.15','-f','null','-'],capture_output=True,text=True,timeout=180,check=True)
    ranges=[];start=None
    for kind,value in re.findall(r'silence_(start|end): ([0-9.]+)',result.stderr):
        value=float(value)
        if kind=='start':start=max(0,value)
        elif start is not None:
            ranges.append([start,min(duration,value)]);start=None
    if start is not None and start<duration:ranges.append([start,duration])
    return ranges


def trim_silence_ranges(ranges,silences,rate,mode,words=(),*,end_margin_ms=0):
    minimum,margin={'soft':(.45,.10),'medium':(.30,.08),'strong':(.18,.06)}[mode]
    cuts=[]
    for start,end in silences:
        if end-start>=minimum:
            # Low-energy final syllables can be labelled silence. Protect the full
            # measured timestamp of brief words touched by a silence boundary.
            cut_start,cut_end=start+margin,end-margin
            for word in words:
                if end_margin_ms and word['start'] < cut_start < word['end'] + end_margin_ms/1000:
                    next_start = min((w['start'] for w in words if w['start'] >= word['end']), default=float('inf'))
                    cut_start = max(cut_start, min(word['end'] + end_margin_ms/1000, next_start))
                if word['end']-word['start']<=.35:
                    if word['start']<cut_start<word['end']:cut_start=word['end']+.04
                    if word['start']<cut_end<word['end']:cut_end=word['start']-.04
            a,b=__import__('math').ceil(cut_start*rate),__import__('math').floor(cut_end*rate)
            if b>a:cuts.append((a,b))
    result=[]
    for start,end,*rest in ranges:
        pieces=[(start,end)]
        for a,b in cuts:
            next_pieces=[]
            for x,y in pieces:
                if b<=x or a>=y:next_pieces.append((x,y));continue
                if x<a:next_pieces.append((x,min(y,a)))
                if b<y:next_pieces.append((max(x,b),y))
            pieces=next_pieces
        result.extend([a,b,*rest] for a,b in pieces if b>a)
    return result
