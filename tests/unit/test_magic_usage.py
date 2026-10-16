import pytest
import httpx
from tests.unit.test_cut_pass_routes import tmp_path


def test_successful_provider_reply_is_cached_and_budget_stops_new_calls(tmp_path):
    from backend.app.magic_usage import provider_scope, invoke_http
    from backend.app.magic_store import MagicStore
    from backend.app.magic_models import MagicOptions
    from backend.app.magic_services import MagicBudgetReached
    store=MagicStore(tmp_path); row=store.create_or_resume('p','s',MagicOptions(max_cloud_requests=1))
    calls=[]
    def request():
        calls.append(True)
        return httpx.Response(200,json={'answer':42},request=httpx.Request('POST','https://example.invalid'))
    with provider_scope(store,row['run_id'],'editorial',lambda:None):
        assert invoke_http('groq',{'prompt':'one'},request).json()=={'answer':42}
        assert invoke_http('groq',{'prompt':'one'},request).json()=={'answer':42}
        with pytest.raises(MagicBudgetReached):invoke_http('groq',{'prompt':'two'},request)
    assert len(calls)==1


def test_timeout_is_unknown_and_not_automatically_retried(tmp_path):
    from backend.app.magic_usage import provider_scope, invoke_http
    from backend.app.magic_store import MagicStore
    from backend.app.magic_models import MagicOptions
    from backend.app.magic_services import MagicWaitingInput
    store=MagicStore(tmp_path); row=store.create_or_resume('p','s',MagicOptions())
    def request(): raise httpx.ReadTimeout('timeout')
    with provider_scope(store,row['run_id'],'cut',lambda:None):
        with pytest.raises(MagicWaitingInput):invoke_http('groq',{'prompt':'one'},request)
    assert store.recover(row['run_id'])['status']=='waiting_input'


def test_existing_groq_client_is_accounted_without_recording_api_key(tmp_path):
    from backend.app.groq_api import GroqDirectorClient
    from backend.app.magic_usage import provider_scope
    from backend.app.magic_store import MagicStore
    from backend.app.magic_models import MagicOptions
    class HTTP:
        def post(self,*args,**kwargs):
            return httpx.Response(200,json={'ok':True},request=httpx.Request('POST','https://example.invalid'))
    store=MagicStore(tmp_path); row=store.create_or_resume('p','s',MagicOptions())
    client=GroqDirectorClient('private-key-must-not-be-saved',http_client=HTTP())
    with provider_scope(store,row['run_id'],'cut',lambda:None):
        assert client._post({'model':'test'},{'Authorization':'Bearer private-key-must-not-be-saved'}).json()['ok']
    calls=store.read(row['run_id'])['calls']
    assert len(calls)==1
    assert 'private-key-must-not-be-saved' not in str(calls)
