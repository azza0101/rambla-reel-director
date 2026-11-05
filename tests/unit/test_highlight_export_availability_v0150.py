from fastapi.testclient import TestClient

from backend.app.curation_server import create_app
from backend.app.curation_project import ProjectStore
from backend.app.transcript_intents import load_phrase_intents, save_phrase_intents
from tests.unit.test_transcript_intents import _run


def test_saved_highlights_are_counted_when_the_export_checkbox_is_off(tmp_path):
    root=tmp_path/'projects'
    project=ProjectStore(root,probe_runner=lambda _: {}).create('Test')
    project_root=root/project.project_id
    run=_run(project_root)
    initial=load_phrase_intents(run)
    save_phrase_intents(run, {'chunk_001':{'highlighted_word_indices':[1]}}, initial['transcript_signature'])
    client=TestClient(create_app(project_root=root))
    url=f'/api/curation/projects/{project.project_id}/export-options'
    assert client.put(url,json={'subtitles':True,'highlights':False}).status_code==200
    response=client.get(url)
    assert response.status_code==200, response.text
    row=response.json()
    assert row['components']['highlights'] is False
    assert row['counts']['highlights'] == 1
    assert row['counts']['subtitles'] > 0
    assert client.put(url,json={'subtitles':True,'highlights':True}).status_code==200
    selected=client.get(url).json()
    assert selected['components']['highlights'] is True
    assert selected['counts']['highlights'] == 1


def test_highlight_edit_refreshes_export_options_after_saving():
    from backend.app.transcript_intent_ui import JS
    assert 'loadResolveComponentsV71' in JS
