"""User-invoked local launcher. Uses existing project runtimes; installs nothing."""
from pathlib import Path
import json
import os
import socket
import subprocess
import time
import urllib.request
import webbrowser


def main():
    root = Path(__file__).resolve().parent
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
           'RAMBLA_BROWSER_PROFILE_ROOT': str(root.parent / 'browser-profiles')}
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
