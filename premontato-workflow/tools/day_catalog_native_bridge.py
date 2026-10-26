import sys,json
sys.path.insert(0,r'C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules')
import DaVinciResolveScript as d
resolve=d.scriptapp('Resolve')
assert resolve
objects={0:resolve}
def encode(value):
    if value is None or isinstance(value,(str,int,float,bool)): return value
    if isinstance(value,(list,tuple)):return [encode(v) for v in value]
    if isinstance(value,dict):return {str(k):encode(v) for k,v in value.items()}
    key=len(objects);objects[key]=value;return {'__handle__':key}
def decode(value):
    if isinstance(value,dict):
        if set(value)=={'__handle__'}:return objects[value['__handle__']]
        return {k:decode(v) for k,v in value.items()}
    if isinstance(value,list):return [decode(v) for v in value]
    return value
def walk(folder):
    clips=list(folder.GetClipList() or [])
    for sub in folder.GetSubFolderList() or []:clips.extend(walk(sub))
    return clips
for line in sys.stdin:
    try:
        req=json.loads(line);obj=objects[req['object']]
        value=getattr(obj,req['method'])(*decode(req.get('args',[])))
        out={'id':req['id'],'result':encode(value)}
    except Exception as error:out={'id':req.get('id'),'error':str(error)}
    print(json.dumps(out),flush=True)
