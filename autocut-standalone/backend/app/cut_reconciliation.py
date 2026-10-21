"""Reconcile a confirmed CUT revision against reviewed editorial choices."""
from copy import deepcopy
from pathlib import Path
import json
import re
import shutil
from .atomic_io import write_json
from .editorial_import import read, digest, transcript_package, import_plan, active_retrieval_root
from .transcript_intents import load_phrase_intents, planning_chunks_for_coverage, WORD_FIELDS


def word_key(w):
    return (int(w['index']), str(w['text']).strip())


def _words(run):
    return [w for s in read(run/'transcript-raw.json')['segments'] for w in s.get('words',[])]


def rebase_magic_placements(retrieval,plan,allowed=None):
    from .magic_store import fingerprint
    path=retrieval/'magic-coverage.json'
    if not path.is_file():return
    document=read(path);fps=float(document.get('fps') or 30)
    beats={b['id']:b for b in plan['visual_beats']}
    kept=[]
    for decision in document.get('decisions',[]):
        bid=decision['beat_id']
        if bid not in beats or (allowed is not None and bid not in allowed):continue
        beat=beats[bid]
        start=round(beat['start']*fps)
        duration=min(round(beat['end']*fps)-start,decision['source_out_frame']-decision.get('source_in_frame',0),decision['edited_out_frame']-decision['edited_in_frame'])
        if duration<=0:continue
        kept.append({**decision,'edited_in_frame':start,'edited_out_frame':start+duration,
                     'source_out_frame':decision.get('source_in_frame',0)+duration})
    document.update(plan_signature=fingerprint(plan),decisions=kept)
    write_json(path,document)


def contiguous_parts(words,positions):
    parts=[]
    for w in words:
        if parts and positions[word_key(w)]==positions[word_key(parts[-1][-1])]+1:parts[-1].append(w)
        else:parts.append([w])
    return parts


def reconcile_cut(previous, target, *, project_id, duration):
    """Copy only reviewed assets that still describe precisely the same words.

    Original word IDs survive CUT rendering. No timeline seconds are used to
    identify a phrase: edited timing can change independently of its meaning.
    """
    previous,target=Path(previous),Path(target)
    old_chunks=read(previous/'semantic-chunks.json')
    old_intents=load_phrase_intents(previous)
    old_planning=planning_chunks_for_coverage(previous)
    old_plan=read(previous/'visual-plan.json') if (previous/'visual-plan.json').is_file() else None
    old_root=active_retrieval_root(previous)
    new_words=_words(target)
    positions={word_key(w):i for i,w in enumerate(new_words)}
    by_key={word_key(w):w for w in new_words}
    # A take replacement may use different source IDs while saying exactly the
    # same complete phrase. Reuse only a unique verbatim match, never a fuzzy
    # semantic guess (negations and different subjects must be re-reviewed).
    normalized=lambda text:re.sub(r'[^\w]','',str(text).casefold())
    tokens=[normalized(w['text']) for w in new_words]
    matched_keys={word_key(w) for c in old_chunks for w in c.get('words',[]) if word_key(w) in by_key}
    for old in old_chunks:
        original=old.get('words',[])
        if len(original)<4 or any(word_key(w) in by_key for w in original):continue
        phrase=[normalized(w['text']) for w in original]
        matches=[i for i in range(len(tokens)-len(phrase)+1) if tokens[i:i+len(phrase)]==phrase and not any(word_key(w) in matched_keys for w in new_words[i:i+len(phrase)])]
        if len(matches)==1:
            replacement=new_words[matches[0]:matches[0]+len(phrase)]
            for a,b in zip(original,replacement):by_key[word_key(a)]=b
            matched_keys.update(word_key(w) for w in replacement)
    used=set(); mappings={}; chunks=[]; intents={}
    for old in old_chunks:
        kept=[by_key[word_key(w)] for w in old.get('words',[]) if word_key(w) in by_key]
        if not kept: continue
        used.update(word_key(w) for w in kept)
        parts=contiguous_parts(kept,positions)
        for part_index,part in enumerate(parts):
            cid=old['id'] if part_index==0 else old['id']+'_cutpart_'+str(part_index)
            chunk={**old,'id':cid,'words':deepcopy(part),'text':' '.join(w['text'] for w in part),
                   'start':part[0]['start'],'end':part[-1]['end'],'duration':part[-1]['end']-part[0]['start']}
            chunks.append(chunk)
            flags={}
            for intent,field in WORD_FIELDS.items():
                selected=set(old_intents['phrases'].get(old['id'],{}).get(field,[]))
                selected_keys={word_key(by_key[word_key(w)]) for j,w in enumerate(old.get('words',[])) if j in selected and word_key(w) in by_key}
                flags[field]=[i for i,w in enumerate(part) if word_key(w) in selected_keys]
                flags[intent]=bool(flags[field])
            intents[cid]=flags
    # Newly restored words are visible and explicitly queued for a new plan.
    pending=[]; added=[]
    for base in read(target/'semantic-chunks.json'):
        groups=[]
        for w in base.get('words',[]):
            if word_key(w) in used: continue
            if groups and groups[-1][-1]['index']+1==w['index']:groups[-1].append(w)
            else:groups.append([w])
        for words in groups:
            cid='cut_added_'+str(words[0]['index'])
            chunk={'id':cid,'words':words,'text':' '.join(w['text'] for w in words),
                   'start':words[0]['start'],'end':words[-1]['end']}
            chunks.append(chunk);added.append(cid)
            intents[cid]={k:bool(k=='coverage') for k in WORD_FIELDS}
            for intent,field in WORD_FIELDS.items():intents[cid][field]=list(range(len(words))) if intent=='coverage' else []
    chunks.sort(key=lambda c:c['start'])
    actual=[word_key(w) for c in chunks for w in c.get('words',[])]
    if actual!=[word_key(w) for w in new_words]:
        raise ValueError('Confronto CUT ambiguo: parole mancanti o duplicate. Il risultato precedente resta conservato.')
    write_json(target/'semantic-chunks.json',chunks)
    signature=digest([{'id':str(c['id']),'start':float(c['start']),'end':float(c['end']),'text':str(c['text'])} for c in chunks])
    write_json(target/'phrase-intents.json',{'schema_version':'rambla-phrase-intents-3','transcript_signature':signature,'phrases':intents})
    planning=[]; states={}; removed=[]
    for row in old_planning:
        original=row.get('words',[])
        words=[by_key[word_key(w)] for w in original if word_key(w) in by_key]
        if not words:removed.append(row['id']);continue
        parts=contiguous_parts(words,positions)
        for part_index,part in enumerate(parts):
            status='unchanged' if len(part)==len(original) else 'changed'
            if status=='unchanged' and (abs(part[0]['start']-row['start'])>.001 or abs(part[-1]['end']-row['end'])>.001):status='realigned'
            cid=row['id'] if part_index==0 else row['id']+'_cutpart_'+str(part_index)
            item={**row,'id':cid,'previous_planning_id':row['id'],'words':deepcopy(part),'text':' '.join(w['text'] for w in part),
                  'start':part[0]['start'],'end':part[-1]['end']}
            planning.append(item);states[cid]=status
    for chunk in chunks:
        if chunk['id'] in added:
            planning.append({**chunk,'coverage_selected':True})
            states[chunk['id']]='added'
    planning.sort(key=lambda c:c['start'])
    # A removed word can leave ASR timestamps touching; avoid invalid overlap.
    for a,b in zip(planning,planning[1:]):
        if a['end']>b['start']:a['end']=max(a['start']+.00001,b['start'])
    write_json(target/'coverage-timing-snapshot.json',{'transcript_signature':signature,'selection_digest':digest(intents),'chunks':planning})
    package=transcript_package(target,project_id,duration)
    beats=[];valid_beats=set(); rows=[]
    for i,c in enumerate(package['chunks']):
        old=next((b for b in (old_plan or {}).get('visual_beats',[]) if c.get('previous_planning_id',c['id']) in b['covered_chunk_ids']),None)
        status=states.get(c['id'],'added')
        valid=old is not None and status in {'unchanged','realigned'}
        # A very short cut cannot safely carry an unchanged coverage clip.
        short=c['end']-c['start']<.7 and bool(c.get('coverage_selected'))
        if short:valid=False;status='changed'
        bid=old['id'] if old and len(old['covered_chunk_ids'])==1 and '_cutpart_' not in c['id'] else 'cut_beat_'+str(i+1)
        if valid and old['action']=='BROLL':
            beat=deepcopy(old);valid_beats.add(bid)
        else:
            selected=bool(c.get('coverage_selected'))
            beat={'id':bid,'action':'BROLL' if selected else 'KEEP_TALKING_HEAD',
                  'editorial_function':'Da aggiornare dopo modifica CUT' if selected else 'Parlato conservato',
                  'core_meaning':c['text'],'subtext':'','visual_mode':'single','avoid':[],
                  'shots':[{'shot_id':bid+'_shot_01','description':c['text'],
                            'image_queries':['editorial coverage'],'video_queries':['editorial coverage']}] if selected else []}
            if selected:pending.append(bid)
        beat.update(id=bid,covered_chunk_ids=[c['id']],original_text=c['text'],start=c['start'],end=c['end'])
        beat.pop('continuation_from',None)
        beats.append(beat)
        rows.append({'beat_id':bid,'chunk_id':c['id'],'status':status,'coverage_valid':bid in valid_beats,'text':c['text'],
                     'needs_update':bid in pending})
    plan={'schema_version':'rambla-visual-plan-1','project_id':project_id,
          'transcript_signature':package['transcript_signature'],'global_topic':(old_plan or {}).get('global_topic','Video aggiornato'),
          'visual_beats':beats}
    new_root=import_plan(target,plan,package)
    # JSON retrieval artifacts reference immutable local media paths. Retain
    # those references instead of duplicating downloads or provider calls.
    retained_selections={}
    if old_root!=previous:
        for path in old_root.glob('*.json'):
            if path.name not in {'selection-plan.json','imported-plan.json'}:shutil.copy2(path,new_root/path.name)
        selection=read(old_root/'selection-plan.json') if (old_root/'selection-plan.json').is_file() else {'chunks':{}}
        selection['chunks']={bid:v for bid,v in selection.get('chunks',{}).items() if bid in valid_beats}
        retained_selections=selection['chunks']
        write_json(new_root/'selection-plan.json',selection)
    rebase_magic_placements(new_root,plan,valid_beats)
    for name in ['generic-coverage.json','envato-downloads.json']:
        if (previous/name).is_file():shutil.copy2(previous/name,target/name)
    report={'source_project_id':previous.parent.name,'project_id':project_id,'status':'needs_update' if pending else 'ready',
            'pending_beat_ids':pending,'rows':rows,'removed_chunk_ids':removed,
            'counts':{key:sum(r['status']==key for r in rows) for key in ['unchanged','realigned','changed','added']},
            'preserved_coverages':sum(len(v.get('selected_assets',[])) for v in retained_selections.values()),'preserved_plan_beats':len(valid_beats),'needs_update':len(pending),'removed':len(removed)}
    write_json(target/'cut-reconciliation.json',report)
    return report


def update_changed_plan(run, project_id, duration, *, director=None):
    """Ask Director only for pending chunks, then merge with retained beats."""
    run=Path(run);report=read(run/'cut-reconciliation.json');pending=set(report.get('pending_beat_ids',[]))
    if not pending:return []
    plan=read(run/'visual-plan.json');old_root=active_retrieval_root(run)
    chunks=transcript_package(run,project_id,duration)['chunks']
    chunk_ids={cid for b in plan['visual_beats'] if b['id'] in pending for cid in b['covered_chunk_ids']}
    subset=[c for c in chunks if c['id'] in chunk_ids]
    work=run/'cut-revision-work';work.mkdir(exist_ok=True)
    for name in ['transcript-raw.json','analysis-signature.json']:
        shutil.copy2(run/name,work/name)
    write_json(work/'semantic-chunks.json',subset)
    subset_signature=digest([{'id':str(c['id']),'start':float(c['start']),'end':float(c['end']),'text':str(c['text'])} for c in subset])
    subset_intents={c['id']:{'coverage':True,'coverage_word_indices':list(range(len(c.get('words',[]))))} for c in subset}
    write_json(work/'phrase-intents.json',{'transcript_signature':subset_signature,'phrases':subset_intents})
    write_json(work/'coverage-timing-snapshot.json',{'transcript_signature':subset_signature,'selection_digest':digest(load_phrase_intents(work)['phrases']),'chunks':[{**c,'coverage_selected':True} for c in subset]})
    if director is None:
        from .api_first_director_cli import run_api_first_director
        director=run_api_first_director
    result=director(run_dir=work,project_id=project_id,duration=duration,activate=False,context_text=' '.join(w['text'] for w in _words(run)))
    generated=read(Path(result['visual_plan']))
    generated_beats=generated['visual_beats']; replacement={cid:b for b in generated_beats for cid in b['covered_chunk_ids']}
    used=set();merged=[];new_ids=[]
    for b in plan['visual_beats']:
        if b['id'] not in pending:merged.append(b);continue
        c=b['covered_chunk_ids'][0];new=deepcopy(replacement[c]);key=new['id']
        if key in used:continue
        used.add(key);new['id']='cut_updated_'+key
        if 'continuation_from' in new:new['continuation_from']='cut_updated_'+new['continuation_from']
        for shot in new['shots']:shot['shot_id']='cut_updated_'+shot['shot_id']
        merged.append(new)
        if new['action']=='BROLL':new_ids.append(new['id'])
    plan['visual_beats']=merged
    new_root=import_plan(run,plan,transcript_package(run,project_id,duration))
    for path in old_root.glob('*.json'):
        if path.name!='imported-plan.json':shutil.copy2(path,new_root/path.name)
    rebase_magic_placements(new_root,plan)
    report.update(status='research_required',pending_beat_ids=[],research_beat_ids=new_ids,needs_update=0)
    write_json(run/'cut-reconciliation.json',report)
    return new_ids
