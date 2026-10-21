"""Build a credential-free code-only Auto-Cut update; no runtime or native SDK."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.autocut_update import allowed, PLUGIN_FILES


def build(root,output):
    root=Path(root).resolve();output=Path(output);output.mkdir(parents=True,exist_ok=True)
    version=json.loads((root/'tools/autocut_integration/package.json').read_text('utf-8'))['version']
    archive=output/('RMBL-AutoCut-'+version+'.zip')
    files=[root/'pyproject.toml',root/'RAMBLA_VERSION',*sorted((root/'backend/app').rglob('*.py')),*[root/'tools/autocut_integration'/name for name in sorted(PLUGIN_FILES)]]
    if (root/'backend/__init__.py').is_file():files.append(root/'backend/__init__.py')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for file in files:
            name=file.relative_to(root).as_posix()
            if not allowed(name):raise ValueError('Unexpected managed file')
            z.writestr(name,file.read_bytes())
    manifest={'version':version,'archive':archive.name,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'restart':'integration-only','native_sdk_included':False}
    (output/'autocut-update.json').write_text(json.dumps(manifest,indent=2),'utf-8')
    return manifest
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('dist/autocut'));args=parser.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[1],args.output)))
