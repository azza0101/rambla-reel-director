"""Retrieval-only constraints and relevance. Never infer a new editorial shot."""
import re

VERSION='retrieval-quality-4'
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
    return out[:max(len(queries),4)]


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
        self.warning=None

    def rank(self,intent,assets):
        measured={}
        if self.visual and assets:
            try: measured={r['id']:r for r in self.visual.rank(intent,assets)}
            except Exception as exc:
                self.warning='Visual ranker unavailable: '+type(exc).__name__
                self.visual=None
        output=[]
        for a in assets:
            meta,contradictions,missing,generic=metadata_quality(intent,a.get('description','')+' '+a.get('title',''))
            visual=measured.get(a['id'],{}).get('embedding_score')
            penalty=.18 if generic else 0
            score=(float(visual)*.85+meta*.15 if visual is not None else meta*.75)-penalty
            reasons=[]
            if contradictions: reasons.append('contradictory condition: '+', '.join(contradictions))
            if missing and (visual is None or float(visual)<.65): reasons.append('required condition not verified: '+', '.join(missing))
            if generic: reasons.append('generic creator/vlog penalty')
            weak_visual=visual is not None and float(visual)<.60
            if weak_visual:reasons.append('visual evidence below relevance floor')
            reject=bool(contradictions or (missing and (visual is None or float(visual)<.65))) or weak_visual or score<.48
            if score<.48:reasons.append('below relevance floor')
            if reject: score=min(score,.29)
            state='rejected' if reject else 'accepted' if visual is not None else 'metadata_only'
            output.append({**a,'score':round(max(0,score),4),'embedding_score':visual,'metadata_score':round(meta,4),
                'quality_state':state,'quality_reasons':reasons,'rank_reason':'Qwen visual + shot metadata' if visual is not None else 'Metadata only; visual relevance needs review',
                'ranking_warning':self.warning,'matched_query':a.get('query') or a.get('matched_query')})
        return sorted(output,key=lambda r:-r['score'])
