import os
from pathlib import Path
import uuid
import pytest
from backend.app.github_auth import store_token,load_token,github_environment

@pytest.fixture
def root():
    path=Path('.test-tmp')/('github-auth-'+uuid.uuid4().hex)/'app'
    path.mkdir(parents=True)
    return path

@pytest.mark.skipif(os.name!='nt',reason='Windows DPAPI')
def test_token_is_machine_user_encrypted_and_reused(root):
    value='github_pat_'+('A'*70)
    target=store_token(root,value)
    assert value.encode() not in target.read_bytes()
    assert load_token(root)==value
    env=github_environment(root,{'OTHER':'keep'})
    assert env['GH_TOKEN']==value and env['OTHER']=='keep'

@pytest.mark.parametrize('value',['gho_personal_account','ghp_broad_token','password',''])
def test_rejects_full_account_oauth_and_classic_tokens(root,value):
    with pytest.raises(ValueError):store_token(root,value)

def test_no_provisioning_keeps_existing_github_login(root):
    assert github_environment(root,{'OTHER':'keep'})=={'OTHER':'keep'}
