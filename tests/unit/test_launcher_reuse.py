from pathlib import Path

import launch_local_v5 as launcher


def test_launcher_prefers_existing_connected_instance_from_same_build():
    def fetch(url):
        if ':8817/' not in url and ':8818/' not in url:
            raise OSError('offline')
        if url.endswith('/health'):
            return {'status':'ok','build_token':'current'}
        if '/projects/' in url:
            return {'project_id':'project'}
        return {'providers':{'tiktok':{'connection_ready':':8817/' in url}}}
    assert launcher.find_running_instance('project','current',fetch=fetch) == 'http://127.0.0.1:8817/curation?project=project'


def test_launcher_ignores_running_instance_from_another_build():
    def fetch(url):
        if url.endswith('/health'):
            return {'status':'ok','build_token':'old'}
        if '/projects/' in url:
            return {'project_id':'project'}
        return {'providers':{'tiktok':{'connection_ready':True}}}
    assert launcher.find_running_instance('project','current',fetch=fetch) is None


def test_launcher_ignores_unrelated_http_services():
    assert launcher.find_running_instance('project','current',fetch=lambda _: {'status':'ok'}) is None


def test_desktop_launcher_builds_gpu_free_api_environment():
    root=Path('C:/RAMBLA/app')
    env=launcher.build_server_env(root,8810,'build-1',base_env={'PEXELS_API_KEY':'secret'})
    assert env['RAMBLA_RUNTIME_MODE']=='desktop_api'
    assert env['RAMBLA_RETRIEVAL_RANKING']=='provider'
    assert env['RAMBLA_BUILD_TOKEN']=='build-1'
    assert env['PEXELS_API_KEY']=='secret'
    assert Path(env['RAMBLA_PROJECT_ROOT'])==root.parent/'rambla-data'/'projects'


def test_stop_only_terminates_the_recorded_matching_build(tmp_path):
    root=tmp_path/'app';root.mkdir()
    record=tmp_path/'rambla-data'/'desktop-runtime.json'
    record.parent.mkdir()
    record.write_text('{"pid":123,"url":"http://127.0.0.1:8810/curation","build":"same"}',encoding='utf-8')
    killed=[]
    assert launcher.stop_recorded_instance(root,'same',fetch=lambda _: {'build_token':'same'},terminate=killed.append)
    assert killed==[123]
    assert not record.exists()


def test_stop_refuses_stale_record_from_another_build(tmp_path):
    root=tmp_path/'app';root.mkdir()
    record=tmp_path/'rambla-data'/'desktop-runtime.json'
    record.parent.mkdir()
    record.write_text('{"pid":123,"url":"http://127.0.0.1:8810/curation","build":"old"}',encoding='utf-8')
    killed=[]
    assert not launcher.stop_recorded_instance(root,'current',fetch=lambda _: {'build_token':'old'},terminate=killed.append)
    assert killed==[]
