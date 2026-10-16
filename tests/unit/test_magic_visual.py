from tests.unit.test_cut_pass_routes import tmp_path


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
