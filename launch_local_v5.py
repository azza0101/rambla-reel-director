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
from urllib.parse import quote


def _fetch_local_json(url):
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url, timeout=1) as response:
        return json.load(response)


def source_build_token(root):
    digest=hashlib.sha256()
    for relative in ('launch_local_v5.py','backend/app/curation_server.py','backend/app/curation_ui_v2.py'):
        digest.update((root/relative).read_bytes())
    return digest.hexdigest()[:12]


def build_server_env(root,port,token,*,base_env=None):
    data_root=root.parent/'rambla-data'
    return {**(base_env or os.environ),
        'RAMBLA_BUILD_TOKEN':token,'PYTHONPATH':str(root),
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
            suffix='?project='+quote(project_id,safe='') if project_id else ''
            return connected, port, base + '/curation' + suffix
        except (OSError, ValueError, TypeError, AttributeError):
            return None
    with ThreadPoolExecutor(max_workers=10) as pool:
        choices = [row for row in pool.map(inspect_port, range(8810, 8820)) if row]
    return max(choices)[2] if choices else None


def main(action='start'):
    root = Path(__file__).resolve().parent
    token=source_build_token(root)
    if action in {'stop','restart'}:
        stopped=stop_recorded_instance(root,token)
        if action=='stop':
            print('RAMBLA stopped.' if stopped else 'No matching RAMBLA desktop instance is running.',flush=True)
            return
        time.sleep(.5)
    project_id=os.environ.get('RAMBLA_DEFAULT_PROJECT_ID','').strip()
    existing = find_running_instance(project_id,token)
    if existing:
        print('Reusing RAMBLA: ' + existing, flush=True)
        webbrowser.open(existing)
        return
    runtime = root.parent / 'editorial-intelligence-worktree/.venv/Scripts/python.exe'
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
                if json.load(response).get('status') == 'ok':
                    break
        except OSError:
            time.sleep(.25)
    else:
        raise RuntimeError('Server did not become ready; see ' + str(log_path))
    url = f'http://127.0.0.1:{port}/curation?build={token}'
    if project_id:url+='&project='+quote(project_id,safe='')
    print(url, flush=True)
    record={'pid':child.pid,'url':url,'build':token}
    runtime_record_path(root).write_text(json.dumps(record,indent=2),encoding='utf-8')
    (root / '.user-launch.json').write_text(json.dumps(record),encoding='utf-8')
    webbrowser.open(url)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',nargs='?',choices=('start','stop','restart'),default='start')
    main(parser.parse_args().action)
