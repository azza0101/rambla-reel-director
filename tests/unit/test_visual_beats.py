import copy
import json
import pytest

from backend.app.visual_beats import BeatPlanner, validate_narrative, validate_batch


CHUNKS = [{'id': 'c1', 'text': 'Take a train.'}, {'id': 'c2', 'text': 'That is the point.'}, {'id': 'c3', 'text': 'A distant garden.'}]


def narrative():
    return {'theme': 'Travel choices', 'constraints': [], 'visual_beats': [
        {'visual_beat_id': 'b1', 'covered_chunk_ids': ['c1'], 'visual_action': 'BROLL', 'editorial_meaning': 'Travel by train', 'continuity_from': None, 'sequence_quote': '', 'anchors': [{'anchor_id': 'a1', 'source_chunk_id': 'c1', 'quote': 'train', 'concept': 'train moving', 'status': 'AFFIRMED'}]},
        {'visual_beat_id': 'b2', 'covered_chunk_ids': ['c2'], 'visual_action': 'CONTINUE_PREVIOUS_VISUAL', 'editorial_meaning': 'Conclude the thought', 'continuity_from': 'b1', 'sequence_quote': '', 'anchors': []}]}


def batch():
    return {'plans': [{'visual_beat_id': 'b1', 'visual_action': 'BROLL', 'grounding_note': 'Train is explicitly stated.', 'shots': [{'shot_id': 's1', 'anchor_id': 'a1', 'description': 'A train moving.', 'image_queries': ['train moving', 'moving train'], 'video_queries': ['train moving', 'moving train']}], 'avoid': ['unrelated props']}]}


def test_two_pass_scope_and_no_global_nouns_in_shot_prompt():
    calls = []
    def generate(prompt):
        calls.append(prompt)
        return json.dumps(narrative() if len(calls) == 1 else batch())
    plan = BeatPlanner(generate=generate).plan(CHUNKS, {}, scope_chunk_ids=['c1', 'c2'])
    assert len(calls) == 2
    assert all('A distant garden.' not in prompt for prompt in calls)
    assert set(plan['chunks']) == {'c1', 'c2'}
    assert plan['chunks']['c2']['visual_action'] == 'CONTINUE_PREVIOUS_VISUAL'
    assert plan['chunks']['c2']['shots'] == []
    assert plan['model_call_count'] == 2


def test_anchor_from_neighbor_is_rejected():
    value = narrative()
    value['visual_beats'][0]['anchors'][0].update(source_chunk_id='c3', quote='garden')
    with pytest.raises(ValueError, match='own beat'):
        validate_narrative(value, CHUNKS, ['c1', 'c2'])


def test_duplicate_or_missing_chunk_coverage_is_rejected():
    value = narrative()
    value['visual_beats'][1]['covered_chunk_ids'] = ['c1']
    with pytest.raises(ValueError, match='coverage'):
        validate_narrative(value, CHUNKS, ['c1', 'c2'])


def test_missing_coverage_is_reported_before_incidental_field_repairs():
    value = narrative()
    value['visual_beats'] = [value['visual_beats'][0]]
    del value['visual_beats'][0]['continuity_from']
    with pytest.raises(ValueError, match='coverage'):
        validate_narrative(value, CHUNKS, ['c1','c2'])


def test_invented_prop_is_rejected_before_retrieval():
    value = batch()
    value['plans'][0]['shots'][0]['description'] = 'A train moving beside a basil plant.'
    with pytest.raises(ValueError, match='ungrounded vocabulary'):
        validate_batch(value, narrative()['visual_beats'][:1], [])


def test_multiple_shots_need_an_explicit_spoken_sequence():
    value = batch()
    value['plans'][0]['shots'].append(dict(value['plans'][0]['shots'][0], shot_id='s2'))
    with pytest.raises(ValueError, match='one primary'):
        validate_batch(value, narrative()['visual_beats'][:1], [])


def test_negated_concept_is_never_retrieved():
    beats = narrative()['visual_beats'][:1]
    beats[0]['anchors'][0]['concept'] = 'tourists riding elephants'
    value = batch()
    value['plans'][0]['shots'][0].update(description='Tourists riding elephants.', image_queries=['tourists riding elephants']*2, video_queries=['elephant riding tourists']*2)
    with pytest.raises(ValueError, match='negated'):
        validate_batch(value, beats, [{'forbidden_concepts': ['elephant riding']}])


def test_question_does_not_establish_exploitation():
    beats = narrative()['visual_beats'][:1]
    beats[0]['anchors'][0].update(status='QUESTION', concept='exploited worker')
    value = batch()
    value['plans'][0]['shots'][0].update(description='An exploited worker.', image_queries=['exploited worker']*2, video_queries=['exploited worker']*2)
    with pytest.raises(ValueError, match='unestablished'):
        validate_batch(value, beats, [])


def test_repetition_penalty_and_batch_memory():
    chunks = [{'id': 'c1', 'text': 'Take a train.'}, {'id': 'c2', 'text': 'Then a train.'}]
    n = narrative()
    second = copy.deepcopy(n['visual_beats'][0])
    second.update(visual_beat_id='b2', covered_chunk_ids=['c2'])
    second['anchors'][0]['source_chunk_id'] = 'c2'
    n['visual_beats'][1] = second
    calls = []
    def generate(prompt):
        calls.append(prompt)
        if len(calls) == 1: return json.dumps(n)
        b = batch()
        if len(calls) == 3: b['plans'][0]['visual_beat_id'] = 'b2'
        return json.dumps(b)
    plan = BeatPlanner(generate=generate, batch_size=1).plan(chunks, {})
    assert 'train moving' in calls[2]
    assert plan['visual_beats'][1]['repetition_penalty'] == 1
    assert plan['visual_beats'][1]['visual_action'] == 'CONTINUE_PREVIOUS_VISUAL'
    assert plan['visual_beats'][1]['shots'] == []


def test_minimal_keep_plan_never_invokes_shot_generation():
    value = narrative()
    for beat in value['visual_beats']:
        beat.update(visual_action='KEEP_TALKING_HEAD', continuity_from=None, anchors=[])
    calls = []
    result = BeatPlanner(generate=lambda p: calls.append(p) or json.dumps(value)).plan(CHUNKS[:2], {})
    assert len(calls) == 1 and not any(row['shots'] for row in result['chunks'].values())


def test_cache_reuses_complete_plan_and_new_schema_invalidates_old(tmp_path):
    from backend.app.visual_planner import load_or_create_visual_plan
    responses = iter([narrative(), batch()])
    first = load_or_create_visual_plan(CHUNKS, {}, tmp_path, generate=lambda _: json.dumps(next(responses)), scope_chunk_ids=['c1','c2'])
    again = load_or_create_visual_plan(CHUNKS, {}, tmp_path, generate=lambda _: pytest.fail('cache missed'), scope_chunk_ids=['c1','c2'])
    assert again == first
    first['input_signature'] = 'legacy-schema'
    (tmp_path/'visual-plan.json').write_text(json.dumps(first), encoding='utf-8')
    responses = iter([narrative(), batch()])
    refreshed = load_or_create_visual_plan(CHUNKS, {}, tmp_path, generate=lambda _: json.dumps(next(responses)), scope_chunk_ids=['c1','c2'])
    assert refreshed['input_signature'] != 'legacy-schema'


def test_visual_cannot_activate_before_its_source_chunk():
    n = narrative()
    n['visual_beats'] = [dict(n['visual_beats'][0], covered_chunk_ids=['c1', 'c2'])]
    n['visual_beats'][0]['anchors'][0].update(source_chunk_id='c2', quote='train')
    chunks = [{'id':'c1','text':'Let me explain.'}, {'id':'c2','text':'Take a train.'}]
    responses = iter([n, batch()])
    result = BeatPlanner(generate=lambda _: json.dumps(next(responses))).plan(chunks,{})
    assert result['chunks']['c1']['visual_action'] == 'KEEP_TALKING_HEAD'
    assert result['chunks']['c2']['shots'][0]['activation_chunk_id'] == 'c2'


def test_continuation_inside_grouped_beat_references_that_visual():
    n = narrative()
    n['visual_beats'] = [dict(n['visual_beats'][0], covered_chunk_ids=['c1','c2'])]
    responses = iter([n, batch()])
    result = BeatPlanner(generate=lambda _: json.dumps(next(responses))).plan(CHUNKS[:2],{})
    assert result['chunks']['c2']['visual_action'] == 'CONTINUE_PREVIOUS_VISUAL'
    assert result['chunks']['c2']['continuity_from'] == 'b1'


def test_non_broll_does_not_call_image_provider(tmp_path):
    from backend.app.debug_run_cli import discover_image_candidates
    class Source:
        async def search(self, *args, **kwargs): pytest.fail('provider called for KEEP')
    plan = {'chunks': {'c1': {'visual_action':'KEEP_TALKING_HEAD', 'core_meaning':'A transition', 'shots':[]}}}
    result = discover_image_candidates([CHUNKS[0]], tmp_path, sources=[Source()], visual_plan=plan)
    assert result['chunks']['c1']['status'] == 'not_requested'
    assert result['chunks']['c1']['candidates'] == []


def test_repeat_of_older_concept_does_not_continue_unrelated_recent_visual():
    n = narrative()
    base = n['visual_beats'][0]
    n['visual_beats'] = []
    chunks = []
    for i, concept in enumerate(['train moving','book reading','train moving'], 1):
        c = {'id':f'c{i}','text':concept}
        chunks.append(c)
        b = copy.deepcopy(base)
        b.update(visual_beat_id=f'b{i}',covered_chunk_ids=[c['id']])
        b['anchors'][0].update(source_chunk_id=c['id'], quote=concept, concept=concept)
        n['visual_beats'].append(b)
    calls = []
    def generate(prompt):
        calls.append(prompt)
        if len(calls) == 1: return json.dumps(n)
        plans = []
        for i,c in enumerate(chunks,1):
            p = batch()['plans'][0]
            p['visual_beat_id'] = f'b{i}'
            p['shots'][0].update(description=c['text'], image_queries=[c['text']]*2, video_queries=[c['text']]*2)
            plans.append(p)
        return json.dumps({'plans':plans})
    result = BeatPlanner(generate=generate).plan(chunks,{})
    assert result['visual_beats'][2]['visual_action'] == 'KEEP_TALKING_HEAD'
    assert result['visual_beats'][2]['continuity_from'] is None


def test_global_theme_cannot_collapse_many_chunks_into_one_beat():
    chunks = [{'id':f'c{i}', 'text':f'Speech {i}'} for i in range(1, 9)]
    n = narrative()
    n['visual_beats'] = [dict(n['visual_beats'][0], covered_chunk_ids=[c['id'] for c in chunks], visual_action='KEEP_TALKING_HEAD', anchors=[])]
    with pytest.raises(ValueError, match='at most 3'):
        validate_narrative(n, chunks, [c['id'] for c in chunks])


def test_keep_has_no_new_anchor_or_sequence():
    n = narrative()
    n['visual_beats'][0]['visual_action'] = 'KEEP_TALKING_HEAD'
    with pytest.raises(ValueError, match='no new anchors'):
        validate_narrative(n, CHUNKS, ['c1','c2'])


def test_omitting_negation_from_quote_does_not_make_action_affirmed():
    chunks = [{'id':'c1','text':'No bicycle riding is permitted.'}, CHUNKS[1]]
    n = narrative()
    n['visual_beats'][0]['anchors'][0].update(quote='bicycle riding', concept='people riding bicycles')
    with pytest.raises(ValueError, match='source negation'):
        validate_narrative(n, chunks, ['c1','c2'])
