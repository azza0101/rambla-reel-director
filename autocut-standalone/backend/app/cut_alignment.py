"""Refine measured speech boundaries on short source windows without changing text."""
import copy
import hashlib
import json
from .atomic_io import write_json
from difflib import SequenceMatcher
import re
import subprocess
from fractions import Fraction
from .cut_pass import words_of


def refine_cut_timing(transcript,plan,source,folder,*,transcriber=None,runner=subprocess.run,progress=None):
    use_cache=transcriber is None
    if transcriber is None:
        from .cloud_analyze_cli import transcribe_groq
        transcriber=transcribe_groq
    result=copy.deepcopy(transcript)
    references=[w for s in result['segments'] for w in s['words']]
    original=words_of(transcript);warnings=[]
    from .cut_timing_guard import transcript_fingerprint
    timing_key=transcript_fingerprint(transcript)
    targets=[]
    for group in plan['groups']:
        selected=group['selected_take']
        if selected>=0:
            targets.append(group['takes'][selected])
            if selected>0:targets.append(group['takes'][selected-1])
    def token(text):return re.sub(r'[^\w]','',str(text).casefold())
    for n,(a,b) in enumerate(targets):
        start=max(0,original[a]['start']-1.0)
        end=min(plan['source_duration_frames']/float(Fraction(plan['fps'])),original[b]['end']+1.5)
        if progress:progress(n,len(targets))
        clip=folder/f'align-{n}.wav'
        runner(['ffmpeg','-v','error','-y','-ss',str(start),'-t',str(end-start),'-i',str(source),
            '-vn','-ac','1','-ar','16000',str(clip)],check=True,capture_output=True,timeout=90)
        key=hashlib.sha256(json.dumps({'source':plan['source_signature'],'timing':timing_key,'a':a,'b':b,'start':start,'end':end},sort_keys=True).encode()).hexdigest()
        cache=folder/'alignment-cache'/f'{key}.json'
        alias=folder/'alignment-cache-source.json'
        if use_cache and not cache.is_file() and alias.is_file():
            from .resolve_cut_source import file_identity
            previous=json.loads(alias.read_text(encoding='utf-8'))
            if previous.get('path')==str(source.resolve()) and previous.get('identity')==file_identity(source):
                old_key=hashlib.sha256(json.dumps({'source':previous['signature'],'timing':timing_key,'a':a,'b':b,'start':start,'end':end},sort_keys=True).encode()).hexdigest()
                inherited=folder/'alignment-cache'/f'{old_key}.json'
                if inherited.is_file():cache=inherited
        if use_cache and cache.is_file():measured=json.loads(cache.read_text(encoding='utf-8'))
        else:
            from .magic_usage import optional_asr_allowed
            if not optional_asr_allowed():
                message='MAGICO economico: conservati i timestamp già misurati; affinamento ASR aggiuntivo limitato per riservare budget a piano e coperture.'
                if message not in warnings:warnings.append(message)
                continue
            try:measured=transcriber(clip,folder)
            except Exception as exc:
                if 'Groq ASR failed (429)' not in str(exc) and 'Groq ASR failed (413)' not in str(exc):raise
                warnings.append('Quota Groq audio raggiunta: affinamento aggiuntivo sospeso; conservati i timestamp già misurati della trascrizione.')
                break
            if use_cache:cache.parent.mkdir(parents=True,exist_ok=True);write_json(cache,measured)
        if measured.get('timing_basis')!='cloud_asr_word_timestamps':
            warnings.append(f'Take {a}–{b}: allineamento non misurato, mantenuti i tempi precedenti')
            continue
        from .cut_timing_guard import timing_anomalies
        if timing_anomalies(measured):
            warnings.append(f'Take {a}–{b}: timestamp ASR anomalo, conservati i tempi precedenti')
            continue
        local=words_of(measured)
        indexes=[i for i,w in enumerate(original) if w['end']>start and w['start']<end]
        matches={}
        for block in SequenceMatcher(None,[token(original[i]['text']) for i in indexes],
                                     [token(w['text']) for w in local],autojunk=False).get_matching_blocks():
            for offset in range(block.size):matches[indexes[block.a+offset]]=local[block.b+offset]
        if any(i not in matches for i in range(a,b+1)):
            warnings.append(f'Take {a}–{b}: testo non interamente riallineato, da verificare')
            continue
        updates={i:{**references[i],'start':start+w['start'],'end':start+w['end']} for i,w in matches.items()}
        proposed=[updates.get(i,w) for i,w in enumerate(references)]
        # Neighbouring unrecognized filler can carry old timestamps inside a corrected
        # word. Move that boundary forward instead of clipping the retained word again.
        for i in range(1,len(proposed)):
            if proposed[i]['start']<proposed[i-1]['end']:
                proposed[i]={**proposed[i],'start':proposed[i-1]['end'],
                    'end':max(proposed[i]['end'],proposed[i-1]['end']+1/float(Fraction(plan['fps'])))}
        from .cut_timing_guard import assert_timing_quality
        try:
            words_of({'segments':[{'words':proposed}]})
            assert_timing_quality({'segments':[{'words':[proposed[i] for i in updates]}]})
        except ValueError:
            warnings.append(f'Take {a}–{b}: tempi incompatibili, da verificare')
            continue
        for i,w in enumerate(proposed):references[i].update(w)
    for segment in result['segments']:
        if segment.get('words'):
            segment['start']=segment['words'][0]['start'];segment['end']=segment['words'][-1]['end']
    result['timing_refinement']='short_source_windows'
    return result,warnings
