from backend.app.social_page_evidence import inspect_search_html

def test_script_translation_and_hidden_template_are_not_page_evidence():
 page=inspect_search_html('<html><script>"no results found"; data-e2e="profile-icon"</script><template>No videos found</template><div hidden>No results found</div><main>Loading</main></html>')
 assert 'no results' not in page.visible_text and not page.signed_in

def test_actual_elements_are_evidence():
 page=inspect_search_html('<html><title>Search</title><main>No results found<input type="password"></main></html>')
 assert page.login_required and 'no results found' in page.visible_text

def test_script_only_zero_message_does_not_complete_browser_search():
 import asyncio
 from backend.app.browser_profiles import _DumpDomPage
 from backend.app.social_browser_source import BrowserSocialSource
 class Manager:
  async def run_in_profile(self,provider,callback,**kwargs):
   return await callback(_DumpDomPage('<html><script>{"empty":"no results found"}</script><main>Loading</main></html>',kwargs['start_url']),None)
 source=BrowserSocialSource('tiktok',Manager())
 assert asyncio.run(source.search('airplane window',orientation=None,min_duration=1,max_duration=60,limit=2))==[]
 assert source.last_attempt['browser_state']=='search_results_unavailable'
 assert source.last_attempt['error'] and 'hits' not in source.last_attempt

def test_search_diagnostics_scroll_and_copy_full_json():
 from backend.app.curation_ui_v2 import render_curation_page_v2
 html=render_curation_page_v2('diagnostics')
 assert 'max-height:320px;overflow:auto;overscroll-behavior:contain' in html
 assert 'id="copySearchDiagnostics"' in html
 assert 'navigator.clipboard.writeText(JSON.stringify(c.retrieval_diagnostics||{},null,2))' in html
