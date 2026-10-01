from pathlib import Path
import shutil
import uuid

import launch_local_v5 as launcher


def test_build_token_changes_when_transcript_workspace_changes():
    root = Path.cwd() / f".launcher-token-{uuid.uuid4().hex}"
    try:
        app = root / "backend" / "app"
        app.mkdir(parents=True)
        (root / "launch_local_v5.py").write_text("launcher", encoding="utf-8")
        (root / 'RAMBLA_VERSION').write_text('v0006', encoding='utf-8')
        (app / "curation_server.py").write_text("server", encoding="utf-8")
        (app / "curation_ui_v2.py").write_text("ui", encoding="utf-8")
        transcript_ui = app / "transcript_intent_ui.py"
        transcript_ui.write_text("version one", encoding="utf-8")
        before = launcher.source_build_token(root)
        transcript_ui.write_text("version two", encoding="utf-8")
        assert launcher.source_build_token(root) != before
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_build_token_changes_when_bundled_resolve_title_changes(tmp_path):
    root = tmp_path / "app"
    app = root / "backend" / "app"
    titles = root / "backend" / "assets" / "resolve_titles"
    app.mkdir(parents=True)
    titles.mkdir(parents=True)
    (root / "launch_local_v5.py").write_text("launcher", encoding="utf-8")
    (root / 'RAMBLA_VERSION').write_text('v0006', encoding='utf-8')
    (app / "server.py").write_text("server", encoding="utf-8")
    title = titles / "KURA.drfx"
    title.write_bytes(b"version-one")
    before = launcher.source_build_token(root)

    title.write_bytes(b"version-two")

    assert launcher.source_build_token(root) != before


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


def test_chrome_app_launcher_uses_existing_profile_and_dedicated_app_window(tmp_path):
    calls=[]
    script=tmp_path/'focus.ps1'; script.write_text('focus',encoding='utf-8')
    launcher.focus_app_window(
        script, 'http://127.0.0.1:8810/curation?project=p1',
        browser_path=r'C:\Edge\msedge.exe', user_data_dir=r'C:\RAMBLA\App Profile', profile_directory='Default',
        runner=lambda command, **kwargs: calls.append((command,kwargs)),
    )
    command=calls[0][0]
    assert '-File' in command and str(script) in command
    assert '-BrowserPath' in command and r'C:\Edge\msedge.exe' in command
    assert '-UserDataDir' in command and r'C:\RAMBLA\App Profile' in command
    assert '-ProfileDirectory' in command and 'Default' in command
    assert '-Url' in command and 'project=p1' in command[command.index('-Url')+1]


def test_desktop_target_is_shared_between_server_builds(tmp_path):
    root=tmp_path/'app'; root.mkdir()
    path=launcher.write_desktop_target(root,'http://127.0.0.1:8818/curation?project=abc')
    payload=__import__('json').loads(path.read_text(encoding='utf-8'))
    assert path == tmp_path/'rambla-data'/'desktop-target.json'
    assert payload['project_id']=='abc' and payload['revision'] > 0


def test_app_window_launcher_closes_duplicate_windows_and_tracks_origin():
    script=Path('tools/focus_rambla_app.ps1').read_text(encoding='utf-8')
    assert 'FindAll' in script
    assert 'WM_CLOSE' in script
    assert 'rambla-window-origin.txt' in script
    assert '$windows.Count -gt 1' in script

def test_window_identity_survives_windows_powershell_ansi_loading():
    import subprocess
    script=Path('tools/focus_rambla_app.ps1').read_text(encoding='utf-8')
    assert script.encode('ascii')
    csharp=script.split("Add-Type @'",1)[1].split("'@",1)[0]
    check=Path('.window-identity-'+uuid.uuid4().hex+'.ps1')
    try:
        checks="""
if (-not [RamblaWindow]::IsRamblaTitle(('RAMBLA '+[char]0x00b7+' B-ROLL'))) { throw 'App title not recognized' }
if ([RamblaWindow]::IsRamblaTitle('RAMBLA - B-ROLL')) { throw 'Bridge must not be matched' }
if ([RamblaWindow]::IsRamblaTitle('YouTube - Microsoft Edge')) { throw 'Unrelated window matched' }
"""
        check.write_text("Add-Type @'"+csharp+"'@\n"+checks,encoding='ascii')
        result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(check.resolve())],capture_output=True,text=True)
        assert result.returncode==0,result.stderr
    finally:
        check.unlink(missing_ok=True)


def test_launch_aborts_when_mutex_is_not_acquired():
    script=Path('tools/focus_rambla_app.ps1').read_text(encoding='ascii')
    assert "if (-not $acquired) { throw" in script
    assert script.index("if (-not $acquired)") < script.index('Start-Process')
    assert 'if ($acquired)' in script
