from backend.app.highlight_phrases import highlight_ranges


def chunks(words):
    return [{'id':'a','words':[{'text':t,'start':s,'end':e} for t,s,e in words]}]


def test_selected_surname_expands_to_complete_name_and_uses_full_timing():
    rows=highlight_ranges(chunks([('sentivamo',0,.2),('National',.2,.5),('Geographic.',.5,1.2)]),{'a':{'highlighted_word_indices':[2]}})
    assert len(rows)==1 and rows[0]['text']=='National Geographic.'
    assert rows[0]['start_seconds']==.2 and rows[0]['end_seconds']>=1.2
    assert rows[0]['word_refs']==[('a',1),('a',2)]


def test_names_can_cross_chunks_but_not_a_sentence_or_long_pause():
    cs=[{'id':'a','words':[{'text':'Steve','start':0,'end':.3}]},{'id':'b','words':[{'text':'McCurry','start':.3,'end':.6}]}]
    assert highlight_ranges(cs,{'b':{'highlighted_word_indices':[0]}})[0]['text']=='Steve McCurry'
    cs[0]['words'][0]['text']='Steve.'
    assert highlight_ranges(cs,{'b':{'highlighted_word_indices':[0]}})[0]['text']=='McCurry'


def test_short_titles_gain_reading_time_without_overlapping_next_title_or_end():
    cs=chunks([('foto',0,.08),('altro',.08,.8),('viaggio',.8,.9),('fine',.9,2)])
    rows=highlight_ranges(cs,{'a':{'highlighted_word_indices':[0,2]}})
    assert rows[0]['end_seconds']-rows[0]['start_seconds']>=.65
    assert rows[0]['end_seconds']<=rows[1]['start_seconds']
    assert rows[1]['end_seconds']<=2


def test_common_sentence_starts_are_not_absorbed_as_names():
    rows=highlight_ranges(chunks([('Quando',0,.3),('Steve',.3,.6),('McCurry',.6,1)]),{'a':{'highlighted_word_indices':[2]}})
    assert rows[0]['text']=='Steve McCurry'


def test_compound_name_is_not_split_by_the_three_word_limit():
    rows=highlight_ranges(chunks([('bello',0,.2),('viaggio',.2,.4),('National',.4,.7),('Geographic',.7,1.2)]),{'a':{'highlighted_word_indices':[0,1,3]}})
    assert [r['text'] for r in rows]==['bello viaggio','National Geographic']


def test_magic_text_only_chunks_keep_and_complete_their_highlights():
    from backend.app.magic_editorial import selection_changes
    cs=[{'id':'a','text':'National Geographic','start':0,'end':1}]
    result=selection_changes(cs,[{'chunk_id':'a','coverage_word_indices':[],'highlighted_word_indices':[1]}])
    assert result['a']['highlighted_word_indices']==[0,1]
