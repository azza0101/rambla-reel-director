from backend.app.cut_pass import words_of
from backend.app.cut_restart_reconcile import reconcile_selected_words
from tests.unit.test_cut_pass import transcript


def test_restores_complete_latest_question_prefix():
    raw=transcript([(0,4,'ma tu hai mai fatto una foto a quel ragazzo sulla spiaggia?'),(5,7,'no ripeti piu piano'),(8,12,'ma tu hai mai fatto una foto a quel ragazzo sulla spiaggia?')])
    w=words_of(raw);start=len(raw['segments'][0]['words'])+len(raw['segments'][1]['words'])
    result,groups=reconcile_selected_words(raw,set(range(start+3,len(w))))
    assert result==set(range(start,len(w)))
    assert groups and groups[0]['selected_take']==1


def test_nested_predicate_restart_is_not_reintroduced_by_broader_repeat():
    raw=transcript([(0,5,'Noi creiamo itinerari con cura o almeno fare il possibile per conoscere bene il posto.'),
        (6,10,'Noi creiamo itinerari con cura o almeno fare il possibile.'),
        (11,15,'O almeno fare il possibile per conoscere bene il posto.')])
    w=words_of(raw);n1=len(raw['segments'][0]['words']);n2=len(raw['segments'][1]['words'])
    result,_=reconcile_selected_words(raw,set(range(n1,len(w))))
    expected=set(range(n1,n1+5))|set(range(n1+n2,len(w)))
    assert result==expected


def test_ellipsis_predicate_false_start_keeps_unique_premise():
    raw=transcript([(0,3,'Essere in posti lontani'),(4,6,'mi aiutano a far credere che in molti...'),(7,11,'Aiuta a farmi credere di avere liberta')])
    w=words_of(raw);result,_=reconcile_selected_words(raw,set(range(len(w))))
    text=' '.join(x['text'] for x in w if x['index'] in result)
    assert text=='Essere in posti lontani Aiuta a farmi credere di avere liberta'


def test_standalone_final_approval_is_removed_without_clipping_closing():
    raw=transcript([(0,4,'Lo costruiamo insieme con cura'),(5,6,'bellissima')])
    result,_=reconcile_selected_words(raw,set(range(6)))
    assert result==set(range(5))


def test_repeated_wording_about_different_places_retains_unique_information():
    raw=transcript([(0,5,'Quando viaggio in Perù porto sempre una macchina fotografica piccola.'),
                    (6,11,'Quando viaggio in Canada porto sempre una macchina fotografica piccola.')])
    words=words_of(raw);result,_=reconcile_selected_words(raw,set(range(len(words))))
    assert result==set(range(len(words)))
