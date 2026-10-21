"""Local reconciliation of whole nearby retakes after semantic selection."""
import re
from difflib import SequenceMatcher
from .cut_pass import words_of
from .cut_residual import repetition_hints


def reconcile_selected_words(transcript,selected,*,trace=None):
    words=words_of(transcript);selected=set(selected)
    norm=lambda text:re.sub(r'[^\w]','',text.casefold())
    tokens=[norm(w['text']) for w in words]
    starts=set();offset=0;segments=[]
    for segment in transcript['segments']:
        count=len(segment.get('words',[]))
        if count:starts.add(offset);segments.append((offset,offset+count-1))
        offset+=count
    def end_of_take(a):
        for i in range(a,min(len(words),a+110)):
            if i>a+4:
                independent=(tokens[i:i+2] in [['noi','di'],['e','quindi']] or tokens[i:i+3]==['cioè','come','mi'])
                if independent:return i-1
                if i in starts and i>a+10 and tokens[i] in {'quando','come','noi','tipo'}:return i-1
            if re.search(r'[.!?]$',words[i]['text']):return i
        return min(len(words)-1,a+60)
    probe={'groups':[],'discards':[],'removed_word_indices':[]}
    hints=repetition_hints(transcript,probe,limit=None)
    candidates=[];seen=set()
    for hint in hints:
        if len(hint['text'].split())<5 or len(set(hint['text'].split()))<3:continue
        takes=[]
        for a,_ in hint['takes']:
            if a and tokens[a-1] in {'cioè','e'} and (a-1 in starts or tokens[a-1]=='cioè'):a-=1
            pair=[a,end_of_take(a)]
            if not takes or pair[0]>takes[-1][1]:takes.append(pair)
        if len(takes)<2:continue
        latest=takes[-1];a,b=latest
        if words[a]['start']-words[takes[-2][1]]['end']>100:continue
        if tokens[a] in {'frase','parole','inizio','fine'}:continue
        signature=tuple(map(tuple,takes))
        if signature in seen:continue
        seen.add(signature)
        old_tokens=tokens[takes[-2][0]:takes[-2][1]+1];last_tokens=tokens[a:b+1]
        blocks=SequenceMatcher(None,old_tokens,last_tokens,autojunk=False).get_matching_blocks()
        if sum(x.size for x in blocks)<min(len(old_tokens),len(last_tokens))*.55:continue
        def specific_details(x,y):
            start=x
            while start>0 and x-start<20 and not re.search(r'[.!?]$',words[start-1]['text']):start-=1
            return {tokens[k] for k in range(start,y+1) if any(ch.isdigit() for ch in tokens[k]) or (k>start and words[k]['text'][:1].isupper() and len(tokens[k])>2)}
        old_a,old_b=takes[-2]
        if (sum(i in selected for i in range(old_a,old_b+1))>.8*(old_b-old_a+1)
            and sum(i in selected for i in range(a,b+1))>.8*(b-a+1)
            and specific_details(old_a,old_b)-specific_details(a,b)):
            # Distinct named places/numbers in two retained statements are new
            # information, not permission to deduplicate a shared verbal pattern.
            continue
        any_kept=any(i in selected for x,y in takes for i in range(x,y+1))
        # A repeated question followed by a retained answer is a real cue,
        # even if the semantic pass mistook all versions for directing speech.
        answer_kept=(words[b]['text'].endswith('?') and any(i in selected for i in range(b+1,min(len(words),b+10))))
        if not any_kept and not answer_kept:continue
        candidates.append(takes)
    # Broad full-utterance corrections first; narrower predicate corrections
    # then remove a restart inside an otherwise retained sentence.
    candidates.sort(key=lambda takes:-(takes[-1][1]-takes[-1][0]))
    if trace is not None:trace['candidates']=candidates
    for takes in candidates:
        for a,b in takes[:-1]:selected.difference_update(range(a,b+1))
        a,b=takes[-1];selected.update(range(a,b+1))
    # A narrower restart can live inside a broader final sentence. It must
    # never be reintroduced by an overlapping candidate's retained prefix.
    old_words={i for takes in candidates for a,b in takes[:-1] for i in range(a,b+1)}
    selected.difference_update(old_words)
    # Ellipsis + an immediate rephrasing of the same predicate is a false start.
    stop={'a','e','di','in','il','la','le','mi','io','che','per','con','un','una','si','ci'}
    stem=lambda text:'far' if text.startswith('far') else text[:4]
    for (a,b),(c,d) in zip(segments,segments[1:]):
        if not words[b]['text'].endswith('...') or b-a>25:continue
        one=[stem(t) for t in tokens[a:b+1] if t not in stop and len(t)>2]
        two=[stem(t) for t in tokens[c:min(d+1,c+15)] if t not in stop and len(t)>2]
        if len(one)>=2 and len(two)>=2 and SequenceMatcher(None,one[:3],two[:5],autojunk=False).find_longest_match().size>=2:
            if any(i in selected for i in range(c,d+1)):selected.difference_update(range(a,b+1))
    # A standalone approval after the closing line is not part of the reel.
    if segments:
        a,b=segments[-1]
        if b-a<3 and all(t in {'perfetto','perfetta','bellissimo','bellissima','ottimo','ottima','esatto','bravo','brava','ok'} for t in tokens[a:b+1]):selected.difference_update(range(a,b+1))
    # Recover complete, coherent alternative ranges, trimming only to the
    # actually retained part of the final take. Never group a new concept.
    groups=[];occupied=set()
    for takes in sorted(candidates,key=lambda ts:-(ts[-1][1]-ts[-1][0])):
        a,b=takes[-1];runs=[]
        for i in range(a,b+1):
            if i not in selected:continue
            if runs and runs[-1][1]+1==i:runs[-1][1]=i
            else:runs.append([i,i])
        for a,b in runs:
            if b-a<4 or occupied.intersection(range(a,b+1)):continue
            alternatives=[];target=tokens[a:b+1]
            for x,y in takes[:-1]:
                if any(i in selected or i in occupied for i in range(x,y+1)):continue
                matches=[m for m in SequenceMatcher(None,tokens[x:y+1],target,autojunk=False).get_matching_blocks() if m.size>=3]
                if not matches or max(m.size for m in matches)<4:continue
                first=x+min(m.a for m in matches);last=x+max(m.a+m.size for m in matches)-1
                if last-first+1>max(len(target)*1.5,len(target)+6):continue
                alternatives.append([first,last])
            if alternatives:
                group={'takes':alternatives+[[a,b]],'selected_take':len(alternatives),'confidence':.98,'reason':'Ripartenze ravvicinate: ultima esecuzione, verifica locale sui tempi e sul testo.','boundaries_reviewed':True,'semantic_reviewed':True}
                groups.append(group)
                for x,y in group['takes']:occupied.update(range(x,y+1))
    return selected,groups
