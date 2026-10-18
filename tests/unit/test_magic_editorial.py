import pytest
from tests.unit.test_cut_pass_routes import tmp_path


def test_director_batches_do_not_count_word_metadata():
    from backend.app.magic_editorial import compact_director_batches
    chunks = [dict(id=f'c{i}', start=i, end=i+1, text='polizia turistica in Egitto',
                   words=[dict(text='parola', metadata='x'*1000)]*100) for i in range(22)]
    batches = compact_director_batches(chunks)
    assert len(batches) == 4
    assert sum(map(len, batches)) == 22
    assert all(set(c) == {'id','start','end','text'} for batch in batches for c in batch)


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


def test_transition_only_words_never_become_magic_broll():
    from backend.app.magic_editorial import selection_changes
    chunks=[{'id':'c0','text':'Poi un giorno Rasit mi ha chiesto una lettera'}]
    rows=[{'chunk_id':'c0','coverage_word_indices':[0,1,2,3,4,5,6,7,8],
           'highlighted_word_indices':[]}]
    changes=selection_changes(chunks,rows)
    assert changes['c0']['coverage_word_indices']==[3,4,5,6,7,8]


def test_provider_index_outside_its_word_window_is_dropped_not_fatal():
    from backend.app.magic_editorial import _valid_window_indices
    valid, dropped = _valid_window_indices([3, 4, 80, '5'], range(0, 10))
    assert valid == [3, 4]
    assert dropped == 2


def test_director_schema_and_parser_accept_only_the_requested_batch():
    from backend.app.magic_editorial import _magic_director_schema, _requested_director_rows
    schema = _magic_director_schema(2)
    beats = schema['properties']['beats']
    assert 'minItems' not in beats and 'maxItems' not in beats
    batch = [{'id':'c1'},{'id':'c2'}]
    rows, extras = _requested_director_rows({'beats':[
        {'chunk_id':'outside'}, {'chunk_id':'c2'}, {'chunk_id':'c1'}]},batch)
    assert [row['chunk_id'] for row in rows] == ['c1','c2']
    assert extras == 1


def test_director_parser_keeps_broll_when_provider_appends_duplicate_talking_head():
    from backend.app.magic_editorial import _magic_director_schema, _requested_director_rows
    properties = _magic_director_schema(1)['properties']['beats']['items']['properties']
    actions = properties['action']['enum']
    assert actions == ['BROLL', 'KEEP_TALKING_HEAD']
    assert properties['visual_mode']['enum'] == ['single', 'sequence', 'juxtaposition']
    rows, extras = _requested_director_rows({'beats':[
        {'chunk_id':'c1','action':'BROLL'},
        {'chunk_id':'c1','action':'KEEP_TALKING_HEAD'},
    ]}, [{'id':'c1'}])
    assert rows == [{'chunk_id':'c1','action':'BROLL'}]
    assert extras == 1


def test_magic_decision_keeps_one_scene_and_two_queries():
    from backend.app.magic_editorial import _compact_magic_decision
    raw = {'visual_mode':'sequence','shots':[
        {'image_queries':['a','b','c'], 'video_queries':['d','e','f']},
        {'image_queries':['g'], 'video_queries':['h']},
    ]}
    decision, dropped = _compact_magic_decision(raw)
    assert decision['shots'] == [{'image_queries':['a','b'], 'video_queries':['d','e']}]
    assert decision['visual_mode'] == 'single'
    assert dropped == 3


def test_magic_replaces_an_invented_location_with_the_beat_context():
    from backend.app.magic_editorial import _geographically_safe_queries
    queries, repaired = _geographically_safe_queries(
        ['Changi airport immigration area'], ['Italy'], 'passport privilege and border control')
    assert repaired is True
    assert queries and 'Italy' in queries[0]
    assert 'Changi' not in queries[0]


def test_magic_removes_duplicate_queries_from_later_beats():
    from backend.app.magic_editorial import _deduplicate_plan_queries
    chunks = [{'id':'c1','text':'scrivere una lettera invito famiglia'},
              {'id':'c2','text':'ricevere una lettera invito viaggio'}]
    decisions = {chunk['id']:{'shots':[{'image_queries':['hand writing invitation letter'],
                                        'video_queries':['hand writing invitation letter']}]} for chunk in chunks}
    repaired = _deduplicate_plan_queries(decisions,chunks)
    assert repaired == 3
    queries = [query for decision in decisions.values() for shot in decision['shots']
               for field in ('image_queries','video_queries') for query in shot[field]]
    assert len(queries) == len(set(query.casefold() for query in queries))


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
        assert all(c['id']=='c0' for c in rows), 'Do not spend Director calls on already unselected talking-head chunks'
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


def test_empty_ai_selections_on_substantial_speech_are_not_published_as_success(tmp_path):
    import json
    from backend.app.magic_editorial import run_magic_editorial
    from backend.app.magic_services import MagicWaitingInput
    chunks=[{'id':'c','start':0,'end':30,'text':' '.join(['passaporto frontiere viaggio costo libertà']*10)}]
    (tmp_path/'semantic-chunks.json').write_text(json.dumps(chunks))
    (tmp_path/'transcript-raw.json').write_text(json.dumps({'language':'it','segments':[]}))
    def query(prompt,schema,label):
        units=json.loads(prompt.split('UNITA=')[1])
        return {'global_topic':'Travel','choices':[dict(unit_id=u['unit_id'],coverage_word_indices=[],highlighted_word_indices=[]) for u in units]}
    with pytest.raises(MagicWaitingInput):
        run_magic_editorial(tmp_path,'p',30,lambda *a:None,query=query)
    assert not (tmp_path/'visual-plan.json').exists()
