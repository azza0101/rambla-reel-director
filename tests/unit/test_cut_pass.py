import pytest

from backend.app.cut_pass import build_cut_plan, clean_transcript


def transcript(rows):
    return {'timing_basis': 'cloud_asr_word_timestamps', 'segments': [
        {'text': text, 'start': start, 'end': end, 'words': [
            {'text': word, 'start': start+i*(end-start)/len(text.split()),
             'end': start+(i+1)*(end-start)/len(text.split())}
            for i, word in enumerate(text.split())]}
        for start, end, text in rows]}


def test_last_take_and_penultimate_use_original_frames():
    raw = transcript([(1,3,'Sono una guida'), (4,6,'Sono una guida'), (7,9,'Sono una guida turistica')])
    plan = build_cut_plan(raw, duration=11, fps=30, signature='s', groups=[
        {'takes': [[0,2],[3,5],[6,9]], 'reason':'ripartenza', 'confidence':.98}])
    assert plan['groups'][0]['selected_take'] == 2
    alt = plan['alternatives'][0]
    assert alt['source_in_frame'] == 120
    assert alt['source_out_frame'] == 180
    clean = clean_transcript(raw, plan)
    assert clean['text'] == 'Sono una guida turistica'
    assert clean['segments'][0]['words'][0]['source_start'] == 7
    assert clean['segments'][0]['words'][0]['start'] < 1


def test_intentional_repetition_and_final_words_survive():
    raw = transcript([(0,2,'molto molto bello'), (8,10,'fine del racconto')])
    plan = build_cut_plan(raw, duration=10.5, fps=29.97, signature='s', groups=[])
    assert clean_transcript(raw,plan)['text'] == 'molto molto bello fine del racconto'
    assert plan['fps'] == '2997/100'
    assert plan['duration_frames'] < plan['source_duration_frames']
    assert clean_transcript(raw,plan)['segments'][-1]['words'][-1]['end'] <= plan['duration_seconds']


def test_estimated_timing_and_overlapping_groups_are_rejected():
    raw = transcript([(0,2,'a b c d')])
    raw['timing_basis'] = 'estimated_segment_word_timing'
    with pytest.raises(ValueError,match='misurati'):
        build_cut_plan(raw,duration=3,fps=30,signature='s',groups=[])
    raw['timing_basis'] = 'cloud_asr_word_timestamps'
    with pytest.raises(ValueError):
        build_cut_plan(raw,duration=3,fps=30,signature='s',groups=[
            {'takes':[[0,1],[1,3]],'reason':'x','confidence':.9}])


def test_switch_take_recomputes_words_and_keeps_alternative_whole():
    raw=transcript([(1,3,'prima frase'),(4,7,'seconda frase completa')])
    groups=[{'takes':[[0,1],[2,4]],'reason':'ripresa','confidence':.95,'selected_take':0}]
    plan=build_cut_plan(raw,duration=8,fps=30,signature='s',groups=groups)
    assert clean_transcript(raw,plan)['text']=='prima frase'
    assert plan['alternatives'][0]['source_out_frame']-plan['alternatives'][0]['source_in_frame']==90


def test_out_of_scene_discards_can_be_restored():
    raw=transcript([(0,1,'fai ancora'),(3,5,'racconto utile')])
    discard={'range':[0,1],'reason':'regia','confidence':.95}
    plan=build_cut_plan(raw,duration=6,fps=30,signature='s',groups=[],discards=[discard])
    assert clean_transcript(raw,plan)['text']=='racconto utile'
    discard['keep']=True
    restored=build_cut_plan(raw,duration=6,fps=30,signature='s',groups=[],discards=[discard])
    assert clean_transcript(raw,restored)['text']=='fai ancora racconto utile'


def test_discard_cannot_override_an_accepted_take():
    from backend.app.cut_pass import prepare_suggestions
    groups,discards,warnings=prepare_suggestions({'groups':[{'takes':[[2,3],[5,6]]}],
        'discards':[{'range':[0,8],'confidence':.99,'reason':'fuori scena'}]})
    assert [d['range'] for d in discards]==[[0,1],[4,4],[7,8]]
    assert warnings


def test_word_touching_a_cut_boundary_is_not_lost_to_frame_rounding():
    raw=transcript([(0,1.013,'prima'),(1.013,1.8,'seconda')])
    plan=build_cut_plan(raw,duration=2,fps=30,signature='s',
        groups=[{'takes':[[0,0],[1,1]],'confidence':1,'reason':'ripresa'}])
    cleaned=clean_transcript(raw,plan)
    assert cleaned['text']=='seconda'
    assert 0<=cleaned['segments'][0]['start']<1/30
    assert plan['alternatives'][0]['edited_in_frame']==0


def test_last_valid_take_uses_previous_take_as_alternative_not_later_bad_fragment():
    raw=transcript([(1,2,'sono Giulia'),(3,4,'sono Giulia'),(5,6,'e oggi sono')])
    plan=build_cut_plan(raw,duration=7,fps=30,signature='s',groups=[{
        'takes':[[0,1],[2,3],[4,6]],'selected_take':1,'confidence':1,'reason':'ultima completa'}])
    assert clean_transcript(raw,plan)['text']=='sono Giulia'
    assert plan['alternatives'][0]['take_index']==0
