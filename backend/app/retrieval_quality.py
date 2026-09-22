"""Retrieval-only constraints and relevance. Never infer a new editorial shot."""
import re

from .editorial_relevance import decode_retrieval_intent

VERSION='retrieval-quality-10'
STOP=set('a an the of on in at with and or to for by is are close up view shot photo image video footage hands small large background'.split())
GROUPS=[('wilt','wilting','wilted','droop','drooping','withered'),('slice','slicing','sliced','cut','cutting','chop','chopping','chopped'),('tomato','tomatoes'),('dry','dried'),('empty','vacant'),('closed','shut')]
CANON={w:group[0] for group in GROUPS for w in group}
CONTRASTS={'wilt':{'healthy','fresh','lush'},'dry':{'wet','soaked'},'empty':{'full','crowded'},'closed':{'open'}}
GENERIC_PROPS={
    'laptop': re.compile(r'\b(laptop|computer|typing|notebook|taking notes?|working remotely)\b',re.I),
    'map': re.compile(r'\b(map|route planning|travel planning|itinerary planning|comparing routes?)\b',re.I),
    'hotel': re.compile(r'\b(hotel room|accommodation options?|booking|hotel comparison)\b',re.I),
    'tutorial': re.compile(r'\b(tutorial|tips|how to|guide to|text on screen|presentation|slide)\b',re.I),
}


def terms(text):
    return {CANON.get(w,w[:-1] if w.endswith('s') and len(w)>4 else w) for w in re.findall(r'[a-z]+',text.lower()) if w not in STOP}


def expand_queries(queries,kind):
    """Bounded retrieval aliases only; preserve subject/condition, log provenance."""
    out=list(dict.fromkeys(queries))
    for q in queries:
        alias=q
        for old,new in [
            ('local guide','tour guide'),('guesthouse','guest house'),('travelers','tourists'),
            ('passengers','people'),('airplane','plane'),('ferry','boat'),
        ]:
            alias=re.sub(r'\b'+old+r'\b',new,alias,flags=re.I)
        if alias!=q and alias not in out:out.append(alias)
        broad=re.sub(r'\blocal\s+','',alias,flags=re.I)
        broad=re.sub(r'\b(long[- ]haul|custom)\s+','',broad,flags=re.I)
        broad=' '.join(broad.split())
        if broad and broad not in out:out.append(broad)
    for q in queries:
        if re.search(r'\b(compare|comparing|plan|planning)\b',q,re.I) and re.search(r'\b(route|routes|itinerary|itineraries)\b',q,re.I):
            for variant in ('travel planning map','route planning map','trip planning map','travel itinerary map'):
                if variant not in out:out.append(variant)
        elif re.search(r'\b(custom\s+)?travel\s+itinerary\s+planning\b|\btraveler\s+planning\s+itinerary\b',q,re.I):
            for variant in ('travel itinerary planning','trip planning map','travel planning map'):
                if variant not in out:out.append(variant)
    for q in queries:
        if re.search(r'\bvegetable garden\b',q,re.I) and re.search(r'\bchickens?\b',q,re.I):
            for variant in ('chickens vegetable garden','free range chickens garden'):
                if variant not in out:out.append(variant)
        if re.search(r'\b(wilted|wilting|dying|drooping)\b',q,re.I):
            base=re.sub(r'\b(on |in |a |the )?(balcony|windowsill|terrace)\b','',q,flags=re.I)
            base=' '.join(base.split())
            if base!=q and 'plant' not in base:base+=' plant'
            for variant in [
                base,
                re.sub(r'\b(wilted|wilting|dying)\b','drooping',base,flags=re.I),
                re.sub(r'\b(wilted|wilting|drooping)\b','dying',base,flags=re.I),
            ]:
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


def generic_prop_mismatches(target,text):
    target=str(target or '')
    text=str(text or '')
    return [name for name,pattern in GENERIC_PROPS.items() if pattern.search(text) and not pattern.search(target)]


class QualityRanker:
    def __init__(self,visual=None):
        self.visual=visual
        self.warning=None if visual is not None else 'Qwen ranker unavailable; metadata-only relevance review'

    def rank(self,intent,assets):
        spec=decode_retrieval_intent(intent)
        editorial_intent=spec['positive'] or str(intent or '')
        positive_intent=spec.get('visual_target') or editorial_intent
        negatives=list(spec.get('negatives') or [])[:3]
        measured={};counter={};query_measured={};talking_head={};graphic_frame={};action_counter={};participant_counter={};negative_counter={}
        def visual_rank(query,rows):
            return [r for i in range(0,len(rows),4) for r in self.visual.rank(query,rows[i:i+4])]
        if self.visual and assets:
            try:
                measured={r['id']:r for r in visual_rank(positive_intent,assets)}
                for query in dict.fromkeys(a.get('retrieval_query') or a.get('query') for a in assets):
                    if query:
                        group=[a for a in assets if (a.get('retrieval_query') or a.get('query'))==query]
                        query_measured.update({r['id']:r.get('embedding_score') for r in (visual_rank(query,group) if query!=positive_intent else [measured[a['id']] for a in group])})
                        opposite_action=re.sub(r'\bboarding\b','sitting inside',query,flags=re.I)
                        video_group=[a for a in group if a.get('kind')=='video']
                        if video_group:graphic_frame.update({r['id']:r.get('embedding_score') for r in visual_rank('An animated diagram of '+query+'.',video_group)})
                        if video_group and re.search(r'\bboarding\b',query,re.I) and re.search(r'\b(passengers|travelers|tourists|people)\b',query,re.I):
                            alternatives=[re.sub(r'\b(passengers|travelers|tourists|people)\b','vehicles',query,flags=re.I),'Empty scene without people: '+re.sub(r'\b(passengers|travelers|tourists|people) boarding\b','',query,flags=re.I)]
                            for alternative in alternatives:
                                for r in visual_rank(alternative,video_group):participant_counter[r['id']]=max(participant_counter.get(r['id'],0),r['embedding_score'])
                        if opposite_action!=query and video_group:action_counter.update({r['id']:r.get('embedding_score') for r in visual_rank(opposite_action,video_group)})
                alternative=re.sub(r'\b(wilted|wilting|dying|drooping)\b','healthy lush',positive_intent,flags=re.I)
                alternative=re.sub(r'\bappassit[aoe]\b','rigogliosa e sana',alternative,flags=re.I)
                if alternative!=positive_intent:counter={r['id']:r.get('embedding_score') for r in visual_rank(alternative,assets)}
                if any(a.get('kind')=='video' for a in assets) and not re.search(r'\b(talking|speaking|interview|conversa|parla)\b',positive_intent,re.I):talking_head={r['id']:r.get('embedding_score') for r in visual_rank('A person talking directly to camera in a vlog, face close-up.',assets)}
                for negative in negatives:
                    for r in visual_rank('Unwanted visual: '+negative,assets):
                        value=r.get('embedding_score')
                        if value is not None:negative_counter[r['id']]=max(float(value),negative_counter.get(r['id'],float('-inf')))
            except Exception as exc:
                self.warning='Visual ranker unavailable: '+type(exc).__name__;self.visual=None
        output=[]
        for a in assets:
            metadata_text=a.get('description','')+' '+a.get('title','')
            meta,contradictions,missing,generic=metadata_quality(positive_intent,metadata_text)
            prop_mismatches=generic_prop_mismatches(positive_intent,metadata_text)
            visual=measured.get(a['id'],{}).get('embedding_score');positive_visual=visual;query_visual=query_measured.get(a['id'])
            if visual is not None and query_visual is not None:visual=.72*float(visual)+.28*float(query_visual)
            penalty=(.10 if generic else 0)+(.12 if prop_mismatches else 0);score=(float(visual) if visual is not None else meta*.75)-penalty;reasons=[]
            opposite=counter.get(a['id']);contradiction=bool(contradictions) if visual is None else opposite is not None and positive_visual is not None and opposite>=float(positive_visual)-.02
            nonphoto=bool(re.search(r'\b(collage|diagram|illustration|drawing|logo)\b',a.get('title',''),re.I)) and not re.search(r'\b(collage|diagram|illustration|drawing|logo)\b',positive_intent,re.I)
            graphic=graphic_frame.get(a['id']);nonphoto=nonphoto or (graphic is not None and visual is not None and graphic>float(visual)+.03 and not re.search(r'animation|simulation|diagram|illustrat',positive_intent,re.I))
            if graphic is not None and nonphoto:reasons.append('non-photographic frame evidence')
            if nonphoto:reasons.append('non-photographic/composite result')
            face=talking_head.get(a['id']);creator_frame=face is not None and visual is not None and face>float(visual)+.04
            if creator_frame:reasons.append('actual frame matches talking-head vlog more than requested action')
            opposite_action=action_counter.get(a['id']);wrong_action=opposite_action is not None and query_visual is not None and opposite_action>query_visual+.02
            wrong_participant=participant_counter.get(a['id']) is not None and query_visual is not None and participant_counter[a['id']]>query_visual+.02
            if wrong_participant:reasons.append('vehicles or empty scene match frames better than requested people')
            if wrong_action:reasons.append('opposite action matches actual frames better')
            if contradiction:reasons.append('contradictory condition evidence')
            if missing and visual is None:reasons.append('condition unverified without visual ranker')
            if generic:reasons.append('generic creator/vlog penalty')
            if prop_mismatches:reasons.append('unsupported generic visual: '+', '.join(prop_mismatches))
            negative_score=negative_counter.get(a['id']);negative_conflict=negative_score is not None and positive_visual is not None and (negative_score>float(positive_visual)+.02 or (bool(prop_mismatches) and negative_score>=float(positive_visual)-.03))
            if negative_conflict:reasons.append('negative visual evidence matches better than editorial target')
            unsupported_demoted=bool(spec.get('generic_shot_demoted')) and bool(prop_mismatches)
            if unsupported_demoted:reasons.append('generic shot was demoted because spoken context does not support it')
            weak_visual=visual is not None and float(visual)<.43
            if weak_visual:reasons.append('visual evidence below relevance floor')
            reject=wrong_participant or wrong_action or contradiction or creator_frame or nonphoto or negative_conflict or unsupported_demoted or weak_visual or score<.40 or (visual is None and (bool(missing) or meta<.60 or bool(prop_mismatches)))
            if score<.40:reasons.append('below relevance floor')
            if reject:score=min(score,.29)
            state='rejected' if reject else ('accepted' if float(visual)>=.60 else 'needs_review') if visual is not None else 'metadata_only'
            if state=='needs_review':reasons.append('borderline visual relevance; inspect candidate')
            output.append({**a,'score':round(max(0,score),4),'embedding_score':visual,'metadata_score':round(meta,4),'shot_embedding_score':positive_visual,'query_embedding_score':query_visual,'negative_embedding_score':negative_score,'visual_target':positive_intent,'editorial_positive':editorial_intent,'editorial_negatives':negatives,'quality_state':state,'condition_counter_score':opposite,'action_counter_score':opposite_action,'quality_reasons':reasons,'rank_reason':'Qwen concrete shot target + query + hard negatives' if visual is not None else 'Metadata only; visual relevance needs review','ranking_warning':self.warning,'matched_query':a.get('query') or a.get('matched_query')})
        return sorted(output,key=lambda r:-r['score'])
