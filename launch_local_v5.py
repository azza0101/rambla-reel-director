"""User-invoked local launcher. Uses existing project runtimes; installs nothing."""
from pathlib import Path
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


def find_running_instance(project_id, *, fetch=_fetch_local_json):
    """Reuse the server owning live social sessions; never open its profile twice."""
    def inspect_port(port):
        base = f'http://127.0.0.1:{port}'
        try:
            project = fetch(base + '/api/curation/projects/' + quote(project_id, safe=''))
            if project.get('project_id') != project_id:
                return None
            status = fetch(base + '/api/curation/social/status')
            providers = status.get('providers')
            if not isinstance(providers, dict) or 'tiktok' not in providers:
                return None
            connected = sum(bool(providers.get(p, {}).get('connection_ready')) for p in ('tiktok', 'instagram'))
            return connected, port, base + '/curation?project=' + quote(project_id, safe='')
        except (OSError, ValueError, TypeError, AttributeError):
            return None
    with ThreadPoolExecutor(max_workers=10) as pool:
        choices = [row for row in pool.map(inspect_port, range(8810, 8820)) if row]
    return max(choices)[2] if choices else None


def main():
    root = Path(__file__).resolve().parent
    existing = find_running_instance('fea7fff128ef')
    if existing:
        print('Reusing RAMBLA: ' + existing, flush=True)
        webbrowser.open(existing)
        return
    runtime = root.parent / 'editorial-intelligence-worktree/.venv/Scripts/python.exe'
    if not runtime.is_file():
        raise RuntimeError('Existing RAMBLA UI runtime missing: ' + str(runtime))
    publication = root / '.funnel-publication.json'
    token = json.loads(publication.read_text(encoding='utf-8'))['sha'][:7] if publication.exists() else 'social-preflight-v5'
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
    env = {**os.environ, 'RAMBLA_BUILD_TOKEN': token, 'PYTHONPATH': str(root),
           'RAMBLA_ENABLE_VERTICAL_SOCIAL': '1', 'RAMBLA_ENABLE_SOCIAL_BROWSER': '1',
           'RAMBLA_ENABLE_WEB_VIDEO': '1',
           'RAMBLA_BROWSER_PROFILE_ROOT': str(root.parent / 'browser-profiles'),
           'RAMBLA_SOCIAL_SESSION_URL': f'http://127.0.0.1:{port}',
           'RAMBLA_SOCIAL_SESSION_TOKEN': secrets.token_urlsafe(32)}
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
    url = f'http://127.0.0.1:{port}/curation?build={token}&project=fea7fff128ef'
    print(url, flush=True)
    (root / '.user-launch.json').write_text(json.dumps({'pid':child.pid,'url':url,'build':token}),encoding='utf-8')
    webbrowser.open(url)


if __name__ == '__main__':
    main()
