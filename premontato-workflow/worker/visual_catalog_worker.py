"""Optional dedicated local Qwen process. JSONL compatible with Session; no API keys."""
import sys,json,os,time,contextlib
from pathlib import Path
from scene_visual import scene_queries,rank_visual_scenes,role_queries,rank_visual_role,rank_visual_neighbors,VERSION
from cache import cache_key,read_cache,write_cache
MODEL=None
CONFIG=None
def analyze(payload,report):
 global MODEL,CONFIG
 config=payload['config'];queries=scene_queries(payload['scenes']);frames=payload['frames']
 root=Path(payload['cache_root']);modelpath=Path(config['model']);stamp=[str(modelpath.resolve()),(modelpath/'config.json').stat().st_mtime_ns]
 weights=sorted(modelpath.glob('*.safetensors'));stamp.extend([(p.name,p.stat().st_size,p.stat().st_mtime_ns) for p in weights])
 def encode(items):
  global MODEL,CONFIG
  vectors=[]
  for i,item in enumerate(items):
   image='image' in item;identity=[item,stamp,VERSION]
   if image:
    s=Path(item['image']).stat();identity.extend([s.st_size,s.st_mtime_ns])
   key=cache_key(identity);cached=read_cache(root,key)
   if cached:vectors.append(cached['value']);report({'label':'Embedding visivo riusato dalla cache','current':i+1,'total':len(items)});continue
   if MODEL is None:
    report({'label':'Carico Qwen visivo locale','current':0,'total':len(items)})
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1';os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
    sys.path.insert(0,config['deps']);sys.path.insert(0,config['code'])
    with contextlib.redirect_stdout(sys.stderr):
     import torch
     from src.models.qwen3_vl_embedding import Qwen3VLEmbedder
     MODEL=Qwen3VLEmbedder(model_name_or_path=str(modelpath),local_files_only=True,dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,max_pixels=224*224,max_length=2048)
    CONFIG=config
   if CONFIG!=config:raise ValueError('Vision configuration changed: restart required')
   with contextlib.redirect_stdout(sys.stderr):v=MODEL.process([item]).detach().float().cpu().tolist()[0]
   write_cache(root,key,v);vectors.append(v);report({'label':'Confronto frame e descrizioni del copione','current':i+1,'total':len(items)})
  return vectors
 texts=encode([{'text':q['text']} for q in queries]);images=encode([{'image':f['path']} for f in frames])
 roles=role_queries();role=rank_visual_role(roles,encode([{'text':q['text']} for q in roles]),images)
 result=rank_visual_scenes(queries,texts,images,[f['frame'] for f in frames]);result['visual_role']=role;result['category']=role['category']
 if role['category']=='broll':result.update(scene_id=None,reason='VISUAL_BROLL')
 references=[]
 if role['category']!='broll':
  for ref in payload.get('references',[]):references.append({**ref,'vectors':encode([{'image':f['path']} for f in ref['frames']])})
 result['neighbors']=rank_visual_neighbors(images,references)
 result['model']='Qwen3-VL-Embedding-2B';result['frame_count']=len(frames);return result

def main():
 for line in sys.stdin:
  try:
   request=json.loads(line);rid=request['request_id']
   def report(event):print(json.dumps({'protocol':1,'request_id':rid,'status':'progress','result':event}),flush=True)
   start=time.monotonic();result=analyze(request['payload'],report);result['elapsed_ms']=round((time.monotonic()-start)*1000)
   response={'protocol':1,'request_id':rid,'status':'ok','result':result}
  except Exception as error:response={'protocol':1,'request_id':request.get('request_id','?'),'status':'error','error':{'message':str(error)}}
  print(json.dumps(response),flush=True)
if __name__=='__main__':main()
