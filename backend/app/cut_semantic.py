"""Semantic selection of literal passages; source indices are computed locally."""
import re
import json
from .cut_pass import words_of

REVIEW_VERSION = 4


def _tokens(text):
    return [re.sub(r'[^\w]', '', token.casefold()) for token in text.split()]


def resolve_passages(words,passages):
    """Exact contiguous quotes, selected backwards to prefer the latest take."""
    source=[_tokens(w['text'])[0] for w in words]
    limit=len(words);resolved=[]
    for text in reversed(passages):
        needle=_tokens(text)
        if not needle or any(not token for token in needle):raise ValueError('Citazione CUT vuota o non valida')
        matches=[i for i in range(limit-len(needle)+1) if source[i:i+len(needle)]==needle]
        if matches:
            positions=list(range(matches[-1],matches[-1]+len(needle)))
        else:
            # The model may join two source excerpts after deleting a restart.
            # Accept only an exact ordered source subsequence, never invented words.
            cursor=limit-1;positions=[]
            for token in reversed(needle):
                while cursor>=0 and source[cursor]!=token:cursor-=1
                if cursor<0:raise ValueError('Citazione CUT non trovata nella trascrizione originale: '+text[:100])
                positions.append(cursor);cursor-=1
            positions.reverse()
            if positions[-1]-positions[0]+1>max(len(needle)*3,len(needle)+80):raise ValueError('Citazione CUT dispersa: revisione necessaria')
        pieces=[]
        for k in positions:
            index=words[k]['index']
            if pieces and pieces[-1][1]+1==index:pieces[-1][1]=index
            else:pieces.append([index,index])
        resolved.extend(reversed(pieces));limit=positions[0]
    return list(reversed(resolved))


def propose_semantic_groups(transcript):
    from .cut_cloud import query_editorial_json,word_windows
    words=words_of(transcript)
    if len(words)>900:
        selected=set()
        for window in word_windows(words,max_words=850,max_chars=6500,overlap=180):
            wanted={w['index'] for w in window};segments=[];offset=0
            for segment in transcript['segments']:
                count=len(segment.get('words',[]));part=[w for w in words[offset:offset+count] if w['index'] in wanted]
                if part:segments.append({'words':part})
                offset+=count
            local=propose_semantic_groups({'segments':segments});selected.difference_update(wanted)
            selected.update(window[i]['index'] for i in local['selected_word_indices'])
        ranges=[]
        for i in sorted(selected):
            if ranges and ranges[-1][1]+1==i:ranges[-1][1]=i
            else:ranges.append([i,i])
        return _finalize_selection(transcript,selected)
    units=[];offset=0
    for segment in transcript['segments']:
        count=len(segment.get('words',[]))
        if count:units.append(words[offset:offset+count])
        offset+=count
    schema={'type':'object','additionalProperties':False,'required':['keep_blocks','discard_blocks','trim_blocks'],'properties':{
        'keep_blocks':{'type':'array','items':{'type':'integer'}},'discard_blocks':{'type':'array','items':{'type':'integer'}},
        'trim_blocks':{'type':'array','items':{'type':'object','additionalProperties':False,'required':['block','keep_text'],'properties':{'block':{'type':'integer'},'keep_text':{'type':'array','items':{'type':'string'}}}}}}}
    prompt="""Monta il parlato italiano grezzo. Tieni OGNI informazione unica e soltanto l'ULTIMA take riuscita delle frasi ripetute. Scarta regia, indicazioni su come dire le frasi, conferme fuori scena, errori e ripartenze sostituiti. Non riassumere o correggere grammatica/ASR.
Ogni blocco ASR sotto deve comparire UNA volta in keep_blocks (tutto buono), discard_blocks (tutto da togliere), oppure trim_blocks (misto). Per trim_blocks copia in keep_text SOLO le parti buone testuali esatte del blocco, nell'ordine; il software trova le parole e i tempi originali.
Non tenere versioni precedenti solo perche complete: se la battuta viene rifatta, scegli l'ultima. Conserva premesse e completamenti unici. Aneddoti, luoghi, spiegazioni, domande e risposte utili restano. Le istruzioni rivolte a chi recita e i commenti alla ripresa non fanno parte del racconto.
Prima della risposta rileggi il montaggio simulato: niente doppioni e niente regia. Non riscrivere il testo. Valuta tutti i blocchi, anche se un blocco e solo un pezzo di frase.
BLOCCHI:\n"""+'\n'.join(f"{i}: "+' '.join(w['text'] for w in unit) for i,unit in enumerate(units))
    cost=(len(json.dumps({'prompt':prompt,'schema':schema},ensure_ascii=False).encode('utf-8'))+2)//3+128
    output=min(5500,7500-cost)
    if output<2000:raise ValueError('Contesto CUT troppo lungo per la quota')
    data=query_editorial_json(prompt,schema,'Revisione completa: take e regia',max_output_tokens=output,thinking_level='medium',preserve_reasoning=True,input_token_budget=cost)
    seen=set();selected=set()
    def claim(index):
        if type(index) is not int or not 0<=index<len(units) or index in seen:raise ValueError('Blocchi CUT mancanti o duplicati')
        seen.add(index)
    for i in data['keep_blocks']:claim(i);selected.update(w['index'] for w in units[i])
    for i in data['discard_blocks']:claim(i)
    for trim in data['trim_blocks']:
        i=trim['block'];claim(i)
        for a,b in resolve_passages(units[i],trim['keep_text']):selected.update(range(a,b+1))
    if seen!=set(range(len(units))):raise ValueError('Revisione CUT incompleta: nessun risultato salvato')
    if not selected:raise ValueError('Nessuna battuta mantenuta: verificare la revisione CUT')
    ranges=[]
    for i in sorted(selected):
        if ranges and ranges[-1][1]+1==i:ranges[-1][1]=i
        else:ranges.append([i,i])
    return _finalize_selection(transcript,selected)


def _finalize_selection(transcript,selected):
    words=words_of(transcript)
    from .cut_restart_reconcile import reconcile_selected_words
    selected,groups=reconcile_selected_words(transcript,selected)
    owned={i for group in groups for a,b in group['takes'] for i in range(a,b+1)}
    discards=[]
    for word in words:
        i=word['index']
        if i in selected or i in owned:continue
        if discards and discards[-1]['range'][1]+1==i:discards[-1]['range'][1]=i
        else:discards.append({'range':[i,i],'reason':'Regia o tentativo escluso dalla revisione del parlato.','confidence':.95})
    return {'groups':groups,'discards':discards,'selected_word_indices':sorted(selected),'warnings':[],'semantic_review_version':REVIEW_VERSION}
