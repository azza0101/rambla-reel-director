"""Retrieval-only constraints and relevance. Never infer a new editorial shot."""
import re

VERSION='retrieval-quality-8'
STOP=set('a an the of on in at with and or to for by is are close up view shot photo image video footage hands small large background'.split())
GROUPS=[('wilt','wilting','wilted','droop','drooping','withered'),('slice','slicing','sliced','cut','cutting','chop','chopping','chopped'),('tomato','tomatoes'),('dry','dried'),('empty','vacant'),('closed','shut')]
CANON={w:group[0] for group in GROUPS for w in group}
CONTRASTS={'wilt':{'healthy','fresh','lush'},'dry':{'wet','soaked'},'empty':{'full','crowded'},'closed':{'open'}}


def terms(text):
    return {CANON.get(w,w[:-1] if w.endswith('s') and len(w)>4 else w) for w in re.findall(r'[a-z]+',text.lower()) if w not in STOP}


def expand_queries(queries,kind):
    """Bounded retrieval aliases only; preserve subject/condition, log provenance."""
    out=list(dict.fromkeys(queries))
    for q in queries:
        alias=q
        for old,new in [('local guide','tour guide'),('guesthouse','guest house'),('travelers','tourists')]:
            alias=re.sub(r'\b'+old+r'\b',new,alias,flags=re.I)
        if alias!=q and alias not in out:out.append(alias)
        broad=re.sub(r'\blocal\s+','',alias,flags=re.I)
        if broad not in out:out.append(broad)
    for q in queries:
        if re.search(r'\b(wilted|wilting|dying|drooping)\b',q,re.I):
            base=re.sub(r'\b(on |in |a |the )?(balcony|windowsill|terrace)\b','',q,flags=re.I)
            base=' '.join(base.split())
            if base!=q and 'plant' not in base:base+=' plant'
            for variant in [base,re.sub(r'\b(wilted|wilting|dying)\b','drooping',base),re.sub(r'\b(wilted|wilting|drooping)\b','dying',base)]:
                if variant not in out:out.append(variant)
    for q in queries:
        compact=re.sub(r'\b(in a small pot|close up|close-up|photo of|image of|video of)\b','',q,flags=re.I)
        compact=' '.join(compact.split())
        if compact and compact not in out: out.append(compact)
        for old,new in (('wilted','wilting'),('wilting','drooping'),('slicing','cutting'),('chopped','sliced')):
            variant=re.sub(r'\b'+old+r'\b',new,compact,flags=re.I)
            if variant!=compact and variant not in out: out.append(variant)
    for q in list(out):
        variant=re.sub(r'\bplant\b','',q,flags=re.I)
        variant=' '.join(variant.split())
        if len(variant.split())>=2 and variant not in out:out.append(variant)
    return out[:max(len(queries),6)]


def metadata_quality(intent,text):
    wanted=terms(intent); found=terms(text)
    overlap=len(wanted & found)/max(1,len(wanted))
    contradictions=[c for c,opposites in CONTRASTS.items() if c in wanted and found & opposites and c not in found]
    missing_conditions=[c for c in CONTRASTS if c in wanted and c not in found]
    generic=bool(re.search(r'\b(vlog|youtuber|subscribe|my trip|travel diary|selfie|reaction)\b',text,re.I)) and not bool(re.search(r'\b(vlog|youtuber|selfie|reaction)\b',intent,re.I))
    return overlap,contradictions,missing_conditions,generic


class QualityRanker:
    def __init__(self,visual=None):
        self.visual=visual
        self.warning=None if visual is not None else 'Qwen ranker unavailable; metadata-only relevance review'

    def rank(self,intent,assets):
        measured={}
        counter={}
        query_measured={}
        talking_head={}
        graphic_frame={}
        action_counter={}
        participant_counter={}
        def visual_rank(query,rows):
            return [r for i in range(0,len(rows),4) for r in self.visual.rank(query,rows[i:i+4])]
        if self.visual and assets:
            try:
                measured={r['id']:r for r in visual_rank(intent,assets)}
                # Preserve the exact multilingual shot; its own imported search phrase
                # supplies a second view, never transcript/theme context.
                for query in dict.fromkeys(a.get('retrieval_query') or a.get('query') for a in assets):
                    if query:
                        group=[a for a in assets if (a.get('retrieval_query') or a.get('query'))==query]
                        query_measured.update({r['id']:r.get('embedding_score') for r in (visual_rank(query,group) if query!=intent else [measured[a['id']] for a in group])})
                        opposite_action=re.sub(r'\bboarding\b','sitting inside',query,flags=re.I)
                        video_group=[a for a in group if a.get('kind')=='video']
                        if video_group:
                            graphic_frame.update({r['id']:r.get('embedding_score') for r in visual_rank('An animated diagram of '+query+'.',video_group)})
                        if video_group and re.search(r'\bboarding\b',query,re.I) and re.search(r'\b(passengers|travelers|tourists|people)\b',query,re.I):
                            alternatives=[re.sub(r'\b(passengers|travelers|tourists|people)\b','vehicles',query,flags=re.I),'Empty scene without people: '+re.sub(r'\b(passengers|travelers|tourists|people) boarding\b','',query,flags=re.I)]
                            for alternative in alternatives:
                                for r in visual_rank(alternative,video_group):participant_counter[r['id']]=max(participant_counter.get(r['id'],0),r['embedding_score'])
                        if opposite_action!=query and video_group:
                            action_counter.update({r['id']:r.get('embedding_score') for r in visual_rank(opposite_action,video_group)})
                alternative=re.sub(r'\b(wilted|wilting|dying|drooping)\b','healthy lush',intent,flags=re.I)
                alternative=re.sub(r'\bappassit[aoe]\b','rigogliosa e sana',alternative,flags=re.I)
                if alternative!=intent:counter={r['id']:r.get('embedding_score') for r in visual_rank(alternative,assets)}
                if any(a.get('kind')=='video' for a in assets) and not re.search(r'\b(talking|speaking|interview|conversa|parla)\b',intent,re.I):
                    talking_head={r['id']:r.get('embedding_score') for r in visual_rank('A person talking directly to camera in a vlog, face close-up.',assets)}
            except Exception as exc:
                self.warning='Visual ranker unavailable: '+type(exc).__name__
                self.visual=None
        output=[]
        for a in assets:
            meta,contradictions,missing,generic=metadata_quality(intent,a.get('description','')+' '+a.get('title',''))
            visual=measured.get(a['id'],{}).get('embedding_score')
            shot_visual=visual
            query_visual=query_measured.get(a['id'])
            if visual is not None and query_visual is not None:visual=.4*float(visual)+.6*float(query_visual)
            penalty=.18 if generic and visual is None else 0
            # Missing English words in a multilingual description are not negative
            # visual evidence. Metadata remains a fallback, not a cosine multiplier.
            score=(float(visual) if visual is not None else meta*.75)-penalty
            reasons=[]
            opposite=counter.get(a['id'])
            contradiction=bool(contradictions) if visual is None else opposite is not None and opposite>=float(shot_visual)-.02
            nonphoto=bool(re.search(r'\b(collage|diagram|illustration|drawing|logo)\b',a.get('title',''),re.I)) and not re.search(r'\b(collage|diagram|illustration|drawing|logo)\b',intent,re.I)
            graphic=graphic_frame.get(a['id'])
            nonphoto=nonphoto or (graphic is not None and visual is not None and graphic>float(visual)+.03 and not re.search(r'animation|simulation|diagram|illustrat',intent,re.I))
            if graphic is not None and nonphoto:reasons.append('non-photographic frame evidence')
            if nonphoto:reasons.append('non-photographic/composite result')
            face=talking_head.get(a['id'])
            creator_frame=face is not None and visual is not None and face>float(visual)+.03
            if creator_frame:reasons.append('actual frame matches talking-head vlog more than requested action')
            opposite_action=action_counter.get(a['id'])
            wrong_action=opposite_action is not None and query_visual is not None and opposite_action>query_visual+.01
            wrong_participant=participant_counter.get(a['id']) is not None and query_visual is not None and participant_counter[a['id']]>query_visual+.01
            if wrong_participant:reasons.append('vehicles or empty scene match frames better than requested people')
            if wrong_action:reasons.append('opposite action matches actual frames better')
            if contradiction: reasons.append('contradictory condition evidence')
            if missing and visual is None:reasons.append('condition unverified without visual ranker')
            if generic: reasons.append('generic creator/vlog penalty')
            weak_visual=visual is not None and float(visual)<.45
            if weak_visual:reasons.append('visual evidence below relevance floor')
            reject=wrong_participant or wrong_action or contradiction or creator_frame or nonphoto or weak_visual or score<.42 or (visual is None and (bool(missing) or meta<.65))
            if score<.42:reasons.append('below relevance floor')
            if reject: score=min(score,.29)
            state='rejected' if reject else ('accepted' if float(visual)>=.60 else 'needs_review') if visual is not None else 'metadata_only'
            if state=='needs_review':reasons.append('borderline visual relevance; inspect candidate')
            output.append({**a,'score':round(max(0,score),4),'embedding_score':visual,'metadata_score':round(meta,4),
                'shot_embedding_score':shot_visual,'query_embedding_score':query_visual,
                'quality_state':state,'condition_counter_score':opposite,'action_counter_score':opposite_action,'quality_reasons':reasons,'rank_reason':'Qwen visual + shot metadata' if visual is not None else 'Metadata only; visual relevance needs review',
                'ranking_warning':self.warning,'matched_query':a.get('query') or a.get('matched_query')})
        return sorted(output,key=lambda r:-r['score'])
