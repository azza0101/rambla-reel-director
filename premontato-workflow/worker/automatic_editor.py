"""Small, conservative local editing policy; no names or external language model required."""
import re
from transcript_align import normalize
from shot_analyzer import speaker_coverage

def narrative_roles(beats, directions):
    roles={};tension=False
    enabled=directions.get('profile')=='VIDEO COLICHE';markers=directions.get('markers',{}) if enabled else {}
    for beat in beats:
        if beat.get('kind')!='dialogue':continue
        text=normalize(beat.get('text',''));marker=markers.get(beat['beat_id']);automatic=False
        if marker is None and enabled:
            invitation=bool(re.search(r'\b(dormire|dormi|dormiamo|letto|baciar|bacio|spoglia)',text) and re.search(r'\b(puoi|potete|vuoi|vieni|mio|con me|offro|offre)',text))
            refusal=bool(re.search(r'\b(no|rifiuto|rifiuta|non esiste|lascia perdere|non posso|non voglio)\b',text))
            if tension and refusal:marker='resolution';automatic=True
            elif invitation and not refusal:marker='tension';automatic=True
        if marker=='tension':tension=True
        elif marker in {'resolution','free'}:tension=False
        roles[beat['beat_id']]={'role':'resolution' if marker=='resolution' else 'tension' if tension else 'free','automatic':automatic}
    return roles

def evaluate_candidates(candidates,shots,beat,opening,role,stats,report):
    from active_speaker import analyze_candidate
    statuses={id(row):speaker_coverage(shots,row[2]['media_id'],row[4]['start_frame'],row[4]['end_frame'],beat.get('character','')) for row in candidates}
    evidence={}
    wide=[r for r in candidates if r[5] and r[5].get('shot_size')=='wide' and r[5].get('confidence',0)>=.55 and statuses[id(r)]!='absent']
    if ((opening or role=='resolution') and wide) or len(normalize(beat.get('text','')).split())<=2 or len({r[2]['media_id'] for r in candidates})<2:return statuses,evidence
    # Evaluate only useful tight views, newest matching occurrence first. A master is
    # context/fallback, not a reason to decode a second ASD sample of the same line.
    useful=sorted((r for r in candidates if statuses[id(r)]=='unknown' and r[5] and r[5].get('shot_size') in {'close','medium'} and r[5].get('confidence',0)>=.55),key=lambda r:(r[0],r[1],r[4]['start_frame']),reverse=True)
    seen=set()
    for row in useful:
        key=row[2]['media_id']
        if key in seen:continue
        seen.add(key)
        if stats.get('disabled'):break
        report(row,False)
        try:
            data=analyze_candidate(row[2],row[4]['start_frame'],row[4]['end_frame'])
            if data.get('status') not in {'visible','absent','unknown'}:raise ValueError('esito del parlante non valido')
            evidence[id(row)]=data;statuses[id(row)]=data['status'];stats['checked']+=1;stats['cache_hits']+=int(bool(data.get('cache_hit')))
        except Exception as error:
            stats['warnings'].append('Controllo parlante non disponibile: '+str(error));stats['disabled']=True
        report(row,True)
    return statuses,evidence

def choose_automatic_pool(credible,statuses,role,opening,recent):
    classified=[r for r in credible if r[5] and r[5].get('confidence',0)>=.55]
    wide=[r for r in classified if r[5].get('shot_size')=='wide' and statuses[id(r)]!='absent']
    tight=[r for r in classified if r[5].get('shot_size') in {'close','medium'} and statuses[id(r)]=='visible']
    if wide and (opening or role=='resolution'):return wide
    if tight:return [r for r in tight if r[5].get('shot_size')=='close'] or tight
    if wide:return wide
    known=[r for r in credible if statuses[id(r)]=='visible']
    return known or [r for r in credible if statuses[id(r)]=='unknown'] or credible
