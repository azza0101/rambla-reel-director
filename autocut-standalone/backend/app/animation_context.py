"""Short extractive context from the full approved plan. No inferred facts/model calls."""
import re
from collections import Counter


def build_animation_context(plan):
    plan=plan or {}
    theme=str(plan.get('global_topic') or '').strip()
    texts=[str(b.get('original_text') or b.get('text') or '').strip() for b in plan.get('visual_beats',[]) if isinstance(b,dict)]
    sentences=[s.strip() for text in texts for s in re.split(r'(?<=[.!?])\s+',text) if s.strip()]
    # Keep location-bearing speech as quoted context, not an inferred setting
    # applied indiscriminately to the entire video.
    place=re.compile(r'\b(?:[Ii]n|presso|near|dans)\s+(?:[A-ZÀ-Ý][a-zà-ÿ][\wÀ-ÿ-]*)',re.UNICODE)
    setting=[s for s in sentences if place.search(s)][:3]
    tokens=lambda text:set(re.findall(r'\b[\wÀ-ÿ]{5,}\b',text.lower()))
    frequency=Counter(t for sentence in sentences for t in tokens(sentence))
    theme_words=tokens(theme)
    scored=sorted(range(len(sentences)),key=lambda i: (-(sum(min(frequency[t],3) for t in tokens(sentences[i]))/max(1,len(tokens(sentences[i]))) - 2*len(tokens(sentences[i]) & theme_words)),i))
    indices=set()
    if sentences: indices.add(0)
    for sentence in setting[:1]: indices.add(sentences.index(sentence))
    for i in scored:
        if len(indices)>=3: break
        indices.add(i)
    excerpts=[sentences[i] for i in sorted(indices)]
    summary='. '.join(s.rstrip(' ,;:.!?') for s in ([theme] if theme else [])+excerpts)+('.' if excerpts or theme else '')
    if len(summary)>1000: summary=summary[:997].rsplit(' ',1)[0]+'…'
    return {'summary':summary,'theme':theme or None,'setting_excerpts':setting,
            'source':'editorial theme and transcript excerpts',
            'usage':'Use as general context only when the specific scene leaves details unspecified. Specific scene text takes precedence. Places in excerpts apply to the cited events, not necessarily every scene. Do not invent missing locations or turn questions into facts.'}
