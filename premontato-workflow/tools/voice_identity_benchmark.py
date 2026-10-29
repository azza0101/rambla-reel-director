"""Reproduce local voice evaluation on a private source/unit fixture.
This reports agreement with supplied labels, not human-annotated accuracy.
No footage, transcript or embeddings are sent over a network.
"""
import argparse,json,os,sys,time
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--model',required=True);parser.add_argument('--dependencies');parser.add_argument('--cache',required=True);parser.add_argument('--private-output');parser.add_argument('--diarization-runtime');parser.add_argument('--diarization-model');parser.add_argument('--diarization-device',choices=['cpu','cuda','cuda:0'],default='cpu');parser.add_argument('--diarization-cache');args=parser.parse_args()
if bool(args.diarization_runtime)!=bool(args.diarization_model):parser.error('Specify both diarization runtime and model')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
if args.dependencies:sys.path.insert(0,args.dependencies)
os.environ['PREMONTATO_VOICE_MODEL']=args.model;os.environ['PREMONTATO_CACHE_DIR']=args.cache
from voice_identity import source_voices,MODEL_SHA256
fixture=json.loads(Path(args.input).read_text(encoding='utf-8-sig'));started=time.perf_counter();result=source_voices(fixture['source'],fixture['units'])
if args.diarization_runtime:
 from diarization import NemotronDiarizer
 from voice_fusion import enhance_source_voices
 secondary=NemotronDiarizer(args.diarization_runtime,args.diarization_model,device=args.diarization_device,cache_root=args.diarization_cache or str(Path(args.cache)/'diarization'))
 result=enhance_source_voices(fixture['source'],result,diarizer=secondary)
 by_id={u['id']:u for u in result['units']}
 result['validation']=[{**v,'voice':by_id[v['unit_id']]['voice'],'status':'identified' if by_id[v['unit_id']]['voice'] else 'unknown'} for v in result['validation']]
identified=[r for r in result['validation'] if r['status']=='identified'];focus={u['id'] for u in fixture.get('focus_units',fixture['units'])};focused=[u for u in result['units'] if u['id'] in focus]
summary={'model_sha256':MODEL_SHA256,'seconds':time.perf_counter()-started,'anchors':len(result['validation']),'identified_anchors':len(identified),'agreed_labels':sum(r['voice']==r['expected'] for r in identified),'unknown_anchors':len(result['validation'])-len(identified),'focus_units':len(focused),'identified_focus_units':sum(u['voice'] is not None for u in focused),'cache':result['telemetry'],'metric':'agreement_with_supplied_resolve_labels_not_human_ground_truth'}
if args.diarization_runtime:summary['diarization']=result['diarization']
if args.private_output:Path(args.private_output).write_text(json.dumps({'summary':summary,**result},ensure_ascii=False),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
