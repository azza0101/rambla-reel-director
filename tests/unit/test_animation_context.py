from backend.app.animation_context import build_animation_context

def test_context_uses_unselected_beats_and_explicit_place():
    plan={'global_topic':'Turismo responsabile e compromessi','visual_beats':[
      {'id':'a','original_text':'Parliamo dei compromessi del turismo.'},
      {'id':'b','original_text':'In Thailandia ho visitato un centro per elefanti.'},
      {'id':'c','original_text':'Ho chiesto chi fosse il proprietario.'}]}
    context=build_animation_context(plan)
    assert context['theme']==plan['global_topic']
    assert 'Thailandia' in str(context)
    assert context['source']=='editorial theme and transcript excerpts'
    assert 'specific scene' in context['usage']

def test_missing_location_is_not_invented():
    context=build_animation_context({'visual_beats':[{'original_text':'Mescola lentamente e spegni il fuoco.'}]})
    assert context['setting_excerpts']==[]
    assert 'Mescola' in context['summary']


def test_person_comparison_and_dm_are_not_settings():
    result=build_animation_context({'visual_beats':[{'original_text':'Mi sentivo a Greta Thunberg.'},{'original_text':'Scrivimi in DM.'}]})
    assert result['setting_excerpts']==[]
