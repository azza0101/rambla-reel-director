from tests.unit.test_cut_pass_routes import tmp_path


def test_video_judge_samples_downloaded_video_instead_of_search_jpeg(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from pathlib import Path
    import backend.app.magic_visual as visual
    video=tmp_path/'full.mp4';video.write_bytes(b'video')
    poster=tmp_path/'poster.jpeg';poster.write_bytes(b'poster')
    def run(command,**kwargs):
        if command[0]=='ffprobe':return SimpleNamespace(stdout='{"format":{"duration":"8"}}')
        assert command[command.index('-i')+1]==str(video)
        Path(command[-1]).write_bytes(b'frame')
    monkeypatch.setattr(visual.subprocess,'run',run)
    result=visual.sample_candidate(dict(kind='video',local_asset_path=str(video),preview_path=str(poster)),tmp_path/'frames')
    assert len(result['sampled_frames'])==3


def test_empty_ffmpeg_output_is_not_a_valid_sample(tmp_path,monkeypatch):
    import pytest
    from types import SimpleNamespace
    import backend.app.magic_visual as visual
    source=tmp_path/'image.png';source.write_bytes(b'image')
    monkeypatch.setattr(visual.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0))
    with pytest.raises(ValueError,match='fotogramma'):
        visual.sample_candidate(dict(kind='image',local_asset_path=str(source)),tmp_path/'frames')


def test_missing_frames_do_not_crash_or_get_visual_approval(tmp_path):
    from backend.app.magic_visual import judge_batch
    class Client:
        def generate_json(self,*a,**k):raise AssertionError('No request for missing frames')
    row=dict(asset_id='missing',kind='video',sampled_frames=[str(tmp_path/f'{i}.jpg') for i in range(3)])
    assert judge_batch([row],Client())['missing']['verdict']=='uncertain'


def test_visual_judge_uses_actual_sample_images_and_exact_candidate_ids(tmp_path):
    from backend.app.magic_visual import judge_batch
    frames=[]
    for i in range(3):
        path=tmp_path/f'{i}.jpg';path.write_bytes(b'jpeg');frames.append(str(path))
    rows=[dict(asset_id='a',kind='video',sampled_frames=frames,beat_text='Egypt police')]
    class Client:
        def generate_json(self,prompt,schema,**kwargs):
            assert len(kwargs['image_inputs'])==3
            assert 'Egypt police' in prompt and 'a' in prompt
            assert 'image' in str(kwargs['image_inputs'])
            return type('Reply',(),{'data':{'verdicts':[dict(asset_id='a',coherent=True,confidence=90,reason='Egypt tourist police visible')]}})()
    assert judge_batch(rows,Client())['a']['verdict']=='verified'


def test_unavailable_visual_model_does_not_approve_candidates():
    from backend.app.magic_visual import judge_batch
    assert judge_batch([dict(asset_id='a',kind='video')],None)['a']['verdict']=='uncertain'
