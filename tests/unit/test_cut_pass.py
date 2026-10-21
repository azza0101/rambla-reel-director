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


def test_rejected_take_cannot_swallow_unique_following_passage():
    raw=transcript([(0,4,'Come mi sentirei con una foto in salotto'),
                    (5,15,'Come mi sentirei con una foto in salotto Noi creiamo itinerari con rispetto per le persone che incontriamo')])
    plan=build_cut_plan(raw,duration=16,fps=30,signature='s',groups=[
        {'takes':[[0,7],[8,25]],'selected_take':0,'confidence':.99}])
    clean=clean_transcript(raw,plan)['text']
    assert 'Noi creiamo itinerari con rispetto per le persone che incontriamo' in clean
    assert plan['protected_passages']


def test_unique_introduction_is_retained_outside_repeat_groups():
    raw=transcript([(0,2,'Domanda iniziale'),(3,5,'Domanda iniziale'),(6,10,'Ciao sono Giulia di Kura Viaggi')])
    plan=build_cut_plan(raw,duration=11,fps=30,signature='s',groups=[{'takes':[[0,1],[2,3]],'confidence':.99}])
    assert 'Ciao sono Giulia di Kura Viaggi' in clean_transcript(raw,plan)['text']



def test_manual_exclusion_is_reversible_and_updates_timing():
    from backend.app.cut_pass import review_words
    raw=transcript([(0,3,'foto Ciao sono Giulia'),(4,7,'saluto alternativo'),(8,11,'saluto alternativo')])
    groups=[{'takes':[[4,5],[6,7]],'confidence':.99}]
    base=build_cut_plan(raw,duration=12,fps=30,signature='s',groups=groups)
    edited=build_cut_plan(raw,duration=12,fps=30,signature='s',groups=groups,excluded_word_indices=[0,6,7])
    assert clean_transcript(raw,edited)['text']=='Ciao sono Giulia'
    assert edited['duration_frames']<base['duration_frames']
    visible=review_words(raw,edited)
    assert visible[0]['text']=='foto' and visible[0]['excluded']
    assert all(w['excluded'] for w in visible if w['index'] in [4,5])
    restored=build_cut_plan(raw,duration=12,fps=30,signature='s',groups=groups,excluded_word_indices=[])
    assert clean_transcript(raw,restored)['text']==clean_transcript(raw,base)['text']


def test_manual_exclusion_rejects_invalid_indices_and_empty_cut():
    raw=transcript([(0,2,'ciao Giulia')])
    with pytest.raises(ValueError,match='Parole escluse'):
        build_cut_plan(raw,duration=3,fps=30,signature='s',groups=[],excluded_word_indices=[-1])
    with pytest.raises(ValueError,match='almeno una parola'):
        build_cut_plan(raw,duration=3,fps=30,signature='s',groups=[],excluded_word_indices=[0,1])


def test_tight_pause_pass_changes_only_time_and_reverts_exactly():
    raw=transcript([(0,1,'Ciao Giulia'),(1.8,2.8,'parlo di viaggi'),(4,5,'con cura')])
    args=dict(duration=6,fps=30,signature='s',groups=[],excluded_word_indices=[1])
    normal=build_cut_plan(raw,**args)
    tight=build_cut_plan(raw,**args,tight_pauses=True)
    assert clean_transcript(raw,normal)['text']==clean_transcript(raw,tight)['text']
    assert tight['duration_frames']<normal['duration_frames']
    assert tight['pause_seconds_removed']>0
    assert tight['excluded_word_indices']==normal['excluded_word_indices']
    reverted=build_cut_plan(raw,**args,tight_pauses=False)
    assert reverted['segments']==normal['segments']
    assert reverted['revision']==normal['revision']



def test_review_words_keeps_automatic_discards_visible_and_struck():
    from backend.app.cut_pass import review_words
    transcript = {'segments':[{'words':[
        {'word':'regia','start':0,'end':.2}, {'word':'ciao','start':.3,'end':.5},
    ]}]}
    plan = {'automatic_removed_word_indices':[0], 'removed_word_indices':[0],
            'excluded_word_indices':[], 'groups':[]}
    rows = review_words(transcript, plan)
    assert [row['text'] for row in rows] == ['regia', 'ciao']
    assert rows[0]['automatic_removed'] and rows[0]['excluded']
    assert not rows[1]['excluded']


def test_manual_restore_overrides_automatic_removal_but_explicit_exclusion_wins():
    from backend.app.cut_pass import review_words
    raw=transcript([(0,2,'prima frase'),(3,5,'ultima frase')])
    kwargs=dict(duration=6,fps=30,signature='restore',groups=[{'takes':[[0,1],[2,3]],'selected_take':1,'confidence':.99}])
    plan=build_cut_plan(raw,**kwargs,restored_word_indices=[0,1])
    assert clean_transcript(raw,plan)['text']=='prima frase ultima frase'
    assert not review_words(raw,plan)[0]['excluded']
    excluded=build_cut_plan(raw,**kwargs,restored_word_indices=[0,1],excluded_word_indices=[0])
    assert review_words(raw,excluded)[0]['excluded']
