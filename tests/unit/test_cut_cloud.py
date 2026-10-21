from backend.app.cut_cloud import word_windows,pack_items,merge_suggestions,TokenWindow


def test_long_text_windows_keep_absolute_indices_and_overlap():
    words=[{'index':i,'text':'parola','start':i,'end':i+.5} for i in range(1200)]
    windows=word_windows(words)
    assert len(windows)>2
    assert {w['index'] for chunk in windows for w in chunk}==set(range(1200))
    assert set(w['index'] for w in windows[0]).intersection(w['index'] for w in windows[1])
    assert all(len(c)<=300 for c in windows)


def test_batches_are_bounded_and_do_not_lose_items():
    rows=[{'index':i,'text':'x'*500} for i in range(30)]
    batches=pack_items(rows,max_chars=2200,max_items=4)
    assert [r['index'] for batch in batches for r in batch]==list(range(30))
    assert all(len(b)<=4 for b in batches)


def test_overlapping_chunks_merge_shared_take_without_duplicate_discards():
    one={'groups':[{'takes':[[10,20],[40,50]],'confidence':.99,'reason':'r'}],'discards':[{'range':[1,3],'confidence':.9,'reason':'regia'}]}
    two={'groups':[{'takes':[[40,50],[70,80]],'confidence':.95,'reason':'r'}],'discards':[{'range':[1,3],'confidence':.9,'reason':'regia'}]}
    merged=merge_suggestions([one,two])
    assert merged['groups'][0]['takes']==[[10,20],[40,50],[70,80]]
    assert len(merged['discards'])==1


def test_minute_budget_requires_wait_between_large_requests():
    quota=TokenWindow(limit=7500)
    assert quota.wait_seconds(5000,0)==0
    quota.record(5000,0)
    assert quota.wait_seconds(3000,10)>=50
    assert quota.wait_seconds(3000,61)==0


def test_cut_requests_have_bounded_output_and_resume_from_cache(monkeypatch):
    import json,uuid
    from pathlib import Path
    from types import SimpleNamespace
    import backend.app.cut_cloud as cloud
    import backend.app.groq_api as groq
    calls=[]
    class FakeClient:
        def __init__(self,*args,**kwargs):calls.append(kwargs)
        def generate_json(self,prompt,schema):return SimpleNamespace(data={'groups':[]},usage={'total_tokens':100})
    monkeypatch.setattr(groq,'GroqDirectorClient',FakeClient)
    monkeypatch.setattr(cloud,'_QUOTA',TokenWindow())
    folder=Path('.test-tmp')/('cloud-'+uuid.uuid4().hex);folder.mkdir(parents=True)
    with cloud.cloud_context(folder,lambda message:None):
        first=cloud.query_json('test',{'type':'object'},'blocco 1/2')
        second=cloud.query_json('test',{'type':'object'},'blocco 1/2')
    assert first==second
    assert len(calls)==1
    assert calls[0]['max_output_tokens']==2600


def test_oversized_request_is_blocked_locally_before_network(monkeypatch):
    import pytest
    import backend.app.cut_cloud as cloud
    monkeypatch.setattr(cloud,'_QUOTA',TokenWindow())
    with pytest.raises(ValueError,match='Blocco CUT troppo grande'):
        cloud.query_json('x'*30000,{},'troppo grande')


def test_magic_can_bound_reasoning_without_changing_manual_defaults(monkeypatch):
    from types import SimpleNamespace
    import backend.app.cut_cloud as cloud
    import backend.app.groq_api as groq
    calls=[]
    class FakeClient:
        def __init__(self,*a,**kw):calls.append(kw)
        def generate_json(self,*a):return SimpleNamespace(data={'ok':True},usage={'total_tokens':10})
    monkeypatch.setattr(groq,'GroqDirectorClient',FakeClient)
    monkeypatch.setattr(cloud,'_QUOTA',TokenWindow())
    cloud.query_json('small',{'type':'object'},'magic',max_output_tokens=2600,thinking_level='low')
    assert calls[0]['thinking_level']=='low' and calls[0]['max_output_tokens']==2600


def test_truncated_json_retries_with_more_output_and_less_reasoning(monkeypatch):
    from types import SimpleNamespace
    import backend.app.cut_cloud as cloud
    import backend.app.groq_api as groq
    calls=[];messages=[]
    class Quota(TokenWindow):
        def wait_seconds(self,tokens,now):
            assert tokens<=self.limit
            return 0
    class Client:
        def __init__(self,*a,**kw):calls.append(kw)
        def generate_json(self,*a):
            if len(calls)==1:raise groq.GroqAPIError('Groq request failed (400): max completion tokens reached; output was truncated')
            return SimpleNamespace(data={'groups':[],'discards':[]},usage={'total_tokens':100})
    monkeypatch.setattr(groq,'GroqDirectorClient',Client);monkeypatch.setattr(cloud,'_QUOTA',Quota())
    result=cloud.query_json('test',{'type':'object'},'take')
    assert result=={'groups':[],'discards':[]}
    assert len(calls)==2
    assert calls[1]['max_output_tokens']>calls[0]['max_output_tokens']
    assert calls[1]['thinking_level']=='low'


def test_other_bad_requests_are_not_retried(monkeypatch):
    import pytest
    import backend.app.cut_cloud as cloud
    import backend.app.groq_api as groq
    calls=[]
    class Client:
        def __init__(self,*a,**kw):calls.append(kw)
        def generate_json(self,*a):raise groq.GroqAPIError('Groq request failed (400): invalid schema')
    monkeypatch.setattr(groq,'GroqDirectorClient',Client);monkeypatch.setattr(cloud,'_QUOTA',TokenWindow())
    with pytest.raises(groq.GroqAPIError):cloud.query_json('test',{},'take')
    assert len(calls)==1
