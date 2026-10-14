"""Refine measured speech boundaries on short source windows without changing text."""
import copy
from difflib import SequenceMatcher
import re
import subprocess
from fractions import Fraction
from .cut_pass import words_of


def refine_cut_timing(transcript,plan,source,folder,*,transcriber=None,runner=subprocess.run,progress=None):
    if transcriber is None:
        from .cloud_analyze_cli import transcribe_groq
        transcriber=transcribe_groq
    result=copy.deepcopy(transcript)
    references=[w for s in result['segments'] for w in s['words']]
    original=words_of(transcript);warnings=[]
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
        measured=transcriber(clip,folder)
        if measured.get('timing_basis')!='cloud_asr_word_timestamps':
            warnings.append(f'Take {a}–{b}: allineamento non misurato, mantenuti i tempi precedenti')
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
        try:words_of({'segments':[{'words':proposed}]})
        except ValueError:
            warnings.append(f'Take {a}–{b}: tempi incompatibili, da verificare')
            continue
        for i,w in enumerate(proposed):references[i].update(w)
    for segment in result['segments']:
        if segment.get('words'):
            segment['start']=segment['words'][0]['start'];segment['end']=segment['words'][-1]['end']
    result['timing_refinement']='short_source_windows'
    return result,warnings
