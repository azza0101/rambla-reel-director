"""Topic-level landscape coverage suggestions, independent from GPU ranking."""
from __future__ import annotations

import re
from typing import Any, Iterable


_STOP={"the","and","with","this","that","from","about","della","delle","degli","questo","questa","sono","come","perché","anche","dentro"}


def derive_topic_queries(topic: str, transcript: str) -> list[str]:
    source=(topic or transcript or "").strip()
    words=[w for w in re.findall(r"[A-Za-zÀ-ÿ0-9]+",source) if len(w)>2 and w.casefold() not in _STOP]
    concrete=" ".join(words[:6]) or "documentary background"
    broad=" ".join(words[:2]) or concrete
    queries=[concrete,broad,f"{broad} landscape",f"{broad} documentary"]
    from .geographic_context import places_in
    places=places_in(source) or places_in(transcript)
    if places and re.search(r"\b(egitto|egizi\w*|thailandia|viaggio|polizia|storia|turistica)\b", source, re.I):
        queries=[f"{p} travel" for p in places]+[f"{p} landscape" for p in places]

    return list(dict.fromkeys(q for q in queries if q.strip()))


def merge_unique(groups: Iterable[Iterable[dict[str,Any]]], *, limit: int=12) -> dict[str,Any]:
    output=[]; seen=set()
    for group in groups:
        for row in group:
            key=str(row.get("provider_id") or row.get("source_page") or "")
            if not key or key in seen: continue
            seen.add(key); output.append(row)
            if len(output)>=limit: return {"items":output,"shortfall":0}
    return {"items":output,"shortfall":max(0,limit-len(output))}


def candidate_dict(row: Any) -> dict[str,Any]:
    return {name:getattr(row,name) for name in (
        "provider","provider_id","query","source_page","title","description","duration","width","height",
        "orientation","preview_url","selected_rendition_url","provider_rank")}
