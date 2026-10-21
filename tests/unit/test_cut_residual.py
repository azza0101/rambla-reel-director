import pytest
from backend.app.cut_residual import merge_residual_suggestions
from backend.app.cut_pass import build_cut_plan,clean_transcript
from tests.unit.test_cut_pass import transcript


def test_partial_restart_keeps_unique_premise_and_only_good_predicate():
    raw=transcript([(0,3,'trovarmi in paesi esotici'),(4,7,'mi aiutano a far credere che in molti...'),(9,14,'Aiuta a farmi credere di avere più libertà')])
    plan=build_cut_plan(raw,duration=15,fps=30,signature='s',groups=[],excluded_word_indices=[0])
    new=merge_residual_suggestions(raw,plan,{'groups':[{'takes':[[4,11],[12,19]],'selected_take':1,'confidence':.99,'reason':'ripartenza parziale'}],'discards':[]})
    text=clean_transcript(raw,new)['text']
    assert text=='in paesi esotici Aiuta a farmi credere di avere più libertà'
    assert new['excluded_word_indices']==[0]
    assert new['duration_seconds']<plan['duration_seconds']


def test_residual_cannot_overwrite_existing_take_choices():
    raw=transcript([(0,2,'prima frase'),(3,5,'prima frase'),(6,8,'frase unica')])
    plan=build_cut_plan(raw,duration=9,fps=30,signature='s',groups=[{'takes':[[0,1],[2,3]],'selected_take':0,'confidence':.99}])
    new=merge_residual_suggestions(raw,plan,{'groups':[{'takes':[[0,1],[4,5]],'confidence':.99}],'discards':[]})
    assert new['groups'][0]['takes']==plan['groups'][0]['takes']
    assert new['groups'][0]['selected_take']==0
    assert 'frase unica' in clean_transcript(raw,new)['text']
    assert new['warnings']


def test_partial_restart_cannot_swallow_the_unique_subject():
    raw=transcript([(0,8,'trovarmi in paesi e culture esotiche mi aiutano a far credere che in molti...'),(10,15,'Aiuta a farmi credere di avere più libertà')])
    plan=build_cut_plan(raw,duration=16,fps=30,signature='s',groups=[])
    new=merge_residual_suggestions(raw,plan,{'groups':[{'takes':[[0,13],[14,21]],'selected_take':1,'confidence':.99,'reason':'r'}],'discards':[]})
    assert new['groups'][0]['takes'][0][0]==6
    assert clean_transcript(raw,new)['text'].startswith('trovarmi in paesi e culture esotiche Aiuta')


def test_short_question_repeats_are_hinted_even_when_modal_verb_changes():
    from backend.app.cut_residual import repetition_hints
    raw=transcript([(0,3,'e quindi non bisogna più scattare?'),(4,7,'e quindi non dobbiamo più scattare?'),(8,11,'e quindi non bisogna più scattare?'),(12,13,'No diciamo')])
    plan=build_cut_plan(raw,duration=14,fps=30,signature='s',groups=[])
    hints=repetition_hints(raw,plan)
    assert hints[0]['takes']==[[0,5],[6,11],[12,17]]
    assert all(b<18 for a,b in hints[0]['takes'])


def test_longer_first_pair_does_not_hide_the_third_question():
    from backend.app.cut_residual import repetition_hints
    raw=transcript([(0,3,'e quindi non bisogna più scattare no'),(4,7,'e quindi non dobbiamo più scattare no'),(8,11,'e quindi non bisogna più scattare?'),(12,13,'No diciamo')])
    plan=build_cut_plan(raw,duration=14,fps=30,signature='s',groups=[])
    assert any(h['takes']==[[0,5],[7,12],[14,19]] for h in repetition_hints(raw,plan))


def test_missing_last_question_and_regia_are_reconciled_without_cutting_answer():
    from backend.app.cut_residual import reconcile_question_takes
    raw=transcript([(0,3,'e quindi non bisogna più scattare no'),(4,5,'esatto sì sì'),(6,9,'e quindi non dobbiamo più scattare no'),(10,13,'e quindi non bisogna più scattare?'),(14,17,'No diciamo che possiamo')])
    plan=build_cut_plan(raw,duration=18,fps=30,signature='s',groups=[{'takes':[[0,6],[10,16]],'selected_take':1,'confidence':.99}])
    new=reconcile_question_takes(raw,plan)
    assert new['groups'][0]['takes']==[[0,5],[10,15],[17,22]]
    assert clean_transcript(raw,new)['text']=='e quindi non bisogna più scattare? No diciamo che possiamo'


def test_chunk_discard_overlap_is_clipped_while_manual_choices_are_protected():
    raw=transcript([(0,2,'prima frase'),(3,5,'prima frase'),(6,8,'regia estranea')])
    plan=build_cut_plan(raw,duration=9,fps=30,signature='s',groups=[{'takes':[[0,1],[2,3]],'selected_take':0,'confidence':.99}])
    suggestion={'groups':[],'discards':[{'range':[0,5],'confidence':.99,'reason':'r'}]}
    new=merge_residual_suggestions(raw,plan,suggestion)
    assert clean_transcript(raw,new)['text']=='prima frase'
    plan['groups'][0]['user_selected_take']=True
    protected=merge_residual_suggestions(raw,plan,suggestion)
    assert 'regia estranea' in clean_transcript(raw,protected)['text']


def test_residual_invalid_ai_take_index_preserves_every_word_without_crashing():
    raw=transcript([(0,2,'primo tentativo'),(3,5,'secondo tentativo'),(6,8,'frase buona')])
    plan=build_cut_plan(raw,duration=9,fps=30,signature='s',groups=[])
    proposal={'groups':[{'takes':[[0,1],[2,3]],'selected_take':99,
                          'confidence':.99,'reason':'modello ha sbagliato indice'}], 'discards':[]}
    new=merge_residual_suggestions(raw,plan,proposal)
    assert new['groups'][0]['selected_take']==-1
    assert clean_transcript(raw,new)['text']==clean_transcript(raw,plan)['text']
    assert any('Indice take residuale non valido' in w for w in new['warnings'])


def test_residual_invalid_non_integer_take_index_is_safe():
    raw=transcript([(0,2,'primo tentativo'),(3,5,'secondo tentativo')])
    plan=build_cut_plan(raw,duration=6,fps=30,signature='s',groups=[])
    proposal={'groups':[{'takes':[[0,1],[2,3]],'selected_take':'1',
                          'confidence':.99,'reason':'indice testuale'}], 'discards':[]}
    new=merge_residual_suggestions(raw,plan,proposal)
    assert new['groups'][0]['selected_take']==-1
    assert new['removed_word_indices']==[]
