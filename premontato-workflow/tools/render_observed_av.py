"""Render a local diagnostic preview from an independent-AV observed plan.

No cloud, media mutation, or agent-authored camera plan. Temporary renders live
next to the output and are removed on exit. Requires the user's existing FFmpeg.
"""
import argparse,json,subprocess,tempfile
from pathlib import Path


def render(plan,output,ffmpeg,codec='libx264'):
 av=plan['av_plan'];fps=plan['fps'];total=av['duration_frames']
 if total<=0:raise ValueError('Piano vuoto')
 for kind in ('audio_spine','video_spine'):
  clock=0
  for d in av[kind]:
   if d['record_frame']!=clock or d['start_frame']<0 or d['end_frame']<=d['start_frame']:raise ValueError('Traccia non contigua')
   if not Path(d['path']).is_file():raise ValueError('Sorgente assente')
   clock+=d['end_frame']-d['start_frame']
  if clock!=total:raise ValueError('Durata tracce differente')
 output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
 def run(args):
  p=subprocess.run([str(ffmpeg),'-hide_banner','-loglevel','error','-nostdin','-y',*args],capture_output=True,timeout=180,creationflags=0x08000000 if __import__('os').name=='nt' else 0)
  if p.returncode:raise RuntimeError(p.stderr.decode('utf8',errors='replace')[-2000:])
 with tempfile.TemporaryDirectory(prefix='av-preview-',dir=output.parent) as folder:
  folder=Path(folder)
  for kind in ('audio','video'):
   files=[];items=av[kind+'_spine']
   for i,d in enumerate(items):
    target=folder/(kind+str(i)+('.wav' if kind=='audio' else '.mkv'));length=d['end_frame']-d['start_frame']
    args=['-ss',str(d['start_frame']/fps),'-i',d['path']]
    if kind=='audio':args+=['-vn','-t',str(length/fps),'-ac','1','-ar','48000','-c:a','pcm_s16le']
    else:args+=['-an','-vf',f'scale=640:360,setsar=1,fps={fps}','-frames:v',str(length),'-c:v',codec,'-threads','2']
    run([*args,str(target)]);files.append(target)
    print(json.dumps({'phase':kind,'current':i+1,'total':len(items)}),flush=True)
   listing=folder/(kind+'.txt');listing.write_text('\n'.join("file '"+p.name+"'" for p in files),encoding='utf8')
   run(['-f','concat','-safe','0','-i',str(listing),'-c','copy',str(folder/(kind+('.wav' if kind=='audio' else '.mkv')))])
  run(['-i',str(folder/'video.mkv'),'-i',str(folder/'audio.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','96k','-t',str(total/fps),'-movflags','+faststart',str(output)])
 return {'output':str(output),'expected_frames':total,'expected_seconds':total/fps,'reactions':len(av['reactions']),'editorial_ready':av['editorial_ready']}


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('plan');p.add_argument('output');p.add_argument('--ffmpeg',required=True);p.add_argument('--codec',default='libx264');a=p.parse_args()
 print(json.dumps(render(json.loads(Path(a.plan).read_text(encoding='utf8')),a.output,a.ffmpeg,a.codec)),flush=True)
