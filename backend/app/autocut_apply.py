"""One explicit Apply operation using the already tested native CUT implementation."""
import json
import os
from pathlib import Path
import sys


def connect():
    if sys.platform=='darwin':
        api=Path('/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting')
        os.environ.setdefault('RESOLVE_SCRIPT_API',str(api))
        os.environ.setdefault('RESOLVE_SCRIPT_LIB','/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so')
    else:
        api=Path(os.environ.get('PROGRAMDATA',r'C:\ProgramData'))/'Blackmagic Design/DaVinci Resolve/Support/Developer/Scripting'
        os.environ.setdefault('RESOLVE_SCRIPT_API',str(api))
        os.environ.setdefault('RESOLVE_SCRIPT_LIB',r'C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll')
    sys.path.insert(0,str(api/'Modules'))
    import DaVinciResolveScript as dvr
    resolve=dvr.scriptapp('Resolve')
    if not resolve:raise RuntimeError('Resolve non risponde allo scripting. Verifica Studio / scripting Local.')
    return resolve


def apply_payload(resolve,payload,progress=lambda *args:None):
    from .resolve_native_cut import create_native_cut_base
    from .native_cut_export import validate_native_cut
    validate_native_cut(payload['native_cut'])
    manager=resolve.GetProjectManager();project=manager.GetCurrentProject()
    context=payload['context']
    if not project or project.GetName()!=context['project_name']:raise RuntimeError('Progetto Resolve cambiato: nessun taglio applicato')
    timeline=project.GetCurrentTimeline()
    if not timeline or timeline.GetUniqueId()!=context['timeline_id']:raise RuntimeError('Timeline Resolve cambiata: nessun taglio applicato')
    if payload.get('check_only'):
        from .autocut_reapply import inspect_timeline
        return inspect_timeline(timeline,payload['native_cut'])
    destination=payload.get('destination','new')
    if destination not in ('new','active'):raise ValueError('Destinazione CUT non valida')
    options={'target':timeline} if destination=='active' else {}
    if destination=='active' and payload.get('timeline_signature'):options['expected_signature']=payload['timeline_signature']
    if destination=='active' and payload.get('allow_modified'):options['allow_modified']=True
    engine_payload={key:payload[key] for key in ('native_cut','subtitle_rows','subtitle_path') if key in payload}
    result=create_native_cut_base(resolve,project,engine_payload,progress=progress,**options)
    return {key:value for key,value in result.items() if key!='timeline'}


def main():
    def emit(value):print(json.dumps(value,ensure_ascii=True),flush=True)
    try:
        payload=json.load(sys.stdin)
        result=apply_payload(connect(),payload,lambda percent,message:emit({'type':'progress','percent':percent,'message':message}))
        emit({'type':'result','result':result})
    except Exception as exc:
        emit({'type':'error','message':str(exc)})
        raise SystemExit(1)
if __name__=='__main__':main()
