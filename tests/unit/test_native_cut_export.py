import pytest
from backend.app.native_cut_export import validate_native_cut,native_cut_format
from tests.unit.test_cut_pass_routes import tmp_path


def test_format_keeps_orientation_and_rotation():
    assert native_cut_format(1920,1080)==(1920,1080)
    assert native_cut_format(1080,1920)==(1080,1920)
    assert native_cut_format(1920,1080,90)==(1080,1920)
    assert native_cut_format(1000,1000)==(1080,1080)


def test_native_map_must_be_contiguous_and_equal_source_duration():
    cut={'fps':'30000/1001','source_duration_frames':100,'duration_frames':40,'segments':[
        {'source_in_frame':10,'source_out_frame':30,'edited_in_frame':0,'edited_out_frame':20},
        {'source_in_frame':50,'source_out_frame':70,'edited_in_frame':20,'edited_out_frame':40}]}
    validate_native_cut(cut)
    cut['segments'][1]['edited_in_frame']=21
    with pytest.raises(ValueError):validate_native_cut(cut)


def test_frozen_child_uses_its_own_map_and_changed_original_is_rejected(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from backend.app.curation_project import ProjectStore
    import backend.app.native_cut_export as native
    root = tmp_path / 'projects'
    store = ProjectStore(root, probe_runner=lambda _: dict(duration=4, fps=30, width=1080, height=1920, has_audio=True))
    parent = store.create('parent')
    source = tmp_path / 'original.mp4'
    source.write_bytes(b'original')
    parent = store.register_local_video(parent.project_id, source)
    plan = {'fps': '30', 'source_signature': parent.analysis_signature,
            'source_duration_frames': 120, 'duration_frames': 20, 'revision': 'frozen',
            'segments': [{'source_in_frame': 10, 'source_out_frame': 30, 'edited_in_frame': 0, 'edited_out_frame': 20}]}
    folder = root / parent.project_id / 'cut'
    folder.mkdir()
    (folder / 'plan.json').write_text(json.dumps(plan))
    child = store.create('child')
    stat = source.stat()
    origin = dict(project_id=parent.project_id, plan=plan, source_path=str(source), source_signature=parent.source_video.signature,
                  source_identity={'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns})
    (root / child.project_id / 'cut-origin.json').write_text(json.dumps(origin))
    monkeypatch.setattr(native.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=json.dumps({'streams': [
        dict(width=1080, height=1920, r_frame_rate='30/1', avg_frame_rate='29999/1000')]})))
    (folder / 'plan.json').write_text(json.dumps({**plan, 'revision': 'later-parent'}))
    frozen = native.load_native_cut(root / child.project_id, root)
    assert frozen['revision'] == 'frozen'
    assert frozen['fps'] == '30'
    assert frozen['source_path'] == str(source.resolve())
    source.write_bytes(b'replaced-source')
    with pytest.raises(ValueError, match='cambiata'):
        native.load_native_cut(root / child.project_id, root)
    with pytest.raises(ValueError, match='cambiato'):
        native.load_native_cut(root / parent.project_id, root)


def test_cut_child_finds_parent_video_receipt_only_for_frozen_revision(tmp_path):
    import json
    from backend.app.native_cut_export import find_native_cut_receipt
    parent=tmp_path/'parent'; child=tmp_path/'child'; child.mkdir(); parent.mkdir()
    (child/'cut-origin.json').write_text(json.dumps({'project_id':'parent'}))
    out=parent/'resolve-outbox'/'sent'; out.mkdir(parents=True)
    cut={'revision':'frozen', 'source_identity':{'size':123,'mtime_ns':456}}
    receipt={'status':'completed','updated_at':'2026-10-14', 'result':{**cut,'cut_revision':'frozen','timeline_id':'existing-cut'}}
    (out/'package.json').write_text(json.dumps(receipt))
    assert find_native_cut_receipt(child,tmp_path,cut)['timeline_id']=='existing-cut'
    assert find_native_cut_receipt(child,tmp_path,{**cut,'revision':'changed'}) is None
    assert find_native_cut_receipt(child,tmp_path,{**cut,'source_identity':{'size':124}}) is None
