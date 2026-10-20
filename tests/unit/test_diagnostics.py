import json
from pathlib import Path
import uuid
import pytest
from backend.app.diagnostics import Diagnostics

@pytest.fixture
def work():
    p=Path('.test-tmp')/('diagnostics-'+uuid.uuid4().hex)
    p.mkdir(parents=True)
    return p

class GitHub:
    def __init__(self,private=True,fail=False):
        self.calls=[];self.private=private;self.fail=fail
    def __call__(self,args,payload=None):
        self.calls.append((args,payload))
        if self.fail:raise RuntimeError('secret server response GROQ_API_KEY=bad')
        if args[0]=='repos/azza0101/rambla-reel-director':return {'private':self.private}
        if args[0]=='search/issues':return {'items':[]}
        if args[0].endswith('/issues'):return {'number':123,'html_url':'https://github.com/azza0101/rambla-reel-director/issues/123'}
        raise AssertionError(args)

def service(work,gh=None):
    return Diagnostics(work/'data',app_root=Path.cwd(),github=gh or GitHub(),version='v0120')

def test_report_excludes_raw_message_paths_keys_and_transcript(work):
    d=service(work)
    report=d.capture_exception(RuntimeError('GROQ_API_KEY=gsk_PRIVATE video C:/Users/PRIVATE/movie.mp4 transcript VERY_PRIVATE'),component='magic',phase='selection')
    text=json.dumps(report)
    for secret in ('gsk_PRIVATE','C:/Users','VERY_PRIVATE','GROQ_API_KEY','movie.mp4'):
        assert secret not in text
    assert report['component']=='magic'
    assert report['error_type']=='RuntimeError'
    assert report['version']=='v0120'

def test_off_by_default_never_calls_github(work):
    gh=GitHub();d=service(work,gh)
    d.capture_exception(ValueError('private'))
    assert d.flush()==0
    assert gh.calls==[]
    assert d.view()['pending_count']==1

def test_installation_id_persists_and_is_not_hostname(work):
    d=service(work);first=d.settings()['installation_id']
    assert str(uuid.UUID(first))==first
    assert service(work).settings()['installation_id']==first

def test_manual_send_private_issue_and_local_dedup(work):
    gh=GitHub();d=service(work,gh)
    d.capture_exception(ValueError('first'))
    assert d.flush(manual=True)==1
    d.capture_exception(ValueError('different private text'))
    assert d.flush(manual=True)==0
    assert len([r for r in gh.calls if r[1] is not None])==1
    assert d.view()['last_url'].endswith('/123')

def test_public_repository_blocks_all_report_uploads(work):
    gh=GitHub(private=False);d=service(work,gh)
    d.capture_exception(ValueError('private'))
    assert d.flush(manual=True)==0
    assert len(gh.calls)==1
    assert gh.calls[0][1] is None
    assert d.view()['delivery_state']=='private_repo_required'
    assert d.view()['pending_count']==1

def test_network_failure_keeps_queue_and_never_saves_stderr(work):
    gh=GitHub(fail=True);d=service(work,gh)
    d.capture_exception(RuntimeError('private'))
    assert d.flush(manual=True)==0
    assert d.view()['pending_count']==1
    for p in (work/'data').rglob('*.json'):
        assert 'GROQ_API_KEY' not in p.read_text()

def test_auto_enabled_sends_and_reuses_existing_issue(work):
    gh=GitHub();d=service(work,gh)
    d.set_automatic(True,start_worker=False)
    d.capture_exception(TimeoutError('provider request private'))
    assert d.flush()==1
    assert d.settings()['choice_made']

def test_untrusted_component_and_phase_are_replaced(work):
    report=service(work).capture_exception(ValueError('secret'),component='my secret client',phase='private transcript')
    assert report['component']=='app'
    assert report['phase']=='unknown'


def test_submit_already_sent_does_not_leave_sending_state(work):
    d=service(work)
    d.capture_exception(ValueError('private'))
    assert d.flush(manual=True)==1
    assert d.submit_async()['delivery_state']=='sent'

def test_tampered_spool_never_sends_extra_fields(work):
    gh=GitHub();d=service(work,gh)
    report=d.capture_exception(ValueError('private'))
    path=work/'data/reports'/(report['fingerprint']+'.json')
    row=json.loads(path.read_text());row['report']['transcript']='PRIVATE'
    path.write_text(json.dumps(row))
    assert d.flush(manual=True)==0
    assert not any(call[1] is not None for call in gh.calls)

def test_unknown_dynamic_exception_name_is_not_sent(work):
    secret_type=type('gsk_PRIVATE_TOKEN',(Exception,),{})
    assert service(work).capture_exception(secret_type('text'))['error_type']=='Exception'


def test_report_quota_prevents_bug_flood(work):
    from datetime import datetime,timezone
    gh=GitHub();d=service(work,gh)
    d.capture_exception(ValueError('private'))
    (work/'data/budget.json').write_text(json.dumps({'day':datetime.now(timezone.utc).date().isoformat(),'count':10}))
    assert d.flush(manual=True)==0
    assert gh.calls==[]
    assert d.view()['delivery_state']=='daily_limit'

def test_old_policy_does_not_silently_enable_uploads(work):
    root=work/'data';root.mkdir()
    (root/'settings.json').write_text(json.dumps({'automatic':True,'choice_made':True,'policy_version':0}))
    d=service(work)
    assert not d.settings()['automatic']
    assert not d.settings()['choice_made']

def test_routes_require_local_custom_header_and_valid_consent(work):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.app.diagnostics_routes import install_diagnostics_routes
    app=FastAPI();d=install_diagnostics_routes(app,work/'routes',app_root=Path.cwd())
    d.github=GitHub()
    with TestClient(app) as c:
        assert c.get('/api/curation/diagnostics').json()['settings']['automatic'] is False
        assert c.post('/api/curation/diagnostics/send').status_code==403
        assert c.post('/api/curation/diagnostics/settings',headers={'X-RMBL-Diagnostics':'1','origin':'https://evil.example'},json={'automatic':True}).status_code==403
        assert c.post('/api/curation/diagnostics/settings',headers={'X-RMBL-Diagnostics':'1'},json={'automatic':'yes'}).status_code==422
        assert c.post('/api/curation/diagnostics/settings',headers={'X-RMBL-Diagnostics':'1'},json={'automatic':False}).json()['settings']['choice_made'] is True
        assert d.github.calls==[]

def test_cross_process_lock_blocks_parallel_delivery(work):
    from backend.app.diagnostics import _delivery_lock
    gh=GitHub();d=service(work,gh);d.capture_exception(ValueError('private'))
    with _delivery_lock(work/'data/delivery.lock') as locked:
        assert locked
        assert d.flush(manual=True)==0
    assert gh.calls==[]
