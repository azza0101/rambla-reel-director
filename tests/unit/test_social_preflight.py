import asyncio
import subprocess
import pytest

def test_login_crash_is_not_reported_started(monkeypatch,tmp_path):
 from backend.app import browser_profiles as m
 class Process:
  pid=99
  def wait(self,timeout):return 21
 monkeypatch.setattr(m,'_installed_browser',lambda:'chrome')
 monkeypatch.setattr(m.subprocess,'Popen',lambda *a,**kw:Process())
 with pytest.raises(m.BrowserUnavailableError,match='21'):
  m._default_login_launcher('tiktok',tmp_path,'https://www.tiktok.com/')

def test_search_check_never_equates_profile_with_login(monkeypatch,tmp_path):
 from backend.app.browser_profiles import BrowserProfileManager
 from backend.app.social_browser_source import BrowserSocialSource
 async def inaccessible(self,*a):raise RuntimeError('login_required')
 monkeypatch.setattr(BrowserSocialSource,'_browser_search',inaccessible)
 manager=BrowserProfileManager(tmp_path)
 (tmp_path/'tiktok').mkdir()
 result=asyncio.run(manager.check_search('tiktok'))
 assert result['ready'] is False and result['login_state']!='verified'
 assert 'login_required' in result['detail']

def test_check_uses_search_page_evidence(monkeypatch,tmp_path):
 from backend.app.browser_profiles import BrowserProfileManager
 from backend.app.social_browser_source import BrowserSocialSource
 async def accessible(self,*a):return {'rows':[{'source_page':'example'}],'diagnostics':{'browser_state':'search_results','login_state':'unknown'}}
 monkeypatch.setattr(BrowserSocialSource,'_browser_search',accessible)
 result=asyncio.run(BrowserProfileManager(tmp_path).check_search('instagram'))
 assert result['ready'] is True and result['login_state']=='unknown'

def test_social_ui_requires_check_before_start():
 from backend.app.curation_ui_v2 import render_curation_page_v2
 html=render_curation_page_v2('test')
 assert 'id="socialConnectDialogV5"' in html
 assert "$('findSocial').onclick=()=>prepareSocialV5()" in html
 assert '/social/${provider}/check' in html
 assert 'checkSocialAndRunV5' in html

def test_all_provider_failures_fail_job_but_true_zero_is_completed():
 from backend.app.debug_social_cli import require_completed_social_search
 with pytest.raises(RuntimeError,match='blocked'):
  require_completed_social_search([{'search_attempts':[{'provider':'tiktok','error':'denied'},{'provider':'instagram','error':'login'}]}])
 require_completed_social_search([{'search_attempts':[{'provider':'tiktok','hits':0}]}])

def test_search_check_endpoint(tmp_path):
 from backend.app.curation_server import create_app
 from fastapi.testclient import TestClient
 class Manager:
  async def check_search(self,provider):return {'provider':provider,'ready':False,'detail':'login_required','login_state':'unknown'}
 client=TestClient(create_app(project_root=tmp_path/'p',allowed_media_roots=[tmp_path],browser_profile_manager=Manager()))
 result=client.post('/api/curation/social/tiktok/check')
 assert result.status_code==200 and result.json()['ready'] is False
 assert client.post('/api/curation/social/facebook/check').status_code==404

def test_social_dialog_behavior_without_browser(tmp_path):
 import re,shutil,subprocess
 from pathlib import Path
 from backend.app.curation_ui_v2 import render_curation_page_v2
 node=shutil.which('node')
 if not node:pytest.skip('Node not installed')
 script=tmp_path/'ui.js'
 script.write_text('\n'.join(re.findall(r'<script[^>]*>(.*?)</script>',render_curation_page_v2('test'),re.S)),encoding='utf-8')
 subprocess.run([node,str(Path('tests/social_preflight_controller.cjs')),str(script)],check=True,capture_output=True)
