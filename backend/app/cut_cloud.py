"""Small, resumable CUT requests paced within the account's 8k TPM limit."""
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib,json,math,os,re,threading,time
from pathlib import Path
from .atomic_io import write_json

_CONTEXT=ContextVar('cut_cloud_context',default=None)
_LOCK=threading.RLock()

class TokenWindow:
    def __init__(self,limit=7500):self.limit=limit;self.events=deque()
    def wait_seconds(self,tokens,now):
        while self.events and self.events[0][0]+60<=now:self.events.popleft()
        if tokens>self.limit:raise ValueError('Blocco CUT troppo grande: riduci il numero di parole')
        return max(0,self.events[0][0]+61-now) if self.events and sum(t for _,t in self.events)+tokens>self.limit else 0
    def record(self,tokens,now):self.events.append((now,tokens))

_QUOTA=TokenWindow()

@contextmanager
def cloud_context(folder,notify):
    token=_CONTEXT.set((Path(folder),notify))
    try:yield
    finally:_CONTEXT.reset(token)


def word_windows(words,max_words=300,overlap=60,max_chars=3600):
    windows=[];start=0
    while start<len(words):
        end=start;size=0
        while end<len(words) and end-start<max_words:
            cost=len(words[end]['text'])+len(str(words[end]['index']))+2
            if end>start and size+cost>max_chars:break
            size+=cost;end+=1
        windows.append(words[start:end])
        if end==len(words):break
        start=max(start+1,end-min(overlap,max(1,(end-start)//3)))
    return windows


def pack_items(rows,max_chars=4200,max_items=8):
    batches=[];batch=[];size=0
    for row in rows:
        cost=len(json.dumps(row,ensure_ascii=False,separators=(',',':')))
        if batch and (len(batch)>=max_items or size+cost>max_chars):batches.append(batch);batch=[];size=0
        batch.append(row);size+=cost
    if batch:batches.append(batch)
    return batches


def compact_indices(indexes):
    runs=[]
    for i in sorted(set(indexes)):
        if runs and i==runs[-1][1]+1:runs[-1][1]=i
        else:runs.append([i,i])
    return ','.join(str(a) if a==b else f'{a}-{b}' for a,b in runs)


def merge_suggestions(replies):
    groups=[];discards={}
    for reply in replies:
        for source in reply.get('groups',[]):
            original=[list(t) for t in source['takes']]
            index=source.get('selected_take',-1)
            selected=original[index] if isinstance(index,int) and 0<=index<len(original) else None
            row={**source,'takes':sorted(original)}
            if 'selected_take' in source:row['selected_take']=row['takes'].index(selected) if selected else -1
            match=next((g for g in groups if set(map(tuple,g['takes'])).intersection(map(tuple,row['takes']))),None)
            if match:
                ranges=sorted(set(map(tuple,match['takes']))|set(map(tuple,row['takes'])))
                if any(a<=ranges[i-1][1] for i,(a,b) in enumerate(ranges) if i):continue
                match['takes']=[list(t) for t in ranges]
                if 'selected_take' in row:match['selected_take']=match['takes'].index(selected) if selected else -1
            else:
                occupied=set(i for g in groups for a,b in g['takes'] for i in range(a,b+1))
                if any(occupied.intersection(range(a,b+1)) for a,b in row['takes']):continue
                groups.append(row)
        for d in reply.get('discards',[]):discards.setdefault(tuple(d['range']),d)
    return {'groups':groups,'discards':list(discards.values())}


def query_json(prompt,schema,label,*,max_output_tokens=2600,thinking_level='medium'):
    from .groq_api import GroqDirectorClient,GroqAPIError
    context=_CONTEXT.get();notify=context[1] if context else lambda message:None
    cache_input={'v':1,'prompt':prompt,'schema':schema}
    if max_output_tokens != 2600:cache_input['max_output_tokens']=max_output_tokens
    if thinking_level != 'medium':cache_input['thinking_level']=thinking_level
    key=hashlib.sha256(json.dumps(cache_input,sort_keys=True).encode()).hexdigest()
    cache=context[0]/'api-cache'/f'{key}.json' if context else None
    if cache and cache.is_file():notify(label+' · risultato salvato');return json.loads(cache.read_text(encoding='utf-8'))
    input_budget=math.ceil(len(json.dumps({'prompt':prompt,'schema':schema},ensure_ascii=False))/2)
    json_mode=False
    with _LOCK:
        for attempt in range(3):
            budget=input_budget+max_output_tokens
            while (delay:=_QUOTA.wait_seconds(budget,time.monotonic()))>0:
                notify(f'{label} · attendo quota Groq: {math.ceil(delay)} s');time.sleep(min(1,delay))
            notify(label+' · analisi in corso')
            _QUOTA.record(budget,time.monotonic())
            client=GroqDirectorClient(os.environ.get('GROQ_API_KEY',''),model='openai/gpt-oss-120b',fallback_models=(),thinking_level=thinking_level,max_retries_per_model=0,max_output_tokens=max_output_tokens,**({'json_mode':True} if json_mode else {}))
            try:reply=client.generate_json(prompt,schema)
            except GroqAPIError as exc:
                truncated=any(marker in str(exc).casefold() for marker in ('max completion tokens reached','output was truncated','output truncated','completion token limit reached'))
                malformed=any(marker in str(exc).casefold() for marker in ('failed to validate json','failed to generate json','generated json does not match','invalid structured json','json outside expected schema'))
                if malformed and attempt<2:
                    json_mode=True;thinking_level='low'
                    ceiling=max_output_tokens if input_budget>=_QUOTA.limit else _QUOTA.limit-input_budget
                    max_output_tokens=max(max_output_tokens,min(ceiling,3900))
                    notify(label+' · JSON non conforme, rigenero e verifico il documento completo')
                    continue
                if truncated and attempt<2:
                    # Reasoning also consumes the completion allowance. Retry a full
                    # document, never the provider's incomplete failed_generation.
                    ceiling=max_output_tokens if input_budget>=_QUOTA.limit else _QUOTA.limit-input_budget
                    max_output_tokens=max(max_output_tokens,min(ceiling,max_output_tokens+max(1024,max_output_tokens//2)))
                    thinking_level='low'
                    notify(label+' · risposta incompleta, riprovo con più spazio per il risultato')
                    continue
                if '(429)' not in str(exc) or attempt==2:raise
                match=re.search(r'try again in ([\d.]+)',str(exc),re.I)
                delay=min(120,max(1,float(match.group(1))+1)) if match else 61
                deadline=time.monotonic()+delay
                while time.monotonic()<deadline:
                    notify(f'{label} · quota Groq, riprendo tra {math.ceil(deadline-time.monotonic())} s');time.sleep(1)
                continue
            if reply.usage and reply.usage.get('total_tokens'):
                stamp,_=_QUOTA.events.pop();_QUOTA.record(reply.usage['total_tokens'],stamp)
            if cache:cache.parent.mkdir(parents=True,exist_ok=True);write_json(cache,reply.data)
            return reply.data
