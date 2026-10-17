from types import SimpleNamespace
from backend.app.resolve_textplus_timeline import append_native_cut_titles
from tests.unit.test_cut_pass_routes import tmp_path


def test_empty_title_restores_exact_package_and_connects_output(tmp_path):
    from pathlib import Path
    from backend.app.resolve_textplus_timeline import restore_empty_title_composition
    state={'loaded':False}; links=[]; group=object()
    comp=SimpleNamespace(GetToolList=lambda *args: {},FindTool=lambda name:group,
        AddTool=lambda kind:SimpleNamespace(ConnectInput=lambda name,source:links.append((name,source)) or True))
    def import_comp(path):
        text=Path(path).read_text(encoding='utf-8')
        assert text.startswith('Composition {') and 'KURA_paper_title_v9' in text
        assert 'setting:/' not in text
        state['loaded']=True
        return True
    item=SimpleNamespace(GetFusionCompByIndex=lambda _:comp,ImportFusionComp=import_comp)
    restore_empty_title_composition(item,'KURA_paper_title_v9',{'media_staging_root':str(tmp_path)})
    assert state['loaded'] and links==[('Input',group)]
    assert not list(tmp_path.rglob('*.comp'))
    assert (tmp_path/'.title-comps'/'assets').is_dir()


def test_native_cut_titles_use_one_seed_composition_and_separate_exact_clips(monkeypatch):
    import backend.app.resolve_textplus_timeline as module
    calls = []
    seed = SimpleNamespace(GetStartFrame=lambda: 1000)
    title = SimpleNamespace(ExportFusionComp=lambda path, index: True)
    pool = SimpleNamespace(CreateEmptyTimeline=lambda name: seed, DeleteTimelines=lambda rows: calls.append(('delete', rows)) or True)
    project = SimpleNamespace(GetMediaPool=lambda: pool)
    target = SimpleNamespace(GetSetting=lambda: dict(timelineResolutionWidth='1080', timelineResolutionHeight='1920'))
    monkeypatch.setattr(module, 'activate_timeline', lambda *args: True)
    monkeypatch.setattr(module, 'restore_empty_title_composition', lambda *args: None)
    import backend.app.resolve_native_cut as native
    monkeypatch.setattr(native, 'configure_native_timeline', lambda *args: None)
    monkeypatch.setattr(module, 'insert_fusion_title_with_retry', lambda *args, **kwargs: calls.append(('seed',)) or title)
    monkeypatch.setattr(module, '_text_tool', lambda item: SimpleNamespace(GetInput=lambda *_: calls[-2][1]))
    monkeypatch.setattr(module, 'set_textplus_content', lambda item, text: calls.append(('text', text)))
    def append(pool, target, source_items, **kwargs):
        row = source_items[0]
        calls.append(('range', row.GetStart()-1000, row.GetEnd()-1000))
        return [SimpleNamespace()]
    monkeypatch.setattr(module, 'append_separate_fusion_titles', append)
    rows = append_native_cut_titles(object(), project, target,
        {'segments': [{'text':'uno','start_frame':30,'end_frame':60}, {'text':'due','start_frame':90,'end_frame':120}]},
        {'native_cut_fps':'30','media_staging_root':'.test-native-titles'}, title_name='KURA', track_index=4, base_frame=108000)
    assert len(rows) == 2
    assert calls.count(('seed',)) == 1
    assert ('range',30,60) in calls and ('range',90,120) in calls
    assert calls[-1] == ('delete',[seed])


def test_initialized_seed_is_never_replaced():
    from backend.app.resolve_textplus_timeline import restore_empty_title_composition
    comp=SimpleNamespace(GetToolList=lambda *a: {'Template':object()})
    item=SimpleNamespace(GetFusionCompByIndex=lambda _: comp)
    restore_empty_title_composition(item,'custom',{})


def test_original_video_with_audio_can_carry_separate_fusion_titles():
    from backend.app.resolve_textplus_timeline import find_title_carrier_media
    media = SimpleNamespace(GetClipProperty=lambda key: 'Video + Audio')
    item = SimpleNamespace(GetMediaPoolItem=lambda: media)
    timeline = SimpleNamespace(GetTrackCount=lambda _: 1, GetItemListInTrack=lambda *_: [item])
    assert find_title_carrier_media(timeline) is media
