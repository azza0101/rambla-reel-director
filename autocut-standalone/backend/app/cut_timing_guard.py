"""Detect implausible ASR word spans; never silently shorten unknown speech."""
from fractions import Fraction
from .cut_pass import words_of


def timing_anomalies(raw):
    return [{'index':w['index'],'text':w['text'],'start':w['start'],'end':w['end'],
             'duration':w['end']-w['start']} for w in words_of(raw)
            if w['end']-w['start']>max(2.5,len(w['text'])*.12+.6)]


def assert_timing_quality(raw,plan=None):
    anomalies=timing_anomalies(raw)
    if plan is not None:
        rate=float(Fraction(plan['fps']));removed=set(plan['removed_word_indices'])
        anomalies=[w for w in anomalies if w['index'] not in removed and any(
            min(w['end']*rate,s['source_out_frame'])>max(w['start']*rate,s['source_in_frame']) for s in plan['segments'])]
    if anomalies:
        details='; '.join('“'+w['text']+'” '+str(round(w['duration'],2))+' s a '+str(round(w['start'],2))+' s' for w in anomalies[:5])
        raise ValueError('Timestamp ASR anomalo: '+details+'. Il tratto audio deve essere ricontrollato prima di esportare; nessuna parola viene accorciata automaticamente.')


def remap_manual_indices(indices,mapping):
    if any(i not in mapping for i in indices):
        raise ValueError('Selezione manuale non riallineabile: conservata la revisione precedente per verifica')
    return sorted({mapping[i] for i in indices})


def splice_window(raw,start,end,replacement):
    """Replace measured ASR words in one bounded source window, preserving provenance."""
    from copy import deepcopy
    import re
    old=words_of(raw);before=[w for w in old if w['start']<start]
    # A short word straddling the audio boundary was not fully re-recognized.
    # Keep it rather than silently deleting its final syllable or the whole word.
    normalized=lambda text:re.sub(r'[^\w]','',text.casefold())
    after=[w for w in old if w['start']>=end or (w['start']<end<w['end'] and w['end']-w['start']<=2.5
        and not any(normalized(v.get('text') or v.get('word',''))==normalized(w['text'])
            and abs(v['start']-w['start'])<1 and v['end']<end-.005 for v in replacement))]
    after_ids={w['index'] for w in after}
    middle=[w for w in old if start<=w['start']<end and w['index'] not in after_ids]
    replacement=[{k:v for k,v in w.items() if k!='index'} for w in replacement]
    if after:
        boundary=after[0]
        replacement=[w for w in replacement if not (w['start']>=boundary['start']-.15 and re.sub(r'[^\w]','',w['text'].casefold())==re.sub(r'[^\w]','',boundary['text'].casefold()))]
    if not replacement:raise ValueError('Ricontrollo ASR senza parole: nessun risultato sostituito')
    if any(w['start']<start or w['end']>end+.05 for w in replacement):raise ValueError('Ricontrollo ASR fuori dalla finestra richiesta')
    combined=before+replacement+after
    words_of({'segments':[{'words':combined}]})
    mapping={w['index']:i for i,w in enumerate(before)}
    shift=len(before)+len(replacement)
    mapping.update({w['index']:shift+i for i,w in enumerate(after)})
    token=lambda w:re.sub(r'[^\w]','',w['text'].casefold())
    last=-1
    for word in middle:
        anomalous=word['end']-word['start']>max(2.5,len(word['text'])*.12+.6)
        candidates=[i for i,w in enumerate(replacement) if i>last and token(w)==token(word)
            and (word['start']-.5<=w['start']<=word['end']+.5 if anomalous else abs(w['start']-word['start'])<=1)]
        if candidates:
            found=min(candidates,key=lambda i:abs(replacement[i]['start']-word['start']))
            mapping[word['index']]=len(before)+found;last=found
    result=deepcopy(raw);segments=[];batch=[]
    for w in combined:
        if batch and w['start']-batch[-1]['end']>1:
            segments.append({'words':batch});batch=[]
        batch.append({k:v for k,v in w.items() if k!='index'})
        if w['text'].endswith(('.','!','?')):segments.append({'words':batch});batch=[]
    if batch:segments.append({'words':batch})
    for segment in segments:
        segment.update(start=segment['words'][0]['start'],end=segment['words'][-1]['end'],text=' '.join(w['text'] for w in segment['words']))
    result['segments']=segments;result['text']=' '.join(s['text'] for s in segments)
    result['timing_repair_version']=1
    return result,mapping


def repair_anomalies(raw,source,folder,transcribe,notify=lambda message:None):
    """Re-recognize short windows before editorial decisions, using the existing ASR."""
    import hashlib,json,subprocess
    from pathlib import Path
    from .atomic_io import write_json
    from .autocut_range import offset_transcript
    source=Path(source);folder=Path(folder);current=raw
    old=words_of(raw);windows=[]
    selection=raw.get('analysis_range_frames')
    lo=selection['in_frame']/float(Fraction(selection['fps'])) if selection else 0
    hi=selection['out_frame']/float(Fraction(selection['fps'])) if selection else max(w['end'] for w in old)
    for w in timing_anomalies(raw):
        a=max(lo,old[max(0,w['index']-2)]['start']);b=min(hi,old[min(len(old)-1,w['index']+2)]['end'])
        if windows and a<=windows[-1][1]:windows[-1][1]=max(windows[-1][1],b)
        else:windows.append([a,b])
    for n,(a,b) in enumerate(windows):
        notify('Ricontrollo timestamp anomalo · tratto '+str(n+1)+'/'+str(len(windows)))
        repaired=[];cursor=a
        while cursor<b:
            stop=min(b,cursor+5)
            key=hashlib.sha256(json.dumps({'v':1,'source':str(source.resolve()),'size':source.stat().st_size,
                'mtime':source.stat().st_mtime_ns,'start':cursor,'end':stop},sort_keys=True).encode()).hexdigest()
            cache=folder/'timing-repair-cache'/key;cache.mkdir(parents=True,exist_ok=True)
            file=cache/'transcript.json'
            if file.is_file():part=json.loads(file.read_text('utf-8'))
            else:
                audio=cache/'source.wav'
                subprocess.run(['ffmpeg','-v','error','-y','-ss',str(cursor),'-i',str(source),'-t',str(stop-cursor),'-vn','-ac','1','-ar','16000',str(audio)],check=True,capture_output=True,timeout=90)
                part=transcribe(audio,cache);write_json(file,part)
            shifted=offset_transcript(part,{'in_frame':round(cursor*1000000),'out_frame':round(stop*1000000),'fps':'1000000'})
            # Punctuation-only ASR placeholders describe no spoken word.
            repaired.extend(w for w in words_of(shifted) if any(c.isalnum() for c in w['text']));cursor=stop
        current,_=splice_window(current,a,b,repaired)
    assert_timing_quality(current)
    return current


def transcript_fingerprint(raw):
    import hashlib,json
    measured=[(w['text'],w['start'],w['end']) for w in words_of(raw)]
    return hashlib.sha256(json.dumps(measured,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
