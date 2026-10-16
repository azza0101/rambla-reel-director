import pytest
from tests.unit.test_cut_pass_routes import tmp_path


def test_automatic_word_selections_cover_all_chunks_and_limit_keyword_spans():
    from backend.app.magic_editorial import selection_changes
    chunks=[{'id':'c0','text':'la polizia turistica in Egitto'},{'id':'c1','text':'ciao sono Giulia'}]
    rows=[{'chunk_id':'c0','coverage_word_indices':[1,2,3,4],'highlighted_word_indices':[1,2]},
          {'chunk_id':'c1','coverage_word_indices':[],'highlighted_word_indices':[]}]
    changes=selection_changes(chunks,rows)
    assert changes['c0']['coverage_word_indices']==[1,2,3,4]
    assert changes['c1']['highlighted_word_indices']==[]
    with pytest.raises(ValueError):selection_changes(chunks,rows[:1])
    with pytest.raises(ValueError):selection_changes(chunks,[{**rows[0],'highlighted_word_indices':[0,1,2,3]},rows[1]])


def test_full_context_keeps_places_even_when_mentioned_in_middle_of_long_text():
    from backend.app.magic_editorial import editorial_context
    text=('introduzione '*600)+' polizia turistica in Egitto '+('conclusione '*600)
    context=editorial_context(text)
    assert 'Egypt' in context or 'Egitto' in context
    assert len(context)<2600


def test_full_editorial_uses_standard_intents_and_director_plan(tmp_path):
    import json
    from backend.app.magic_editorial import run_magic_editorial
    from backend.app.transcript_intents import load_phrase_intents
    chunks=[{'id':'c0','start':0,'end':3,'text':'la polizia turistica in Egitto'},
            {'id':'c1','start':3,'end':5,'text':'ciao sono Giulia'}]
    (tmp_path/'semantic-chunks.json').write_text(json.dumps(chunks))
    (tmp_path/'transcript-raw.json').write_text(json.dumps({'language':'it','segments':[]}))
    (tmp_path/'analysis-signature.json').write_text(json.dumps({'analysis_signature':'s'}))
    def query(prompt,schema,label):
        if 'choices' in schema['properties']:
            units=json.loads(prompt.split('UNITA=')[1])
            return {'global_topic':'Tourism in Egypt','choices':[dict(unit_id=u['unit_id'],
                coverage_word_indices=[0,1,2,3,4] if u['chunk_id']=='c0' else [],
                highlighted_word_indices=[1,2] if u['chunk_id']=='c0' else []) for u in units]}
        rows,_=json.JSONDecoder().raw_decode(prompt.split('TRANSCRIPT_CHUNKS=')[1])
        return {'global_topic':'Tourism in Egypt','beats':[dict(chunk_id=c['id'],
            action='BROLL' if c['id']=='c0' else 'KEEP_TALKING_HEAD',
            editorial_function='Show local tourist police' if c['id']=='c0' else 'Keep introduction',
            core_meaning=c['text'],subtext='',visual_mode='single',avoid=[],
            shots=[{'description':'tourist police Egypt','image_queries':['tourist police Egypt'],
                    'video_queries':['tourist police Egypt']}] if c['id']=='c0' else []) for c in rows]}
    result=run_magic_editorial(tmp_path,'p',5,lambda *args:None,query=query)
    assert result['coverage_count']==1
    assert load_phrase_intents(tmp_path)['phrases']['c0']['highlighted_word_indices']==[1,2]
    plan=json.loads((tmp_path/'visual-plan.json').read_text())
    assert [b['action'] for b in plan['visual_beats']]==['BROLL','KEEP_TALKING_HEAD']
