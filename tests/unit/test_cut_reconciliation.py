import json
from pathlib import Path
from backend.app.atomic_io import write_json
from backend.app.cut_reconciliation import reconcile_cut,update_changed_plan
from backend.app.editorial_import import digest,transcript_package,import_plan,load_import,active_retrieval_root
from tests.unit.test_cut_pass_routes import tmp_path


def seed(run,words,chunks,project='old'):
    run.mkdir(parents=True)
    write_json(run/'transcript-raw.json',{'segments':[{'words':words,'text':' '.join(w['text'] for w in words)}]})
    write_json(run/'semantic-chunks.json',chunks)
    write_json(run/'analysis-signature.json',{'analysis_signature':'s'})


def chunk(cid,words):
    return {'id':cid,'words':words,'text':' '.join(w['text'] for w in words),'start':words[0]['start'],'end':words[-1]['end']}


def broll(row,bid):
    return {'id':bid,'covered_chunk_ids':[row['id']],'start':row['start'],'end':row['end'],'original_text':row['text'],
            'action':'BROLL','core_meaning':row['text'],'editorial_function':'Show subject','subtext':'','avoid':[],
            'visual_mode':'single','shots':[{'shot_id':bid+'_shot','description':'real subject','image_queries':['real subject'],'video_queries':['real subject']}]}


def fixture(tmp_path):
    old=tmp_path/'old'/'run';new=tmp_path/'new'/'run'
    words=[{'index':i,'text':f'word{i}','start':float(i),'end':float(i)+.8} for i in range(12)]
    chunks=[chunk('c'+str(i),words[i*4:i*4+4]) for i in range(3)]
    seed(old,words,chunks)
    signature=digest([{k:c[k] for k in ('id','start','end','text')} for c in chunks])
    phrases={c['id']:{'coverage':True,'coverage_word_indices':[0,1,2,3],'animation':False,'animation_word_indices':[],'highlight':True,'highlighted_word_indices':[1]} for c in chunks}
    write_json(old/'phrase-intents.json',{'transcript_signature':signature,'phrases':phrases})
    write_json(old/'coverage-timing-snapshot.json',{'transcript_signature':signature,'selection_digest':digest(phrases),'chunks':[{**c,'coverage_selected':True} for c in chunks]})
    package=transcript_package(old,'old',12)
    plan={'schema_version':'rambla-visual-plan-1','project_id':'old','transcript_signature':package['transcript_signature'],
          'global_topic':'topic','visual_beats':[broll(c,'b'+str(i)) for i,c in enumerate(package['chunks'])]}
    retrieval=import_plan(old,plan,package)
    write_json(retrieval/'selection-plan.json',{'chunks':{b['id']:{'selected_assets':[{'asset_id':b['id']+'--pexels:1','order':0}]} for b in plan['visual_beats']}})
    write_json(retrieval/'online-candidates.json',[])
    kept=[{**w,'start':i*.9,'end':i*.9+.8} for i,w in enumerate(words[:4]+words[5:8])]
    added=[{'index':99+i,'text':'added'+str(i),'start':6.3+i,'end':7.1+i} for i in range(2)]
    seed(new,kept+added,[chunk('base',kept+added)],project='new')
    return old,new


def test_cut_reconciliation_preserves_only_matching_choices_and_retimes(tmp_path):
    old,new=fixture(tmp_path)
    before=(old/'visual-plan.json').read_bytes()
    report=reconcile_cut(old,new,project_id='new',duration=9)
    assert report['preserved_coverages']==1
    assert report['removed']==1
    assert report['needs_update']==2
    selections=json.loads((active_retrieval_root(new)/'selection-plan.json').read_text())['chunks']
    assert list(selections)==['b0']
    assert selections['b0']['selected_assets'][0]['asset_id']=='b0--pexels:1'
    plan=load_import(new)
    assert plan['visual_beats'][0]['end']==3.5
    assert (old/'visual-plan.json').read_bytes()==before


def test_incremental_director_sees_only_modified_chunks(tmp_path):
    old,new=fixture(tmp_path)
    report=reconcile_cut(old,new,project_id='new',duration=9)
    old_plan=load_import(new);retained=old_plan['visual_beats'][0]
    calls=[]
    def director(**kw):
        package=transcript_package(kw['run_dir'],'new',9)
        calls.append([c['id'] for c in package['chunks']])
        assert 'c0' not in calls[-1]
        plan={'schema_version':'rambla-visual-plan-1','project_id':'new','transcript_signature':package['transcript_signature'],
              'global_topic':'topic','visual_beats':[broll(c,'generated'+str(i)) for i,c in enumerate(package['chunks'])]}
        output=kw['run_dir']/'generated.json';write_json(output,plan)
        return {'visual_plan':str(output)}
    ids=update_changed_plan(new,'new',9,director=director)
    assert len(calls)==1 and len(calls[0])==2
    assert len(ids)==2
    assert load_import(new)['visual_beats'][0]==retained
    assert 'b0' in json.loads((active_retrieval_root(new)/'selection-plan.json').read_text())['chunks']


def test_restored_word_inside_retained_phrase_never_reorders_or_duplicates_text(tmp_path):
    old,new=fixture(tmp_path)
    raw=json.loads((new/'transcript-raw.json').read_text())
    words=raw['segments'][0]['words']
    words.insert(2,{'index':100,'text':'restored','start':0,'end':0})
    for i,w in enumerate(words):w.update(start=i*.9,end=i*.9+.8)
    write_json(new/'transcript-raw.json',{'segments':[{'words':words}]})
    write_json(new/'semantic-chunks.json',[chunk('base',words)])
    reconcile_cut(old,new,project_id='new',duration=11)
    output=json.loads((new/'semantic-chunks.json').read_text())
    assert [w['index'] for c in output for w in c['words']]==[w['index'] for w in words]
    load_import(new)
