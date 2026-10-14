import pytest
from backend.app.cut_boundaries import apply_boundary_review
from backend.app.cut_pass import build_cut_plan,clean_transcript,review_words
from tests.unit.test_cut_pass import transcript


def test_new_concept_is_outside_all_takes_and_survives_every_choice():
    raw=transcript([(0,4,'Come mi sentirei con una foto in salotto'),
                    (5,15,'Come mi sentirei con una foto in salotto Noi creiamo itinerari con rispetto per le persone che incontriamo')])
    groups=[{'takes':[[0,7],[8,25]],'confidence':.99,'selected_take':0}]
    decisions=[{'group':0,'take':0,'start':0,'end':7,'equivalent':True,'reason':'stessa frase'},
               {'group':0,'take':1,'start':8,'end':15,'equivalent':True,'reason':'Gli itinerari sono autonomi'}]
    reviewed=apply_boundary_review(raw,groups,decisions)
    assert reviewed[0]['takes']==[[0,7],[8,15]]
    for selected in (0,1,-2):
        plan=build_cut_plan(raw,duration=16,fps=30,signature='s',groups=[{**reviewed[0],'selected_take':selected}])
        assert 'Noi creiamo itinerari' in clean_transcript(raw,plan)['text']
        assert all('Noi creiamo' not in t for t in plan['groups'][0]['texts'])
        assert all(w['group_index'] is None for w in review_words(raw,plan) if w['index']>=16)


def test_non_equivalent_fragment_is_not_offered_as_an_alternative():
    raw=transcript([(0,2,'frase buona'),(3,4,'scattato scattato'),(5,7,'frase buona')])
    groups=[{'takes':[[0,1],[2,3],[4,5]],'confidence':.99,'selected_take':2}]
    decisions=[{'group':0,'take':i,'start':a,'end':b,'equivalent':i!=1,'reason':'confini'} for i,(a,b) in enumerate(groups[0]['takes'])]
    reviewed=apply_boundary_review(raw,groups,decisions)
    assert reviewed[0]['takes']==[[0,1],[4,5]]
    assert reviewed[0]['selected_take']==1


def test_review_cannot_expand_ranges_or_silently_omit_a_take():
    raw=transcript([(0,2,'prima frase'),(3,5,'prima frase')])
    groups=[{'takes':[[0,1],[2,3]],'confidence':.99}]
    with pytest.raises(ValueError,match='incompleta'):apply_boundary_review(raw,groups,[])
    decisions=[{'group':0,'take':i,'start':a,'end':b,'equivalent':True,'reason':'r'} for i,(a,b) in enumerate(groups[0]['takes'])]
    decisions[0]['end']=3
    with pytest.raises(ValueError,match='fuori intervallo'):apply_boundary_review(raw,groups,decisions)


def test_incomplete_take_does_not_split_the_completion_of_the_full_sentence():
    raw=transcript([(0,3,'vedo delle scene...'),(4,10,'vedo delle scene, a delle immagini impattanti che vorrei condividere')])
    groups=[{'takes':[[0,2],[3,12]],'confidence':.99}]
    decisions=[{'group':0,'take':0,'start':0,'end':2,'equivalent':True,'reason':'r'},
               {'group':0,'take':1,'start':3,'end':5,'equivalent':True,'reason':'prefisso comune'}]
    reviewed=apply_boundary_review(raw,groups,decisions)
    assert reviewed[0]['takes'][1]==[3,12]
