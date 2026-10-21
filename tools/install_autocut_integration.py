"""Install the native Workflow Integration using the matching SDK shipped by Resolve."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import sys

FILES=('main.js','preload.js','source_adapter.js','loading.html','manifest.xml','package.json')


def paths_for_platform():
    if sys.platform=='darwin':
        support=Path('/Library/Application Support/Blackmagic Design/DaVinci Resolve')
        return support/'Workflow Integration Plugins',support/'Developer/Workflow Integrations/Examples/SamplePlugin/WorkflowIntegration.node'
    if os.name=='nt':
        support=Path(os.environ.get('PROGRAMDATA',r'C:\ProgramData'))/'Blackmagic Design/DaVinci Resolve/Support'
        return support/'Workflow Integration Plugins',support/'Developer/Workflow Integrations/Examples/SamplePlugin/WorkflowIntegration.node'
    raise RuntimeError('La Workflow Integration richiede Windows o macOS con Resolve Studio')


def install(app_root,plugin_root,data_root,*,python,sdk):
    app_root=Path(app_root).resolve();plugin_root=Path(plugin_root).resolve();data_root=Path(data_root).resolve()
    source=app_root/'tools'/'autocut_integration';sdk=Path(sdk).resolve();python=Path(python).resolve()
    if not python.is_file():raise RuntimeError('Runtime Python non disponibile')
    if not sdk.is_file():raise RuntimeError('SDK WorkflowIntegration.node non trovato nella installazione Resolve')
    for name in FILES:
        if not (source/name).is_file():raise RuntimeError('File plugin mancante: '+name)
    target=plugin_root/'com.rambla.autocut'
    if target.is_symlink() or target.resolve().parent!=plugin_root:raise RuntimeError('Destinazione plugin non valida')
    plugin_root.mkdir(parents=True,exist_ok=True);data_root.mkdir(parents=True,exist_ok=True)
    if target.is_dir():
        backup=data_root/'install-backups'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backup.mkdir(parents=True)
        for name in (*FILES,'runtime.json','WorkflowIntegration.node'):
            if (target/name).is_file():shutil.copy2(target/name,backup/name)
    target.mkdir(exist_ok=True)
    for name in FILES:shutil.copy2(source/name,target/name)
    shutil.copy2(sdk,target/'WorkflowIntegration.node')
    config={'app_root':str(app_root),'python':str(python),'data_root':str(data_root)}
    (target/'runtime.json').write_text(json.dumps(config,indent=2),'utf-8')
    return target


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--app-root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--plugin-root',type=Path)
    parser.add_argument('--data-root',type=Path)
    args=parser.parse_args();default_root,sdk=paths_for_platform()
    target=install(args.app_root,args.plugin_root or default_root,args.data_root or args.app_root.parent/'autocut-data',python=Path(sys.executable),sdk=sdk)
    print('Installato: '+str(target))
    print('Dopo riavvio Resolve: Workspace > Workflow Integrations > RMBL Auto-Cut')
    print('Non vengono modificati progetti o timeline.')
if __name__=='__main__':main()
