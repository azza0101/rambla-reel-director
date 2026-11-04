import asyncio
import json
from types import SimpleNamespace


def test_selected_envato_is_downloaded_and_failures_are_reported(tmp_path, monkeypatch):
    from backend.app.curation_project import ProjectStore
    from backend.app.curation_server import create_app
    import backend.app.curation_artifacts as artifacts
    import backend.app.transcript_intents as intents
    import backend.app.envato_auto_download as envato
    project = ProjectStore(tmp_path, probe_runner=lambda _: {}).create('Example')
    run = tmp_path / project.project_id / 'run'
    run.mkdir(exist_ok=True)
    (run / 'selection-plan.json').write_text(json.dumps({'chunks': {'beat': {'selected_assets': [{'asset_id': 'one'}, {'asset_id': 'two'}]}}}))
    def candidate(asset_id):
        return SimpleNamespace(asset_id=asset_id, chunk_id='beat', provider='envato', kind='video', title=asset_id, source_page='https://elements.envato.com/item', local_asset_path=None, preview_path=None)
    monkeypatch.setattr(artifacts, 'load_curation_run', lambda _: SimpleNamespace(candidate_index={x:candidate(x) for x in ('one','two')}))
    monkeypatch.setattr(intents, 'has_selected_intent', lambda *args: True)
    calls=[]
    async def download(self, url, name, folder, asset_id, progress=None):
        calls.append((name, asset_id))
        if asset_id == 'two': raise RuntimeError('login required')
        return {'status':'ready'}
    monkeypatch.setattr(envato.EnvatoSession, 'download', download)
    app = create_app(project_root=tmp_path)
    progress=[]
    failures=asyncio.run(app.state.prepare_selected_timeline_media(project.project_id, report=lambda n,s:progress.append(s)))
    assert calls == [('Example','one'),('Example','two')]
    assert [f['asset_id'] for f in failures] == ['two']
    assert any('Envato' in s for s in progress)


def test_ignore_all_control_is_available():
    from backend.app.timeline_export_ui import JS
    assert 'IGNORA TUTTE LE COPERTURE NON DISPONIBILI' in JS

def test_session_status_never_claims_connected_from_profile_alone(tmp_path):
    from backend.app.envato_auto_download import session_evidence
    assert session_evidence('envato', 'https://elements.envato.com/', '<a href="/login">Sign in</a>') == 'login_required'
    assert session_evidence('envato', 'https://elements.envato.com/', '<p>Welcome</p>') == 'unknown'
    assert session_evidence('envato', 'https://elements.envato.com/', '<a href="/account/downloads">My downloads</a>') == 'connected'
    assert session_evidence('tiktok', 'https://www.tiktok.com/', '<span data-e2e="profile-icon"></span>') == 'connected'
    assert session_evidence('tiktok', 'https://www.tiktok.com/', '<p>Verify you are human</p>') == 'verification_required'

def test_export_ui_has_individual_media_progress():
    from backend.app.timeline_export_ui import PANEL, JS
    assert 'resolveCurrentMediaV136' in PANEL
    assert 'job.media' in JS
    assert 'Dimensione non disponibile' in JS

def test_failed_envato_offer_retry_and_reuses_existing_selection(tmp_path, monkeypatch):
    import asyncio,json
    from backend.app.curation_project import ProjectStore
    from backend.app.curation_server import create_app
    from backend.app.envato_auto_download import EnvatoSession
    import backend.app.curation_artifacts as artifacts
    import backend.app.transcript_intents as intents
    root=tmp_path/'projects';p=ProjectStore(root,probe_runner=lambda _:{}).create('Test')
    run=root/p.project_id/'run';run.mkdir(exist_ok=True)
    (run/'selection-plan.json').write_text(json.dumps({'chunks':{'beat':{'selected_assets':[{'asset_id':'one'}]}}}))
    candidate=SimpleNamespace(asset_id='one',chunk_id='beat',provider='envato',kind='video',title='Campfire',source_page='https://elements.envato.com/item-ABCDEF',local_asset_path=None,preview_path=None)
    monkeypatch.setattr(artifacts,'load_curation_run',lambda _:SimpleNamespace(candidate_index={'one':candidate}))
    monkeypatch.setattr(intents,'has_selected_intent',lambda *a:True)
    calls=[]
    async def download(self,url,name,folder,asset_id,progress=None):
        calls.append(asset_id)
        if len(calls)==1:raise RuntimeError('Envato non ha risposto entro 50 secondi')
        return {'status':'ready'}
    monkeypatch.setattr(EnvatoSession,'download',download)
    issues=[]
    def report(*args):pass
    async def issue(row):issues.append(row);return 'retry'
    report.interactive=True;report.issue=issue
    app=create_app(project_root=root)
    assert asyncio.run(app.state.prepare_selected_timeline_media(p.project_id,report=report))==[]
    assert calls==['one','one'] and issues[0]['source_page']==candidate.source_page
