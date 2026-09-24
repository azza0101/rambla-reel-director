import json
import pytest
from tests.unit.test_editorial_import import fixture
from backend.app.editorial_import import import_plan,load_import,active_retrieval_root,transcript_package
from backend.app.transcript_corrections import correct_phrase,needs_editorial_refresh,require_current_editorial

def test_correction_updates_all_text_and_preserves_timing_and_media(tmp_path):
    package,plan=fixture(tmp_path);root=import_plan(tmp_path,plan,package)
    selection=root/'selection-plan.json';selection.write_text('{"safe":true}')
    raw=(tmp_path/'transcript-raw.json').read_bytes()
    result=correct_phrase(tmp_path,'vb-1',{'c1':'Slice the potatoes.','c2':'Keep the pieces small.'},plan['visual_beats'][0]['original_text'])
    assert result['changed']
    current=load_import(tmp_path)
    assert current['visual_beats'][0]['original_text']=='Slice the potatoes. Keep the pieces small.'
    assert current['visual_beats'][0]['end']==6
    assert active_retrieval_root(tmp_path)==root
    assert selection.read_text()=='{"safe":true}'
    assert (tmp_path/'transcript-raw.json').read_bytes()==raw
    package=transcript_package(tmp_path,'project1',8)
    assert 'potatoes' in package['full_transcript']
    assert package['word_timestamps']==[]
    with pytest.raises(ValueError,match='rigenera'):require_current_editorial(tmp_path)
    current['global_topic']='Preparing potatoes'
    import_plan(tmp_path,current,package)
    assert not needs_editorial_refresh(tmp_path)


def test_stale_or_empty_edit_cannot_modify_files(tmp_path):
    package,plan=fixture(tmp_path);import_plan(tmp_path,plan,package)
    before=(tmp_path/'semantic-chunks.json').read_bytes()
    with pytest.raises(ValueError):correct_phrase(tmp_path,'vb-1',{'c1':'x','c2':'y'},'stale text')
    with pytest.raises(ValueError):correct_phrase(tmp_path,'vb-1',{'c1':'','c2':'y'},plan['visual_beats'][0]['original_text'])
    assert (tmp_path/'semantic-chunks.json').read_bytes()==before


def test_phrase_edit_api_reads_saves_and_rejects_busy_project(tmp_path):
    from tests.unit.test_project_maintenance_api import _client
    import backend.app.debug_server as debug
    client,projects,source=_client(tmp_path)
    pid=client.post('/api/curation/projects',json={'name':'Corrections'}).json()['project_id']
    run=projects/pid/'run';run.mkdir(parents=True,exist_ok=True)
    package,plan=fixture(run);package['project_id']=pid;plan['project_id']=pid
    import_plan(run,plan,package)
    url=f'/api/curation/projects/{pid}/beats/vb-1/transcript'
    current=client.get(url).json()
    assert len(current['chunks'])==2
    payload={'expected_text':current['text'],'chunks':{'c1':'Slice the potatoes.','c2':'Keep the pieces small.'}}
    running=debug.RunState('edit-busy',source,run,status='RUNNING',stage_type='videos');debug.RUNS[running.run_id]=running
    try:assert client.put(url,json=payload).status_code==409
    finally:debug.RUNS.pop(running.run_id,None)
    assert client.put(url,json=payload).status_code==200
    assert 'potatoes' in client.get(url).json()['text']
    assert client.put(url,json=payload).status_code==409
    assert 'potatoes' in client.get(f'/api/curation/projects/{pid}/transcript').json()['segments'][0]['text']
    assert client.post(f'/api/curation/projects/{pid}/source/social',json={'providers':['tiktok']}).status_code==409


def test_write_failure_rolls_back_edit(tmp_path,monkeypatch):
    import backend.app.transcript_corrections as mod
    package,plan=fixture(tmp_path);root=import_plan(tmp_path,plan,package)
    paths=[tmp_path/'semantic-chunks.json',tmp_path/'visual-plan.json',root/'imported-plan.json']
    original={p:p.read_bytes() for p in paths}
    writer=mod.write_json
    def fail(path,payload):
        if path.name=='transcript-corrections.json':raise OSError('write failed')
        writer(path,payload)
    monkeypatch.setattr(mod,'write_json',fail)
    with pytest.raises(OSError):correct_phrase(tmp_path,'vb-1',{'c1':'Potatoes.','c2':'Small pieces.'},plan['visual_beats'][0]['original_text'])
    assert all(p.read_bytes()==data for p,data in original.items())
    assert not (tmp_path/'editorial-location.json').exists()
