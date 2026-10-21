import base64,json
from types import SimpleNamespace
import httpx,pytest
from tests.unit.test_cut_pass_routes import tmp_path


def test_gateway_sends_image_boards_and_returns_structured_verdict():
    from backend.app.visual_gateway import FreeLLMVisualClient
    class HTTP:
        def post(self,url,**kw):
            body=kw['json']
            assert url=='http://127.0.0.1:8831/v1/chat/completions'
            assert body['messages'][0]['content'][1]['image_url']['url']=='data:image/jpeg;base64,abc'
            return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'verdicts':[]})}}]},headers={'x-routed-via':'groq/test'})
    client=FreeLLMVisualClient('secret',http_client=HTTP())
    result=client.generate_json('check',{'type':'object'},image_inputs=[{'mime_type':'image/jpeg','data':'abc'}])
    assert result.data=={'verdicts':[]} and result.model=='groq/test'


def test_gateway_refuses_more_than_three_boards_before_network():
    from backend.app.visual_gateway import FreeLLMVisualClient
    with pytest.raises(ValueError,match='tre'):
        FreeLLMVisualClient('secret').generate_json('check',{},image_inputs=[{}]*4)


def test_contact_sheet_keeps_three_real_samples_in_order(tmp_path):
    from PIL import Image
    from backend.app.magic_visual import contact_sheet
    frames=[]
    for n,color in enumerate(['red','green','blue']):
        p=tmp_path/f'{n}.jpg';Image.new('RGB',(80,60),color).save(p);frames.append(str(p))
    board=Image.open(contact_sheet(frames))
    assert board.width==1536
    assert board.getpixel((256,300))[0]>150
    assert board.getpixel((1280,300))[2]>150


def test_packed_judge_sends_one_board_per_candidate_and_keeps_temporal_evidence(tmp_path):
    from PIL import Image
    from backend.app.magic_visual import judge_batch
    frames=[]
    for n in range(3):
        p=tmp_path/f'{n}.jpg';Image.new('RGB',(80,60),'red').save(p);frames.append(str(p))
    class Client:
        contact_sheets=True
        def generate_json(self,prompt,schema,**kwargs):
            assert len(kwargs['image_inputs'])==1
            assert 'inizio' in prompt
            return SimpleNamespace(data={'verdicts':[{'asset_id':'a','coherent':True,'confidence':90,'reason':'Actual action matches'}]})
    assert judge_batch([dict(asset_id='a',kind='video',sampled_frames=frames,beat_text='camera')],Client())['a']['verdict']=='verified'


def test_invalid_or_rejected_gateway_reply_cannot_approve_a_clip(tmp_path):
    from PIL import Image
    from backend.app.magic_visual import judge_batch
    frames=[]
    for n in range(3):
        p=tmp_path/f'{n}.jpg';Image.new('RGB',(80,60),'red').save(p);frames.append(str(p))
    class Client:
        contact_sheets=True
        def generate_json(self,*a,**kw):
            return SimpleNamespace(data={'verdicts':[{'asset_id':'a','coherent':False,'confidence':99,'reason':'Subject does not match'}]})
    assert judge_batch([dict(asset_id='a',kind='video',sampled_frames=frames)],Client())['a']['verdict']=='rejected'


def test_gateway_factory_is_opt_in(monkeypatch):
    from backend.app.magic_product import configured_visual_client
    monkeypatch.setenv('RAMBLA_VISUAL_BACKEND','freellmapi')
    monkeypatch.setenv('RAMBLA_FREELLM_API_KEY','test-not-sent')
    assert configured_visual_client().max_candidates_per_batch==3


def test_small_visual_budget_covers_beginning_middle_and_end():
    from backend.app.magic_product import spread_visual_candidates
    rows=[{'asset_id':str(i),'chunk_id':str(i)} for i in range(7)]
    assert [r['asset_id'] for r in spread_visual_candidates(rows,3)]==['0','3','6']
    assert spread_visual_candidates(rows,0)==[]
