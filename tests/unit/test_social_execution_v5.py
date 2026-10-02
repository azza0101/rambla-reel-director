import asyncio,json
from types import SimpleNamespace
from tests.unit.test_editorial_import import fixture
from backend.app.editorial_import import import_plan,retrieval_bundle

def test_global_social_routes_imported_broll_beats(monkeypatch,tmp_path):
 from backend.app import debug_social_cli as worker
 package,plan=fixture(tmp_path);import_plan(tmp_path,plan,package)
 (tmp_path/'semantic-beats.json').write_text('{}');video=tmp_path/'source.mp4';video.write_bytes(b'x')
 root=retrieval_bundle(tmp_path)[0];calls=[]
 monkeypatch.setattr(worker,'_probe',lambda p:(25,200))
 monkeypatch.setattr(worker,'persist_video_diagnostics',lambda p:None)
 def execute(cmd,**kwargs):
  calls.append(cmd);(root/'online-candidates.json').write_text(json.dumps([{'parent_beat_id':'vb-1','search_attempts':[{'provider':'tiktok','hits':0},{'provider':'instagram','hits':0}]}]))
 monkeypatch.setattr(worker.subprocess,'run',execute)
 result=worker.run_social_research(video=video,output=tmp_path,client_id='test')
 assert result['beats']==1
 assert calls[0][calls[0].index('--beat-ids')+1:calls[0].index('--providers')]==['vb-1']
 assert calls[0][-2:]==['tiktok','instagram']

def test_social_failed_search_is_not_cached(tmp_path,monkeypatch):
 from backend.app import quality_video
 from backend.app.funnel_runtime import cached_source_video_beat
 calls=[]
 async def source(engine,**kw):
  calls.append(1);return {'candidates':[],'search_attempts':[{'provider':'tiktok','error':'profile_in_use'}]}
 monkeypatch.setattr(quality_video,'source_video_beat',source)
 engine=SimpleNamespace(cache=SimpleNamespace(root=tmp_path),sources=[SimpleNamespace(provider_name='tiktok')])
 async def run():
  await cached_source_video_beat(engine,beat_id='b')
  await cached_source_video_beat(engine,beat_id='b')
 asyncio.run(run());assert len(calls)==2

def test_browser_and_public_failure_is_not_zero_hits():
 from backend.app.social_browser_source import BrowserSocialSource
 class Manager:
  async def run_in_profile(self,*a,**kw):raise RuntimeError('profile in use')
 class Fallback:
  last_attempt={'error':'HTTPStatusError'}
  async def search(self,*a,**kw):return []
 source=BrowserSocialSource('instagram',Manager(),fallback=Fallback())
 asyncio.run(source.search('passenger ferry',orientation=None,min_duration=1,max_duration=60,limit=2))
 assert source.last_attempt.get('error')
 assert source.last_attempt['fallback_attempt']['error']=='HTTPStatusError'
 assert 'hits' not in source.last_attempt

def test_dump_dom_login_and_empty_document_are_not_zero_hits():
 from backend.app.browser_profiles import _DumpDomPage
 from backend.app.social_browser_source import BrowserSocialSource
 for html in ('<html><title>Login • Instagram</title><form><input type="password"></form></html>',''):
  class Manager:
   async def run_in_profile(self,provider,callback,**kw):return await callback(_DumpDomPage(html,kw['start_url']),None)
  source=BrowserSocialSource('instagram',Manager())
  asyncio.run(source.search('passenger ferry',orientation=None,min_duration=1,max_duration=60,limit=2))
  assert source.last_attempt.get('error')
  assert 'hits' not in source.last_attempt

def test_append_social_preserves_verified_proposals_and_discovery():
 from backend.app.beat_research import merge_video_rows
 old={'parent_beat_id':'b','coverage_slot_id':'b:shot:s','quality_version':'q','candidates':[{'id':'clip','clip_verified':True}], 'discovery_sources':[{'id':'envato','provider':'envato'}]}
 new={'parent_beat_id':'b','coverage_slot_id':'b:shot:s','candidates':[], 'discovery_sources':[], 'proposals':{'proposal_A':None},'search_attempts':[{'provider':'tiktok','error':'login'}]}
 merged=merge_video_rows([old],[new],'b','append')[0]
 assert merged['proposals']['proposal_A']['id']=='clip'
 assert merged['discovery_sources'][0]['id']=='envato'

def test_workflow_controls_are_unique_and_grouped():
 from backend.app.curation_ui_v2 import render_curation_page_v2
 from html.parser import HTMLParser
 class Parser(HTMLParser):
  def __init__(self):super().__init__();self.ids=[]
  def handle_starttag(self,tag,attrs):
   value=dict(attrs).get('id')
   if value:self.ids.append(value)
 html=render_curation_page_v2('test');page=html.split('<script>')[0]
 parser=Parser();parser.feed(page)
 assert len(parser.ids)==len(set(parser.ids))
 media=page[page.index('id="mediaWorkflowV5"'):page.index('<div class="grid">')]
 assert all('id="'+id+'"' in media for id in ['findSocial','findVideos','findImages','socialConnectionsV5'])
 assert '1 · Source &amp; analysis' in page and '2 · Transcript review' in page and '3 · Editorial plan' in page
 assert 'THIS BEAT' in html
