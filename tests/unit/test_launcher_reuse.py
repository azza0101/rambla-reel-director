import launch_local_v5 as launcher


def test_launcher_prefers_existing_connected_instance_over_newer_unconnected_one():
    def fetch(url):
        if ':8817/' not in url and ':8818/' not in url:
            raise OSError('offline')
        if '/projects/' in url:
            return {'project_id':'project'}
        return {'providers':{'tiktok':{'connection_ready':':8817/' in url}}}
    assert launcher.find_running_instance('project', fetch=fetch) == 'http://127.0.0.1:8817/curation?project=project'


def test_launcher_ignores_unrelated_http_services():
    assert launcher.find_running_instance('project', fetch=lambda _: {'status':'ok'}) is None
