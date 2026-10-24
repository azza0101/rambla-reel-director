"""Transcript matching keeps every occurrence; repeated lines are not deduplicated."""
import re
import unicodedata
from difflib import SequenceMatcher


def normalize(text):
    text = unicodedata.normalize("NFKD", text.casefold())
    return " ".join(re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE).split())


def similarity(a, b):
    aa, bb = normalize(a), normalize(b)
    if not aa or not bb:
        return 0.0
    at, bt = set(aa.split()), set(bb.split())
    return len(at & bt) / max(1, len(at | bt))


_STOPWORDS = {"a", "ad", "al", "alla", "alle", "che", "chi", "ci", "con", "da", "dal", "de", "del", "della", "di", "e", "ed", "è", "il", "in", "io", "la", "le", "lo", "ma", "mi", "ne", "nel", "nella", "no", "non", "o", "per", "più", "poi", "qualche", "se", "si", "sì", "sono", "su", "ti", "tu", "un", "una", "uno", "va", "vabbè", "vi"}


def _stem_token(token):
    for suffix in ("ando", "endo", "ato", "ata", "ati", "ate", "uto", "uta", "uti", "ute", "oso", "osa", "osi", "ose", "mente", "zione", "are", "ere", "ire", "i", "e", "a", "o"):
        if len(token) - len(suffix) >= 4 and token.endswith(suffix):
            return token[:-len(suffix)]
    return token


def _same_content(left, right):
    a, b = _stem_token(left), _stem_token(right)
    return a == b or (min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)))


def phrase_candidates(beat, segment, fallback_threshold=0.35):
    """Find tight, word-timed matches inside a Resolve speaker turn."""
    beat_tokens = normalize(beat.get("text", "")).split()
    if not beat_tokens:
        return []
    words = segment.get("words") or []
    if not words:
        score = similarity(beat.get("text", ""), segment.get("text", ""))
        return [{"score": score, "start_frame": segment["start_frame"], "end_frame": segment["end_frame"], "text": segment.get("text", "")} ] if score >= fallback_threshold else []
    tokens = [normalize(word.get("text", "")).split() or [""] for word in words]
    tokens = [row[0] for row in tokens]
    target_content = [_stem_token(token) for token in beat_tokens if token not in _STOPWORDS]
    if not target_content:
        target_content = beat_tokens
    target_size = len(target_content)
    # Include ASR insertions/deletions while keeping the scan linear in the turn length.
    min_size, max_size = max(1, target_size - 1), min(len(words), target_size + 3)
    results = []
    for size in range(min_size, max_size + 1):
        for start in range(0, len(words) - size + 1):
            end = start + size
            observed = [token for token in tokens[start:end] if token]
            if not observed:
                continue
            observed_content = [_stem_token(token) for token in observed if token not in _STOPWORDS]
            if not observed_content:
                observed_content = observed
            # Content overlap prevents common function words from producing matches;
            # sequence similarity allows minor ASR substitutions and inflections.
            common = {target for target in target_content if any(_same_content(target, observed) for observed in observed_content)}
            if len(target_content) >= 2 and len(common) < 2:
                continue
            if len(target_content) == 1 and (len(target_content[0]) < 4 or target_content[0] not in common):
                continue
            overlap = len(common) / max(1, len(set(target_content) | set(observed_content)))
            sequence = SequenceMatcher(None, target_content, observed_content, autojunk=False).ratio()
            score = max(overlap, sequence * 0.75)
            if score >= fallback_threshold:
                results.append({"score": score, "start_frame": words[start]["start_frame"],
                                "end_frame": words[end - 1]["end_frame"],
                                "text": " ".join(word.get("text", "") for word in words[start:end])})
    # Keep the strongest non-overlapping phrase hit from each speaker turn.
    if results:
        top_score = max(row["score"] for row in results)
        # ASR may extend a hit with adjacent words. Keep a near-best shorter phrase
        # to avoid turning a correct dialogue match into a whole-speaker-turn cut.
        results = [row for row in results if row["score"] >= top_score - 0.08]
    results.sort(key=lambda row: (row["end_frame"] - row["start_frame"], -row["score"]))
    kept = []
    for result in results:
        if not any(result["start_frame"] < other["end_frame"] and other["start_frame"] < result["end_frame"] for other in kept):
            kept.append(result)
    return kept


def beat_phrases(beat):
    """Extract clauses from long script beats so a short ASR turn can match a clause."""
    text = beat.get("text", "")
    parts = re.split(r"(?<=[.!?])\s+|[,;:]\s*|…", text)
    phrases = [part.strip() for part in parts if len([token for token in normalize(part).split() if token not in _STOPWORDS]) >= 2 or
               (len(normalize(part).split()) >= 3 and len([token for token in normalize(part).split() if token not in _STOPWORDS]) == 1)]
    return phrases or [text]


def select_scene(scenes, transcript_segments, minimum_similarity=0.42, minimum_margin=0.08):
    """Identify one script scene from its spoken lines; abstain on weak/generic matches."""
    transcript = []
    for segment in transcript_segments:
        text = segment.get("text", "")
        # Resolve often groups an entire speaker turn into one segment. Split it
        # into sentence/phrase candidates so separate screenplay beats can match.
        parts = re.split(r"(?<=[.!?])\s+|,\s+", text)
        for part_index, part in enumerate(parts):
            if normalize(part) and normalize(part) != "":
                transcript.append({**segment, "segment_id": f"{segment.get('segment_id', 's')}:{part_index}", "text": part})
    ranked = []
    for scene in scenes:
        beats = []
        for beat in scene.get("beats", []):
            if beat.get("kind") != "dialogue":
                continue
            for part in re.split(r"(?<=[.!?])\s+|,\s+|…", beat.get("text", "")):
                if len(normalize(part).split()) >= 3:
                    beats.append({**beat, "text": part})
        candidates = sorted(
            ((similarity(beat.get("text", ""), segment.get("text", "")), beat_index, segment_index)
             for beat_index, beat in enumerate(beats)
             for segment_index, segment in enumerate(transcript)
             if similarity(beat.get("text", ""), segment.get("text", "")) >= minimum_similarity),
            reverse=True,
        )
        used_beats, used_segments, matches = set(), set(), []
        for score, beat_index, segment_index in candidates:
            if beat_index in used_beats or segment_index in used_segments:
                continue
            used_beats.add(beat_index); used_segments.add(segment_index); matches.append(score)
        count = len(matches)
        coverage = count / len(beats) if beats else 0.0
        mean_score = sum(matches) / count if count else 0.0
        ranked.append((count, coverage, mean_score, scene))
    ranked.sort(key=lambda row: (row[0], row[1], row[2]), reverse=True)
    if not ranked or ranked[0][0] < 2:
        return {"scene": None, "confidence": 0.0, "candidates": [
            {"scene_id": row[3].get("scene_id"), "heading": row[3].get("heading"), "matched_lines": row[0],
             "coverage": row[1], "mean_similarity": row[2]} for row in ranked[:3]
        ]}
    best = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else (0, 0.0, 0.0, None)
    confident = best[2] >= 0.48 and (best[0] > runner_up[0] or best[2] - runner_up[2] >= minimum_margin)
    evidence = min(1.0, best[0] / 5.0)
    separation = max(0.0, (best[0] - runner_up[0]) / max(1, best[0]))
    confidence = min(1.0, best[2] * 0.55 + evidence * 0.25 + separation * 0.20)
    return {"scene": best[3] if confident else None,
            "confidence": confidence if confident else 0.0,
            "candidates": [{"scene_id": row[3].get("scene_id"), "heading": row[3].get("heading"),
                            "matched_lines": row[0], "coverage": row[1], "mean_similarity": row[2]}
                           for row in ranked[:3]],
            "ambiguous": not confident}


def align_occurrences(beats, transcript_segments, options=None):
    matches, unmatched_beats, unmatched_segments = [], [], set(range(len(transcript_segments)))
    threshold = (options or {}).get("minimum_similarity", 0.35)
    for beat in beats:
        candidates = [(similarity(beat.get("text", ""), seg.get("text", "")), i, seg)
                      for i, seg in enumerate(transcript_segments)]
        candidates = [(score, i, seg) for score, i, seg in candidates if score >= threshold]
        if not candidates:
            unmatched_beats.append(beat["beat_id"])
            continue
        # Keep all transcript occurrences for this line, to expose retakes and repeated intent.
        for score, i, seg in candidates:
            matches.append({"beat_id": beat["beat_id"], "media_id": seg.get("media_id"),
                            "start_frame": seg["start_frame"], "end_frame": seg["end_frame"],
                            "similarity": score, "confidence": score, "segment_id": seg.get("segment_id")})
            unmatched_segments.discard(i)
    return {"matches": matches, "unmatched_beats": unmatched_beats,
            "unmatched_segments": [transcript_segments[i].get("segment_id") for i in sorted(unmatched_segments)]}


def propose_take_segments(media, transcript, fps, gap_seconds=2.5):
    if fps <= 0:
        raise ValueError("frame rate must be positive")
    items = sorted(transcript, key=lambda item: item["start_frame"])
    if not items:
        return [{"take_id": media["media_id"] + ":take:1", "media_id": media["media_id"],
                 "start_frame": 0, "end_frame": media["duration_frames"], "take_index": 1,
                 "camera_id": "camera_1", "boundary_source": "whole_clip", "confirmed": False}]
    runs, run = [], [items[0]]
    for item in items[1:]:
        gap = item["start_frame"] - run[-1]["end_frame"]
        if gap > gap_seconds * fps and normalize(run[-1].get("text", "")) != normalize(item.get("text", "")):
            runs.append(run)
            run = [item]
        else:
            run.append(item)
    runs.append(run)
    if len(runs) == 1:
        return [{"take_id": media["media_id"] + ":take:1", "media_id": media["media_id"],
                 "start_frame": 0, "end_frame": media["duration_frames"], "take_index": 1,
                 "camera_id": "camera_1", "boundary_source": "whole_clip", "confirmed": False}]
    result = []
    for index, current in enumerate(runs):
        start = 0 if index == 0 else (runs[index - 1][-1]["end_frame"] + current[0]["start_frame"]) // 2
        end = media["duration_frames"] if index == len(runs) - 1 else (current[-1]["end_frame"] + runs[index + 1][0]["start_frame"]) // 2
        result.append({"take_id": f"{media['media_id']}:take:{index+1}", "media_id": media["media_id"],
                       "start_frame": start, "end_frame": end, "take_index": index + 1,
                       "camera_id": "camera_1", "boundary_source": "suggested", "confirmed": False})
    return result


def propose_take_segments_for_beats(media, beats, transcript, fps, minimum_similarity=0.35):
    """Suggests boundaries only when transcript alignment returns to an earlier screenplay beat."""
    if not beats or not transcript:
        return propose_take_segments(media, transcript, fps, gap_seconds=10**9)
    ordered = sorted(transcript, key=lambda item: item["start_frame"])
    cursor, matched, boundaries = 0, [], []
    for segment in ordered:
        ranked = [(similarity(beat.get("text", ""), segment.get("text", "")), index)
                  for index, beat in enumerate(beats) if beat.get("kind", "dialogue") == "dialogue"]
        ranked = [(score, index) for score, index in ranked if score >= minimum_similarity]
        if not ranked:
            continue
        forward = [row for row in ranked if row[1] >= cursor]
        score, beat_index = max(forward or ranked, key=lambda row: (row[0], -row[1]))
        if matched and beat_index < cursor:
            previous = matched[-1]
            boundary = (previous["end_frame"] + segment["start_frame"]) // 2
            if 0 < boundary < media["duration_frames"] and (not boundaries or boundary > boundaries[-1]):
                boundaries.append(boundary)
        matched.append(segment)
        cursor = beat_index + 1
    if not boundaries:
        return [{"take_id": media["media_id"] + ":take:1", "media_id": media["media_id"],
                 "start_frame": 0, "end_frame": media["duration_frames"], "take_index": 1,
                 "camera_id": "camera_1", "boundary_source": "whole_clip", "confirmed": False}]
    edges = [0, *boundaries, media["duration_frames"]]
    return [{"take_id": f"{media['media_id']}:take:{index+1}", "media_id": media["media_id"],
             "start_frame": start, "end_frame": end, "take_index": index + 1,
             "camera_id": "camera_1", "boundary_source": "suggested", "confirmed": False}
            for index, (start, end) in enumerate(zip(edges, edges[1:])) if end > start]


def complete_beat_candidates(beat, segments, fps):
    """Local sequence alignment; gaps allow ASR errors, intervals never join takes."""
    target=normalize(beat.get('text','')).split()
    if not target: return []
    words=[]
    for seg in sorted(segments,key=lambda s:s['start_frame']):
        items=seg.get('words') or [{'text':t,'start_frame':seg['start_frame'],'end_frame':seg['end_frame']} for t in seg.get('text','').split()]
        for word in items:
            for token in normalize(word.get('text','')).split():
                if token: words.append({**word,'token':token})
    results=[]; blocked=set()
    for attempt in range(8):
        n,m=len(target),len(words)
        scores=[[0.0]*(m+1) for _ in range(n+1)]
        pointers={}; best=(0,0,0)
        for i in range(1,n+1):
            for j in range(1,m+1):
                if j-1 in blocked: continue
                same=_same_content(target[i-1],words[j-1]['token'])
                # Do not align across a long silence / take boundary.
                prior=0 if j>1 and words[j-1]['start_frame']-words[j-2]['end_frame']>2.5*fps else scores[i-1][j-1]
                values=(0,prior+(2 if same else -1.3),scores[i-1][j]-.9,scores[i][j-1]-.9)
                value=max(values); direction=values.index(value)
                scores[i][j]=value
                if value: pointers[(i,j)]=direction
                if value>best[0]: best=(value,i,j)
        value,i,j=best
        if value<=0: break
        pairs=[]; observed=[]
        while i and j and scores[i][j]>0:
            direction=pointers.get((i,j),0)
            if direction==1:
                if _same_content(target[i-1],words[j-1]['token']): pairs.append((i-1,j-1))
                observed.append(j-1);i-=1;j-=1
            elif direction==2:i-=1
            elif direction==3:observed.append(j-1);j-=1
            else:break
        if not pairs:break
        pairs.reverse();lo,hi=min(observed),max(observed)+1
        blocked.update(range(lo,hi))
        content=[idx for idx,t in enumerate(target) if t not in _STOPWORDS]
        matched={a for a,b in pairs}
        coverage=sum(idx in matched for idx in content)/max(1,len(content)) if content else len(pairs)/len(target)
        if len(target)<=2 and (coverage<1 or len(pairs)/max(1,hi-lo)<.7):continue
        if coverage<.3 or (len(content)>2 and sum(idx in matched for idx in content)<2):continue
        if pairs[0][0]<=2 and all(t in _STOPWORDS for t in target[:pairs[0][0]]):lo=max(0,lo-pairs[0][0])
        trailing=len(target)-pairs[-1][0]-1
        if trailing<=2:hi=min(len(words),hi+trailing)
        if words[hi-1]['end_frame']-words[lo]['start_frame']>35*fps:continue
        precision=len(pairs)/max(1,hi-lo)
        results.append({'start_frame':words[lo]['start_frame'],'end_frame':words[hi-1]['end_frame'],
                        'coverage':coverage,'score':.8*coverage+.2*precision,
                        'text':' '.join(w['text'] for w in words[lo:hi])})
    return sorted(results,key=lambda h:(-h['coverage'],-h['score']))


def semantic_windows(source, fps):
    """Candidate utterances retain real word timestamps, never invented timing."""
    units=[]
    for segment in sorted(source.get('segments',[]),key=lambda s:s['start_frame'] if 'start_frame' in s else s['words'][0]['start_frame']):
        current=[]
        words=segment.get('words') or [{'text':segment.get('text',''),'start_frame':segment['start_frame'],'end_frame':segment['end_frame']}]
        for word in words:
            if not normalize(word.get('text','')) or word['text'].strip()=='(...)':continue
            current.append(word)
            if re.search(r'[.!?]$',word['text'].strip()) or (len(current)>5 and word['end_frame']-current[0]['start_frame']>8*fps):
                units.append(current);current=[]
        if current:units.append(current)
    windows=[]
    for i in range(len(units)):
        combined=[];previous_texts=[]
        for unit in units[i:i+8]:
            text=' '.join(w['text'].strip() for w in unit)
            if combined and unit[0]['start_frame']-combined[-1]['end_frame']>2.5*fps:break
            # A repeated sentence begins another attempt, not one longer line.
            core=[_stem_token(t) for t in normalize(text).split() if t not in _STOPWORDS]
            repeated=False
            if len(core)>=2:
                for old in previous_texts:
                    old_core=[_stem_token(t) for t in normalize(old).split() if t not in _STOPWORDS]
                    if (len(old_core)>=2 and core[:2]==old_core[:2]) or SequenceMatcher(None,core,old_core,autojunk=False).find_longest_match(0,len(core),0,len(old_core)).size>=3:repeated=True;break
            if repeated:break
            combined+=unit;previous_texts.append(text)
            if len(combined)>120 or combined[-1]['end_frame']-combined[0]['start_frame']>35*fps:break
            windows.append({'media_id':source['media_id'],'start_frame':combined[0]['start_frame'],
                            'end_frame':combined[-1]['end_frame'],'text':' '.join(w['text'].strip() for w in combined)})
    return windows


def contextual_path(candidates):
    """Scene-level monotonic alignment, with an explicit unmatched option."""
    states=[(0.0,0,[])]
    for rows in candidates:
        next_states=[(value-.18,end,path+[None]) for value,end,path in states]
        for row in rows:
            eligible=[s for s in states if s[1]<=row['start_frame']]
            if eligible:
                value,_,path=max(eligible,key=lambda s:s[0])
                next_states.append((value+row['score']-.45,row['end_frame'],path+[row]))
        states=[];best=-float('inf')
        for state in sorted(next_states,key=lambda s:s[1]):
            if state[0]>best:states.append(state);best=state[0]
    return max(states,key=lambda s:s[0])[2]


class LocalSemanticEncoder:
    def __init__(self):
        import json,hashlib,sys
        from pathlib import Path
        import onnxruntime as ort
        from tokenizers import Tokenizer
        roots=[Path(sys.executable).parent/'models'/'semantic',Path(__file__).resolve().parents[1]/'runtime'/'models'/'semantic']
        folder=next((p for p in roots if (p/'model-lock.json').is_file()),None)
        if folder is None:raise RuntimeError('Modello semantico locale mancante: reinstalla Premontato')
        lock=json.loads((folder/'model-lock.json').read_text(encoding='utf8'))
        for name in ['model.onnx','tokenizer.json']:
            if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=lock['files'][name]['sha256']:
                raise RuntimeError('Modello semantico danneggiato: reinstalla Premontato')
        self.tokenizer=Tokenizer.from_file(str(folder/'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=128);self.tokenizer.enable_padding()
        options=ort.SessionOptions();options.intra_op_num_threads=4
        self.model=ort.InferenceSession(str(folder/'model.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
        self.cache={}
    def encode(self,texts):
        import numpy as np
        missing=list(dict.fromkeys(text for text in texts if text not in self.cache))
        if len(self.cache)>5000:self.cache.clear();missing=list(dict.fromkeys(texts))
        for start in range(0,len(missing),32):
            batch=self.tokenizer.encode_batch(missing[start:start+32])
            mask=np.array([b.attention_mask for b in batch],dtype=np.int64)
            args={'input_ids':np.array([b.ids for b in batch],dtype=np.int64),'attention_mask':mask,'token_type_ids':np.array([b.type_ids for b in batch],dtype=np.int64)}
            output=self.model.run(None,{i.name:args[i.name] for i in self.model.get_inputs()})[0]
            if output.ndim==3:output=(output*mask[:,:,None]).sum(1)/np.maximum(mask.sum(1)[:,None],1)
            output=output/np.maximum(np.linalg.norm(output,axis=1,keepdims=True),1e-9)
            self.cache.update(zip(missing[start:start+32],output))
        return np.array([self.cache[text] for text in texts])


_SEMANTIC_ENCODER=None

def semantic_scene_hits(beats, sources, fps):
    global _SEMANTIC_ENCODER
    if _SEMANTIC_ENCODER is None:_SEMANTIC_ENCODER=LocalSemanticEncoder()
    dialogue=[b for b in beats if b.get('kind')=='dialogue']
    windows=[(s,semantic_windows(s,fps)) for s in sources]
    flat=[w for s,rows in windows for w in rows]
    if not flat or not dialogue:return {}
    encoder=_SEMANTIC_ENCODER
    queries=encoder.encode([b['text'] for b in dialogue]);vectors=encoder.encode([w['text'] for w in flat])
    similarities=queries@vectors.T
    clause_vectors=[encoder.encode(beat_phrases(beat)) for beat in dialogue]
    output={};offset=0
    for source,rows in windows:
        candidates=[]
        for i,beat in enumerate(dialogue):
            target=normalize(beat['text']).split();content=[t for t in target if t not in _STOPWORDS]
            choices=[]
            for k,row in enumerate(rows):
                observed=normalize(row['text']).split();semantic=float(similarities[i,offset+k])
                if semantic<.48:continue
                if len(target)==1 and target[0] not in observed:continue
                coverage=sum(any(_same_content(t,o) for o in observed) for t in content)/max(1,len(content))
                inside=[offset+j for j,w in enumerate(rows) if w['start_frame']>=row['start_frame'] and w['end_frame']<=row['end_frame']]
                support=float((clause_vectors[i]@vectors[inside].T).max(axis=1).mean()) if inside else semantic
                score=.8*semantic+.2*coverage
                if len(content)>=2 and coverage==0 and semantic<.8:continue
                # Equivalent candidates should prefer a clean, compact utterance.
                score-=.015*max(0,len(observed)-len(target))/max(1,len(target))
                choices.append({**row,'score':score,'semantic_score':semantic,'coverage':coverage,'semantic_completeness':support,'match_method':'semantic_context'})
            candidates.append(sorted(choices,key=lambda c:c['score'],reverse=True)[:40])
        path=contextual_path(candidates)
        all_words=[w for seg in source.get('segments',[]) for w in seg.get('words',[]) if normalize(w.get('text','')) and w['text'].strip()!='(...)']
        all_words.sort(key=lambda w:w['start_frame'])
        for index,(beat,hit) in enumerate(zip(dialogue,path)):
            if not hit:continue
            if len(normalize(beat['text']).split())>7:
                following=next((p for p in path[index+1:] if p),None)
                safe_end=max((w['end_frame'] for w in rows if w['start_frame']==hit['start_frame']),default=hit['end_frame'])
                limit=min(following['start_frame'] if following else hit['end_frame']+5*fps,hit['start_frame']+35*fps,safe_end)
                end=hit['end_frame'];sentence_end=end
                for word in all_words:
                    if word['start_frame']<end:continue
                    if word['end_frame']>limit or word['start_frame']-end>1.2*fps:break
                    end=word['end_frame']
                    if re.search(r'[.!?]$',word['text'].strip()):sentence_end=end
                end=sentence_end
                if end>hit['end_frame']:
                    hit={**hit,'end_frame':end,'text':' '.join(w['text'].strip() for w in all_words if w['start_frame']>=hit['start_frame'] and w['end_frame']<=end)}
            else:
                subset=[{**seg,'words':[w for w in seg.get('words',[]) if w['start_frame']>=hit['start_frame'] and w['end_frame']<=hit['end_frame']]} for seg in source.get('segments',[])]
                subset=[seg for seg in subset if seg['words']]
                tight=complete_beat_candidates(beat,subset,fps)
                if tight and tight[0]['coverage']>=.65:
                    hit={**hit,'start_frame':tight[0]['start_frame'],'end_frame':tight[0]['end_frame'],'text':tight[0]['text']}
            output[(source['take_id'],beat['beat_id'])]=[hit]
        offset+=len(rows)
    return output
