"""Listening cutaway over the original preceding dialogue audio."""
def listening_overlay(decision,previous,sources,fps,minimum,occupied=None):
    if not previous or previous.get('narrative_role')!='tension' or decision.get('narrative_role')!='resolution':return None
    if decision.get('manual') or previous.get('manual') or decision.get('reaction_enabled') is False:return None
    ranges=previous.get('source_ranges',[previous]);available=sum(r['end_frame']-r['start_frame'] for r in ranges)
    duration=max(round(2*fps),minimum);margin=max(1,round(.12*fps))
    if duration>min(available-round(.8*fps),round(3*fps)):return None
    from active_speaker import verify_listener
    candidates=sorted([decision,*decision.get('alternatives',[])],key=lambda r:r.get('score',0),reverse=True)
    for row in candidates:
        if row['media_id']==previous['media_id']:continue
        if row.get('shot_size') not in {'close','medium'} or row.get('speaker_coverage')=='absent':continue
        source=next((s for s in sources if s['media_id']==row['media_id'] and s.get('take_id')==row.get('take_id')),None)
        if not source:continue
        anchor=row.get('matched_start_frame',row['start_frame']);end=anchor-margin;start=end-duration
        if start<source.get('start_frame',0) or end>source.get('end_frame',source['duration_frames']):continue
        retained=[r for d in occupied or [] if d['media_id']==row['media_id'] for r in d.get('source_ranges',[d])]+[r for d in occupied or [] for r in d.get('action_after',[]) if r['media_id']==row['media_id']]
        if any(r['start_frame']<end and start<r['end_frame'] for r in retained):continue
        try:proof=verify_listener(source,start,end,anchor,row.get('matched_end_frame',row['end_frame']))
        except Exception:continue
        if not proof.get('verified'):continue
        return {'kind':'reaction','basis':'verified_listener','media_id':row['media_id'],'take_id':row['take_id'],'start_frame':start,'end_frame':end,'offset_frames':available-duration,'shot_size':row['shot_size'],'character':decision.get('dialogue_character',''),'speaker_coverage':'visible','enabled':True,'evidence':proof}
    return None
