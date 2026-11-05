"""User-invoked local launcher. Uses existing project runtimes; installs nothing."""
from pathlib import Path
import hashlib
import argparse
import signal
import json
import os
import socket
import secrets
import subprocess
import time
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, quote, urlparse


def write_desktop_target(root, url):
    query=parse_qs(urlparse(url).query)
    project_id=str((query.get('project') or [''])[0])
    path=root.parent/'rambla-data'/'desktop-target.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    if project_id:
        (path.parent/'last-open-project.json').write_text(json.dumps({'project_id':project_id}),encoding='utf-8')
    if path.is_file():
        previous=json.loads(path.read_text(encoding='utf-8'))
        previous_id=previous.get('project_id')
        previous_root=path.parent/'projects'/str(previous_id or '')
        if previous_id and previous.get('url') != url and (previous_root/'project.json').is_file():
            from backend.app.workspace_backup import backup_project_state
            backup_project_state(previous_root,path.parent/'backups')
    path.write_text(json.dumps({'project_id':project_id,'url':url,'revision':time.time_ns()}),encoding='utf-8')
    return path


def focus_app_window(script, url, *, browser_path, user_data_dir, profile_directory='Default', runner=subprocess.Popen):
    command=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),
             '-Url',url,'-BrowserPath',browser_path,'-UserDataDir',str(user_data_dir),
             '-ProfileDirectory',profile_directory]
    return runner(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                  creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))


def open_browser_url(url, root=None):
    if os.name != 'nt':
        webbrowser.open(url); return
    from backend.app.browser_profiles import _installed_browser
    browser=_installed_browser()
    if not browser:
        os.startfile(url); return
    app_root=Path(root or Path(__file__).resolve().parent)
    write_desktop_target(app_root,url)
    focus_app_window(app_root/'tools'/'focus_rambla_app.ps1',url,browser_path=browser,
                     user_data_dir=app_root.parent/'rambla-data'/'app-browser-profile')


def _fetch_local_json(url):
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url, timeout=1) as response:
        return json.load(response)


def source_build_token(root):
    digest=hashlib.sha256()
    sources=[
        root/'launch_local_v5.py',
        root/'RAMBLA_VERSION',
        *([root/'tools'/'freellm_trial_runtime.py'] if (root/'tools'/'freellm_trial_runtime.py').is_file() else []),
        *sorted((root/'tools'/'resolve_bridge').glob('*.py')),
        *([root/'tools'/'focus_rambla_app.ps1'] if (root/'tools'/'focus_rambla_app.ps1').is_file() else []),
        *sorted((root/'backend'/'app').glob('*.py')),
        *sorted((root/'backend'/'assets'/'resolve_titles').glob('*.drfx')),
        *sorted((root/'backend'/'assets'/'branding').glob('*')),
    ]
    for path in sources:
        digest.update(path.relative_to(root).as_posix().encode('utf-8'))
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def build_server_env(root,port,token,*,base_env=None):
    from tools.freellm_trial_runtime import ensure_gateway
    try:
        ensure_gateway(root)
    except (OSError,RuntimeError) as exc:
        print(f'FreeLLMAPI trial unavailable: {exc}')
    data_root=root.parent/'rambla-data'
    return {**(base_env or os.environ),
        'RAMBLA_BUILD_TOKEN':token,'PYTHONPATH':str(root),
        'PATH':str(root/'runtime'/'bin')+os.pathsep+(base_env or os.environ).get('PATH',''),
        'RAMBLA_RUNTIME_MODE':'desktop_api','RAMBLA_RETRIEVAL_RANKING':'provider',
        'RAMBLA_PROJECT_ROOT':str(data_root/'projects'),
        'RAMBLA_ENABLE_VERTICAL_SOCIAL':'1','RAMBLA_ENABLE_SOCIAL_BROWSER':'1',
        'RAMBLA_ENABLE_WEB_VIDEO':'1',
        'RAMBLA_BROWSER_PROFILE_ROOT':str(data_root/'browser-profiles'),
        'RAMBLA_SOCIAL_SESSION_URL':f'http://127.0.0.1:{port}',
        'RAMBLA_SOCIAL_SESSION_TOKEN':secrets.token_urlsafe(32)}


def runtime_record_path(root):
    return root.parent/'rambla-data'/'desktop-runtime.json'


def stop_recorded_instance(root,build_token,*,fetch=_fetch_local_json,terminate=None):
    record_path=runtime_record_path(root)
    if not record_path.is_file():return False
    try:
        record=json.loads(record_path.read_text(encoding='utf-8'))
        base=str(record['url']).split('/curation',1)[0]
        health=fetch(base+'/health')
        if record.get('build')!=build_token or health.get('build_token')!=build_token:return False
        (terminate or (lambda pid: os.kill(pid,signal.SIGTERM)))(int(record['pid']))
        record_path.unlink(missing_ok=True)
        return True
    except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError):
        return False


def find_running_instance(project_id,build_token,*,fetch=_fetch_local_json):
    """Reuse the server owning live social sessions; never open its profile twice."""
    def inspect_port(port):
        base = f'http://127.0.0.1:{port}'
        try:
            health=fetch(base+'/health')
            if health.get('build_token')!=build_token:
                return None
            if project_id:
                project = fetch(base + '/api/curation/projects/' + quote(project_id, safe=''))
                if project.get('project_id') != project_id:return None
            status = fetch(base + '/api/curation/social/status')
            providers = status.get('providers')
            if not isinstance(providers, dict) or 'tiktok' not in providers:
                return None
            connected = sum(bool(providers.get(p, {}).get('connection_ready')) for p in ('tiktok', 'instagram'))
            try:
                bridge_connected = bool(fetch(base + '/api/curation/resolve-bridge/session').get('connected'))
            except (OSError, ValueError, TypeError, AttributeError):
                bridge_connected = False
            suffix='?project='+quote(project_id,safe='') if project_id else ''
            return bridge_connected, connected, port, base + '/curation' + suffix
        except (OSError, ValueError, TypeError, AttributeError):
            return None
    with ThreadPoolExecutor(max_workers=10) as pool:
        choices = [row for row in pool.map(inspect_port, range(8810, 8820)) if row]
    return max(choices)[3] if choices else None


def main(action='start'):
    root = Path(__file__).resolve().parent
    token=source_build_token(root)
    if action in {'stop','restart'}:
        record_path = runtime_record_path(root)
        recorded_token = json.loads(record_path.read_text(encoding='utf-8')).get('build', token) if record_path.is_file() else token
        stopped=stop_recorded_instance(root,recorded_token)
        if action=='stop':
            print('RAMBLA stopped.' if stopped else 'No matching RAMBLA desktop instance is running.',flush=True)
            return
        time.sleep(.5)
    project_id=os.environ.get('RAMBLA_DEFAULT_PROJECT_ID','').strip()
    if not project_id:
        last=root.parent/'rambla-data'/'last-open-project.json'
        if last.is_file():
            saved=json.loads(last.read_text(encoding='utf-8')).get('project_id','')
            if (root.parent/'rambla-data'/'projects'/saved/'project.json').is_file():
                project_id=saved
    existing = find_running_instance(project_id,token)
    if existing:
        print('Reusing RAMBLA: ' + existing, flush=True)
        open_browser_url(existing,root)
        return
    record_path=runtime_record_path(root)
    if record_path.is_file():
        record=json.loads(record_path.read_text(encoding='utf-8'))
        if record.get('build') != token:
            stop_recorded_instance(root, record.get('build'))
            time.sleep(.5)
    runtimes = [
        root / '.venv/Scripts/python.exe',
        root.parent / 'editorial-intelligence-worktree/.venv/Scripts/python.exe',
    ]
    runtime = next((candidate for candidate in runtimes if candidate.is_file()), runtimes[0])
    if not runtime.is_file():
        raise RuntimeError('Existing RAMBLA UI runtime missing: ' + str(runtime))
    port = None
    for candidate in range(8810, 8820):
        try:
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', candidate))
            port = candidate
            break
        except OSError:
            continue
    if port is None:
        raise RuntimeError('No free RAMBLA port (8810-8819).')
    env = build_server_env(root,port,token)
    Path(env['RAMBLA_PROJECT_ROOT']).mkdir(parents=True,exist_ok=True)
    Path(env['RAMBLA_BROWSER_PROFILE_ROOT']).mkdir(parents=True,exist_ok=True)
    logs = root / '.curation-logs'
    logs.mkdir(exist_ok=True)
    log_path = logs / f'user-launch-{port}.log'
    with log_path.open('ab') as log:
        child = subprocess.Popen([str(runtime), '-m', 'uvicorn', 'backend.app.curation_server:app',
                                  '--host', '127.0.0.1', '--port', str(port)], cwd=root, env=env,
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    for _ in range(60):
        if child.poll() is not None:
            raise RuntimeError('Server exited; see ' + str(log_path))
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=1) as response:
                server_health = json.load(response)
                if server_health.get('status') == 'ok':
                    break
        except OSError:
            time.sleep(.25)
    else:
        raise RuntimeError('Server did not become ready; see ' + str(log_path))
    url = f'http://127.0.0.1:{port}/curation?build={token}'
    if project_id:url+='&project='+quote(project_id,safe='')
    print(url, flush=True)
    record={'pid':server_health.get('server_pid', child.pid),'url':url,'build':token}
    runtime_record_path(root).write_text(json.dumps(record,indent=2),encoding='utf-8')
    (root / '.user-launch.json').write_text(json.dumps(record),encoding='utf-8')
    open_browser_url(url,root)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',nargs='?',choices=('start','focus','stop','restart'),default='start')
    parser.add_argument('--url',default='')
    parser.add_argument('--project',default='')
    args=parser.parse_args()
    if args.project:
        os.environ['RAMBLA_DEFAULT_PROJECT_ID']=args.project
    if args.action=='focus' and args.url:
        open_browser_url(args.url,Path(__file__).resolve().parent)
        raise SystemExit(0)
    main(args.action)
