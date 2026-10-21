"""Update managed Auto-Cut code without replacing native SDK, runtime or user data."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
import tomllib
import zipfile

PLUGIN_FILES={'main.js','preload.js','source_adapter.js','loading.html','manifest.xml','package.json'}
REPO='azza0101/rambla-reel-director'


def allowed(name):
    p=PurePosixPath(name)
    if not name or '\\' in name or ':' in name or p.is_absolute() or '..' in p.parts:return False
    return (name in {'RAMBLA_VERSION','pyproject.toml','backend/__init__.py'} or
            name.startswith('backend/app/') and name.endswith('.py') or
            p.parent==PurePosixPath('tools/autocut_integration') and p.name in PLUGIN_FILES)


def commit_files(changes,data_root):
    backup=Path(data_root)/'update-backups'/datetime.now().strftime('%Y%m%d-%H%M%S-%f');backup.mkdir(parents=True)
    previous=[];manifest=[]
    try:
        for index,(target,content) in enumerate(changes):
            target=Path(target)
            if target.is_symlink():raise ValueError('Destinazione aggiornamento non valida')
            old=target.read_bytes() if target.is_file() else None
            if old==content:continue
            if old is not None:(backup/str(index)).write_bytes(old)
            manifest.append({'target':str(target),'backup':str(index) if old is not None else None})
            (backup/'manifest.json').write_text(json.dumps({'files':manifest},indent=2),'utf-8')
            previous.append((target,old));target.parent.mkdir(parents=True,exist_ok=True)
            temporary=target.with_name(target.name+'.autocut-update');temporary.write_bytes(content);os.replace(temporary,target)
    except Exception:
        for target,old in reversed(previous):
            if old is None:target.unlink(missing_ok=True)
            else:target.write_bytes(old)
        raise
    return str(backup)


def plugin_changes(root,plugin):
    return [(plugin/name,(root/'tools'/'autocut_integration'/name).read_bytes()) for name in PLUGIN_FILES if (root/'tools'/'autocut_integration'/name).is_file()]


def apply_archive(root,plugin,data,archive,expected_hash):
    root,plugin=Path(root).resolve(),Path(plugin).resolve()
    archive=Path(archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=expected_hash:raise ValueError('SHA256 pacchetto non valido')
    changes=[];contents={}
    with zipfile.ZipFile(archive) as z:
        if sum(i.file_size for i in z.infolist())>40*1024*1024:raise ValueError('Pacchetto troppo grande')
        for info in z.infolist():
            if info.is_dir():continue
            if not allowed(info.filename) or info.filename in contents or (info.external_attr>>16)&0o170000==0o120000:raise ValueError('File non consentito nel pacchetto')
            contents[info.filename]=z.read(info)
    pyproject=root/'pyproject.toml'
    if 'pyproject.toml' not in contents or not pyproject.is_file():raise ValueError('Manifest dipendenze mancante')
    def dependencies(raw):
        project=tomllib.loads(raw.decode('utf-8'))['project']
        return {key:project.get(key) for key in ('dependencies','optional-dependencies','requires-python')}
    if dependencies(contents['pyproject.toml'])!=dependencies(pyproject.read_bytes()):raise ValueError('Dipendenze cambiate: serve il nuovo installer')
    for name,content in contents.items():
        target=root/name
        if not target.resolve().is_relative_to(root):raise ValueError('Percorso aggiornamento non valido')
        changes.append((target,content))
        if PurePosixPath(name).parent==PurePosixPath('tools/autocut_integration'):
            destination=plugin/PurePosixPath(name).name
            if not destination.resolve().is_relative_to(plugin):raise ValueError('Percorso plugin non valido')
            changes.append((destination,content))
    return commit_files(changes,data)


def update(root,plugin,data):
    root,plugin,data=Path(root).resolve(),Path(plugin).resolve(),Path(data).resolve()
    from .software_update import installed_root
    if not installed_root(root):
        backup=commit_files(plugin_changes(root,plugin),data)
        return {'status':'updated','message':'Modifiche locali ricaricate; Resolve resta aperto.','backup':backup}
    record=root.parent/'rambla-data'/'desktop-runtime.json'
    if record.is_file():
        import urllib.request
        from urllib.parse import urlsplit
        saved=json.loads(record.read_text('utf-8'))
        url=urlsplit(saved.get('url',''))
        if url.hostname=='127.0.0.1' and url.port:
            try:
                with urllib.request.urlopen('http://127.0.0.1:'+str(url.port)+'/health',timeout=1) as response:running=json.load(response).get('status')=='ok'
            except OSError:running=False
            if running:raise RuntimeError('Chiudi soltanto il programma RMBL B ROLL prima di aggiornare il motore condiviso. Resolve può restare aperto.')
    from .github_auth import github_environment
    env=github_environment(root)
    gh=shutil.which('gh') or str(root/'runtime'/'bin'/'gh.exe')
    def call(args):return subprocess.run([gh,*args],env=env,capture_output=True,text=True,check=True,timeout=120).stdout
    releases=json.loads(call(['api','repos/'+REPO+'/releases?per_page=100']))
    releases=[r for r in releases if not r.get('draft') and r['tag_name'].startswith('autocut-')]
    if not releases:raise RuntimeError('Nessun aggiornamento Auto-Cut pubblicato')
    release=max(releases,key=lambda r:r.get('published_at') or '')
    with tempfile.TemporaryDirectory(prefix='rmbl-autocut-update-') as folder:
        stage=Path(folder)
        call(['release','download',release['tag_name'],'--repo',REPO,'--pattern','autocut-update.json','--dir',str(stage)])
        manifest=json.loads((stage/'autocut-update.json').read_text('utf-8'))
        if not re.fullmatch(r'RMBL-AutoCut-\d+\.\d+\.\d+\.zip',str(manifest.get('archive',''))) or not re.fullmatch(r'[a-f0-9]{64}',str(manifest.get('sha256',''))):raise ValueError('Manifest aggiornamento non valido')
        current=json.loads((plugin/'package.json').read_text('utf-8'))['version']
        def version(v):return tuple(int(x) for x in v.split('.'))
        if version(manifest['version'])<=version(current):return {'status':'current','message':'Auto-Cut è già aggiornato'}
        call(['release','download',release['tag_name'],'--repo',REPO,'--pattern',manifest['archive'],'--dir',str(stage)])
        backup=apply_archive(root,plugin,data,stage/manifest['archive'],manifest['sha256'])
        return {'status':'updated','message':'Auto-Cut aggiornato a '+manifest['version']+'; Resolve resta aperto.','backup':backup}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--app-root',type=Path,required=True);parser.add_argument('--plugin-root',type=Path,required=True);parser.add_argument('--data-root',type=Path,required=True)
    args=parser.parse_args()
    try:result=update(args.app_root,args.plugin_root,args.data_root)
    except Exception as exc:result={'status':'failed','message':str(exc)}
    from .atomic_io import write_json
    write_json(args.data_root/'update-status.json',result)
    print(json.dumps(result,ensure_ascii=True))
if __name__=='__main__':main()
