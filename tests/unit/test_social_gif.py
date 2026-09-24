def test_samples_span_video_and_not_only_intro():
    from backend.app.social_gif import sample_times
    points=sample_times(100)
    assert len(points)==6
    assert points[0]==10 and points[-1]==90
    assert points==sorted(set(points))

def test_instructional_bus_and_vehicle_ferry_do_not_pass_physical_shot():
    from types import SimpleNamespace as S
    from backend.app.quality_video import _discovery_relevant
    def c(title,query):return S(title=title,description=title,query=query,provider='tiktok')
    assert not _discovery_relevant(c('How to take shuttle bus from city center to airport: tips','airport shuttle bus departing'),'A public bus or airport shuttle pulling away on a wet tarmac with travel bags visible')
    assert not _discovery_relevant(c('Smallest vehicle ferry crossing','small ferry crossing water'),'Small passenger ferry with people holding luggage on deck')
