import pytest
from tests.unit.test_cut_pass import transcript
from backend.app.cut_pass import words_of,build_cut_plan,clean_transcript
from backend.app.cut_semantic import resolve_passages,_finalize_selection,propose_semantic_groups


def test_literal_passages_choose_latest_and_remove_directing(monkeypatch):
    import backend.app.cut_cloud as cloud
    raw=transcript([(0,2,"Ma tu l'hai mai fatta una foto?"),(3,5,"piu piano ripeti la frase"),(6,8,"Ma tu l'hai mai fatta una foto?"),(9,10,"Ciao sono Ada")])
    result=_finalize_selection(raw,{i for a,b in resolve_passages(words_of(raw),["Ma tu l'hai mai fatta una foto?",'Ciao sono Ada']) for i in range(a,b+1)})
    plan=build_cut_plan(raw,duration=11,fps=30,signature='s',**{k:result[k] for k in ('groups','discards')})
    assert clean_transcript(raw,plan)['text']=="Ma tu l'hai mai fatta una foto? Ciao sono Ada"
    assert plan['groups'] and plan['groups'][0]['selected_take']==1
    assert plan['groups'][0]['takes'][0]==[0,6]


def test_invented_or_reordered_text_is_rejected():
    words=words_of(transcript([(0,1,'prima frase'),(2,3,'seconda frase')]))
    with pytest.raises(ValueError,match='non trovata'):resolve_passages(words,['parole inventate'])
    with pytest.raises(ValueError,match='non trovata'):resolve_passages(words,['seconda frase','prima frase'])


def test_unique_premise_and_later_corrected_predicate_remain():
    raw=transcript([(0,2,'trovarmi in paesi esotici'),(3,5,'mi aiutano a far credere che in molti'),(6,9,'Aiuta a farmi credere di avere liberta')])
    w=words_of(raw);ranges=resolve_passages(w,['trovarmi in paesi esotici','Aiuta a farmi credere di avere liberta'])
    result=_finalize_selection(raw,{i for a,b in ranges for i in range(a,b+1)})
    plan=build_cut_plan(raw,duration=10,fps=30,signature='s',**{k:result[k] for k in ('groups','discards')})
    assert clean_transcript(raw,plan)['text']=='trovarmi in paesi esotici Aiuta a farmi credere di avere liberta'


def test_semantically_reviewed_utterances_not_shrunk(monkeypatch):
    from backend.app.cut_pass_routes import choose_complete_takes
    import backend.app.cut_boundaries as boundaries
    def forbidden(*a):raise AssertionError('No fragment-level review')
    monkeypatch.setattr(boundaries,'review_take_boundaries',forbidden)
    groups=[{'takes':[[0,1],[2,3]],'selected_take':1,'semantic_reviewed':True}]
    assert choose_complete_takes(transcript([(0,1,'ciao mondo'),(2,3,'ciao mondo')]),groups)==groups


def test_editorial_stays_groq_with_gemini_key(monkeypatch):
    import backend.app.cut_cloud as cloud
    monkeypatch.setenv('GEMINI_API_KEY','test-not-real')
    calls=[]
    monkeypatch.setattr(cloud,'query_json',lambda *a,**k:calls.append(k) or {'kept_passages':[]})
    assert cloud.query_editorial_json('text',{},'review')=={'kept_passages':[]}
    assert len(calls)==1


def test_joined_passages_split_at_removed_restart_without_inventing_words():
    raw=transcript([(0,2,'Noi costruiamo viaggi con rispetto'),(3,4,'o almeno fare il possibile'),(5,8,'O almeno fare il possibile per tutti')])
    words=words_of(raw)
    ranges=resolve_passages(words,['Noi costruiamo viaggi con rispetto O almeno fare il possibile per tutti'])
    kept={i for a,b in ranges for i in range(a,b+1)}
    assert kept==set(range(5))|set(range(10,17))


def test_complete_block_decisions_keep_original_words(monkeypatch):
    import backend.app.cut_cloud as cloud
    raw=transcript([(0,1,'una frase'),(2,3,'regia ripeti'),(4,5,'una frase')])
    monkeypatch.setattr(cloud,'query_editorial_json',lambda *a,**k:{'keep_blocks':[2],'discard_blocks':[0,1],'trim_blocks':[]})
    result=propose_semantic_groups(raw)
    assert result['selected_word_indices']==[4,5]
    assert result['discards']


def test_missing_or_out_of_range_decisions_never_produce_a_cut(monkeypatch):
    import backend.app.cut_cloud as cloud
    raw=transcript([(0,1,'testo originale')])
    monkeypatch.setattr(cloud,'query_editorial_json',lambda *a,**k:{'keep_blocks':[],'discard_blocks':[],'trim_blocks':[]})
    with pytest.raises(ValueError,match='incompleta'):propose_semantic_groups(raw)
    monkeypatch.setattr(cloud,'query_editorial_json',lambda *a,**k:{'keep_blocks':[9],'discard_blocks':[],'trim_blocks':[]})
    with pytest.raises(ValueError,match='Blocchi'):propose_semantic_groups(raw)


def test_long_requests_are_divided_before_tpm_limit(monkeypatch):
    import json,re
    import backend.app.cut_cloud as cloud
    calls=[]
    def reply(prompt,schema,label,**kwargs):
        calls.append(prompt)
        assert kwargs['input_token_budget']+kwargs['max_output_tokens']<=7500
        indices=[int(line.split(':',1)[0]) for line in prompt.split('BLOCCHI:')[1].strip().splitlines()]
        return {'keep_blocks':indices,'discard_blocks':[],'trim_blocks':[]}
    monkeypatch.setattr(cloud,'query_editorial_json',reply)
    result=propose_semantic_groups(transcript([(0,600,' '.join(['parola']*2000))]))
    assert len(calls)>1 and len(result['selected_word_indices'])==2000


def test_mixed_asr_block_is_trimmed_using_source_words(monkeypatch):
    import backend.app.cut_cloud as cloud
    raw=transcript([(0,4,'una volta vai rifallo una volta corretta')])
    monkeypatch.setattr(cloud,'query_editorial_json',lambda *a,**k:{'keep_blocks':[],'discard_blocks':[],'trim_blocks':[{'block':0,'keep_text':['una volta corretta']}]})
    result=propose_semantic_groups(raw)
    assert result['selected_word_indices']==[4,5,6]
