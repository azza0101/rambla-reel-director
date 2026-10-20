"""Local completion and readable timing for highlighted expressions."""
import re

_COMMON = set('il lo la i gli le un uno una e ma o quando come perché perchè noi voi io tu lui lei non sì si no poi questo questa questi queste the a an and but when how'.split())


def _token(word):
    return str(word.get('text',word.get('word',''))).strip()


def _proper(word):
    text=_token(word).strip('.,;:!?“”"()[]')
    return bool(text and text[0].isupper() and text.casefold() not in _COMMON)


def _refs(chunks):
    refs=[]
    for c in chunks:
        words=c.get('words')
        if not words:
            tokens=str(c.get('text','')).split()
            start=float(c.get('start',0));end=float(c.get('end',start+len(tokens)))
            step=(end-start)/max(1,len(tokens))
            words=[{'text':text,'start':start+i*step,'end':start+(i+1)*step} for i,text in enumerate(tokens)]
        refs.extend((str(c['id']),i,w) for i,w in enumerate(words))
    return refs


def expanded_highlight_indices(chunks, phrases):
    """Complete short adjacent capitalized names; never cross sentence/pause cuts."""
    refs=_refs(chunks)
    selected={(cid,i) for cid,i,w in refs if i in phrases.get(cid,{}).get('highlighted_word_indices',[])}
    groups=[]
    for position,(cid,i,w) in enumerate(refs):
        if not _proper(w):
            continue
        previous=groups[-1][-1] if groups else None
        adjacent=previous and position==previous[3]+1
        if (adjacent and len(groups[-1])<3 and not re.search(r'[.!?;:]$',_token(previous[2]))
                and float(w['start'])-float(previous[2]['end'])<=.35):
            groups[-1].append((cid,i,w,previous[3]+1))
        else:
            groups.append([(cid,i,w,position)])
    for group in groups:
        keys={(cid,i) for cid,i,w,_ in group}
        if len(group)>1 and selected & keys:selected.update(keys)
    result={str(c['id']):[] for c in chunks}
    for cid,i in sorted(selected):result[cid].append(i)
    return result


def highlight_ranges(chunks, phrases, *, max_words=3):
    refs=_refs(chunks)
    indices=expanded_highlight_indices(chunks,phrases)
    groups=[]
    for position,(cid,i,w) in enumerate(refs):
        if i not in indices.get(cid,[]):continue
        prev=groups[-1][-1] if groups else None
        joins=prev and position==prev[0]+1 and len(groups[-1])<max_words
        # Join across a chunk edge only for a compound proper name.
        joins=joins and (cid==prev[1] or (_proper(w) and _proper(prev[3])))
        joins=joins and float(w['start'])-float(prev[3]['end'])<=.35 and not re.search(r'[.!?;:]$',_token(prev[3]))
        name_width=1
        if _proper(w):
            for _,_,following in refs[position+1:position+3]:
                if not _proper(following):break
                name_width+=1
        if joins and len(groups[-1])+name_width>max_words:joins=False
        entry=(position,cid,i,w)
        if joins:groups[-1].append(entry)
        else:groups.append([entry])
    ranges=[]
    for g in groups:
        ranges.append({'source_chunk_ids':list(dict.fromkeys(x[1] for x in g)),
            'text':' '.join(_token(x[3]) for x in g),
            'start_seconds':float(g[0][3]['start']),'end_seconds':float(g[-1][3]['end']),
            'word_start_index':g[0][2],'word_end_index':g[-1][2],
            'word_refs':[(x[1],x[2]) for x in g]})
    timeline_end=max((float(w['end']) for _,_,w in refs),default=0)
    for n,row in enumerate(ranges):
        floor=.95 if len(row['word_refs'])>1 else .65
        limit=ranges[n+1]['start_seconds'] if n+1<len(ranges) else timeline_end
        row['end_seconds']=min(limit,max(row['end_seconds'],row['start_seconds']+floor))
        if row['end_seconds']-row['start_seconds']<floor:
            prior=ranges[n-1]['end_seconds'] if n else 0
            row['start_seconds']=max(prior,row['start_seconds']-.12,row['end_seconds']-floor)
    return ranges
