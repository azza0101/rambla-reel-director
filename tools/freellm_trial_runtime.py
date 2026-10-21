"""Start the separately installed FreeLLMAPI trial on loopback, if opted in."""
import json,os,shutil,subprocess,time,urllib.request
from pathlib import Path


def ensure_gateway(root):
    root=Path(root)
    config=root/'.env.local'
    settings={}
    if config.is_file():
        for line in config.read_text(encoding='utf-8-sig').splitlines():
            k,sep,v=line.partition('=')
            if sep:settings[k.strip()]=v.strip().strip('"').strip("'")
    if settings.get('RAMBLA_VISUAL_BACKEND')!='freellmapi':return None
    data=root.parent/'rambla-data'/'freellm-trial'
    token_path=data/'gateway-token.txt'
    if not token_path.is_file():raise RuntimeError('FreeLLMAPI trial is not provisioned')
    token=token_path.read_text().strip()
    def ready():
        try:
            req=urllib.request.Request('http://127.0.0.1:8831/v1/models',headers={'Authorization':'Bearer '+token})
            with urllib.request.urlopen(req,timeout=1) as response:return response.status==200
        except (OSError,ValueError):return False
    if ready():return {'port':8831,'reused':True}
    repo=root.parent.parent/'freellmapi-trial'
    entry=repo/'server/dist/index.js'
    node=shutil.which('node')
    if not node or not entry.is_file():raise RuntimeError('FreeLLMAPI trial installation is missing')
    env={**os.environ,'HOST':'127.0.0.1','PORT':'8831','FREEAPI_DB_PATH':str(data/'gateway.db'),
         'ENCRYPTION_KEY':(data/'encryption-key.txt').read_text().strip()}
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    with (data/'server.log').open('a') as output:
        process=subprocess.Popen([node,str(entry)],cwd=repo,env=env,stdout=output,stderr=output,creationflags=flags)
    record={'pid':process.pid,'port':8831,'repo':str(repo)}
    (data/'runtime.json').write_text(json.dumps(record))
    for _ in range(15):
        if ready():return record
        if process.poll() is not None:break
        time.sleep(.2)
    raise RuntimeError('FreeLLMAPI trial did not become ready; see its local server.log')
