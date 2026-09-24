"""Bounded retrieval wording variations; never rewrite the editorial plan."""
import re

def search_variants(queries,target,round_no=0,override=''):
    base=[re.sub(r'\s+',' ',q).strip() for q in queries if str(q).strip()]
    if override.strip():base=[override.strip()]
    if not base:return []
    round_no=max(0,min(3,int(round_no)))
    if round_no==0:return base[:2]
    if round_no==1 and len(base)>1:return (base[1:]+base[:1])[:2]
    suffix={1:'travel video',2:'travel vlog',3:'footage'}[round_no]
    if round_no==3 and re.search(r'\b(pov|riding|window|onboard|on board)\b',target,re.I) and not re.search(r'street level|exterior|outside',target,re.I):suffix='pov'
    return [' '.join(dict.fromkeys((q+' '+suffix).split())) for q in base[:2]]
