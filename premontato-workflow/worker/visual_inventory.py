"""Bounded local single-frame evidence. Never identifies voices or completed gestures."""
import base64,json,math,os,subprocess,time,socket,urllib.request,urllib.error,re
from pathlib import Path
from cache import get_or_compute

PROMPT='Inspect the whole image, including foreground and partially visible people. List handheld objects separately from visible faces. Blur may prevent naming an object without preventing detecting its presence. Do not infer speech or movement. Return JSON {"held_objects":[{"region":"foreground|middle|background","type":"food|tool|document|device|container|other|uncertain","evidence":"max 12 words describing the actual object"}]}. Use an empty held_objects list if no handheld object is visibly present. Objects on shelves are background props, not handheld objects. Do not assign an owner: identity requires separate evidence.'
VERSION='frame-inventory-v1'

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise urllib.error.URLError('Redirect del motore visivo non consentito')

def parse_response(response):
 if not isinstance(response,dict) or not isinstance(response.get('choices'),list) or not response['choices']:raise ValueError('Risposta visiva senza scelte')
 choice=response['choices'][0]
 if not isinstance(choice,dict) or choice.get('finish_reason')!='stop' or not isinstance(choice.get('message'),dict) or not isinstance(choice['message'].get('content'),str):raise ValueError('Risposta visiva incompleta')
 value=json.loads(choice['message']['content'])
 if not isinstance(value,dict):raise ValueError('Inventario visivo non strutturato')
 return value

def sample_frames(start,end,count=3):
 if type(start) is not int or type(end) is not int or not 0<=start<end or type(count) is not int or not 1<=count<=12:raise ValueError('Campioni inventario non validi')
 return sorted(set(round(start+(end-start-1)*i/max(1,count-1)) for i in range(count)))

def normalize_inventory(raw,frame):
 if type(frame) is not int or frame<0 or not isinstance(raw,dict) or not isinstance(raw.get('held_objects'),list) or len(raw['held_objects'])>8:raise ValueError('Inventario visivo non valido')
 objects=[]
 for obj in raw['held_objects']:
  if not isinstance(obj,dict) or obj.get('region') not in ('foreground','middle','background') or obj.get('type') not in ('food','tool','document','device','container','other','uncertain') or not isinstance(obj.get('evidence'),str):raise ValueError('Oggetto visivo non valido')
  objects.append({'region':obj['region'],'type':obj['type'],'evidence':obj['evidence'][:200],'owner':'unverified'})
 return {'frame':frame,'objects':objects,'speaker_verified':False,'owner_verified':False}

def summarize(samples):
 changes=[]
 for a,b in zip(samples,samples[1:]):
  if bool(a['objects'])!=bool(b['objects']):changes.append({'from_frame':a['frame'],'to_frame':b['frame'],'kind':'becomes_visible' if b['objects'] else 'no_longer_visible'})
 known=sum(any(o['type'] not in ('other','uncertain') for o in s['objects']) for s in samples)
 return {'sample_count':len(samples),'presence_fraction':sum(bool(s['objects']) for s in samples)/max(1,len(samples)),'known_object_fraction':known/max(1,len(samples)),'changes':changes,'gesture_completion_verified':False,'speaker_verified':False,'owner_verified':False}

class LocalInventory:
 """Own a loopback-only model process; reuse existing executables and weights."""
 def __init__(self,config,cache_root):
  self.config=config;self.root=Path(cache_root)/'visual-inventory';self.process=None;self.log=None;self.start_failed=False
  self.model_stamp=None
  self.http=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
 def _stamp(self):
  if self.model_stamp is None:
   stamp=[]
   for key in ('server','model','projection'):
    p=Path(self.config[key]);s=p.stat();stamp.append([str(p.resolve()),s.st_size,s.st_mtime_ns])
   self.model_stamp=stamp
  return self.model_stamp
 def __enter__(self):
  return self
 def _start(self):
  self.root.mkdir(parents=True,exist_ok=True)
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  self.url=f'http://127.0.0.1:{port}';self.log=open(self.root/'server.log','ab')
  c=self.config
  try:
   self.process=subprocess.Popen([c['server'],'-m',c['model'],'--mmproj',c['projection'],'--host','127.0.0.1','--port',str(port),'-ngl','99','-c','8192','-np','1','--threads','4','--image-max-tokens','512'],stdout=self.log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   deadline=time.monotonic()+60
   while time.monotonic()<deadline:
    if self.process.poll() is not None:raise RuntimeError('Motore visivo locale terminato')
    try:
     with self.http.open(self.url+'/health',timeout=1) as r:
      if r.status==200:return self
    except OSError:pass
    time.sleep(.25)
   raise TimeoutError('Avvio motore visivo locale scaduto')
  except Exception:self.close();raise
 def close(self):
  if self.process is not None:
   if self.process.poll() is None:
    self.process.terminate()
    try:self.process.wait(timeout=8)
    except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
   self.process=None
  if self.log is not None:self.log.close();self.log=None
 def __exit__(self,*args):self.close()
 def infer(self,jpeg):
  if self.start_failed:raise RuntimeError('Motore visivo locale non disponibile in questa analisi')
  if self.process is None:
   try:self._start()
   except Exception:self.start_failed=True;raise
  if self.process is None or self.process.poll() is not None:raise RuntimeError('Motore visivo non disponibile')
  body={'model':'local','messages':[{'role':'user','content':[{'type':'text','text':PROMPT},{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(jpeg).decode()}}]}],'temperature':0,'max_tokens':350,'response_format':{'type':'json_object'},'chat_template_kwargs':{'enable_thinking':False}}
  req=urllib.request.Request(self.url+'/v1/chat/completions',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
  with self.http.open(req,timeout=45) as r:
   if r.geturl()!=self.url+'/v1/chat/completions':raise RuntimeError('Redirect del motore visivo non consentito')
   response=json.load(r)
  return parse_response(response)
 def observe(self,source,frame):
  if type(frame) is not int or not 0<=frame<source['duration_frames'] or not math.isfinite(source['fps']) or source['fps']<=0:raise ValueError('Frame fuori sorgente')
  p=Path(source['path']);st=p.stat();stamp=[str(p.resolve()),st.st_size,st.st_mtime_ns]
  def compute():
   ffmpeg=self.config.get('ffmpeg') or r'C:\Program Files\FFmpeg\ffmpeg.exe'
   image=subprocess.check_output([ffmpeg,'-nostdin','-v','error','-ss',str(frame/source['fps']),'-i',str(p),'-frames:v','1','-vf','scale=640:360:force_original_aspect_ratio=decrease','-f','image2pipe','-c:v','mjpeg','pipe:1'],stderr=subprocess.DEVNULL,timeout=45,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   return normalize_inventory(self.infer(image),frame)
  value,hit=get_or_compute(self.root,stamp,VERSION,{'frame':frame,'fps':source['fps'],'duration':source['duration_frames'],'model':self._stamp(),'prompt':PROMPT},compute)
  return {**value,'cache_hit':hit}

def analyze_inventory(payload,report=None):
 source=payload['source'];frames=payload.get('frames') or sample_frames(payload['start_frame'],payload['end_frame'])
 if not isinstance(frames,list) or not 1<=len(frames)<=24 or frames!=sorted(set(frames)):raise ValueError('Limite inventario: 24 frame distinti ordinati')
 rows=[];errors=[];root=payload.get('cache_root') or os.environ.get('PREMONTATO_CACHE_DIR','.premontato-cache')
 with LocalInventory(payload['config'],root) as client:
  for i,frame in enumerate(frames):
   if report:report({'phase':'visual_inventory','current':i,'total':len(frames),'label':'Controllo oggetti separato dai volti'})
   try:rows.append(client.observe(source,frame))
   except (OSError,ValueError,RuntimeError,KeyError,subprocess.SubprocessError) as error:errors.append({'frame':frame,'kind':type(error).__name__})
 if report:report({'phase':'visual_inventory','current':len(frames),'total':len(frames),'label':'Controllo visivo completato'})
 return {'samples':rows,'errors':errors,'complete':not errors,'summary':summarize(rows),'status':'ready' if not errors else 'incomplete'}

def annotate_candidates(candidate_sets,sources,config,cache_root,report=None,max_frames=12):
 """Only inspect grounded speaker candidates for object-related dialogue."""
 if type(max_frames) is not int or not 0<=max_frames<=48:raise ValueError('Budget visivo non valido')
 by={s['media_id']:s for s in sources};used=0;hits=0;errors=[];started=time.perf_counter()
 if max_frames==0:return {'frames':0,'cache_hits':0,'errors':[],'seconds':0.,'maximum_frames':0}
 with LocalInventory(config,cache_root) as client:
  for choices in candidate_sets:
   relevant=bool(re.search(r'\b(quest[oaie]|guarda|mostra\w*|prend\w*|pos[ao]\w*|prodotto|oggetto|this|show|hold|object)\b',choices[0].get('text',''),re.I))
   if not relevant:continue
   eligible=[c for c in choices if c.get('speaker_visible')]
   needed=sum(len(sample_frames(c['start_frame'],c['end_frame'])) for c in eligible)
   if len(eligible)<2 or used+needed>max_frames:continue
   for c in choices:
    c['object_required']=True
    if not c.get('speaker_visible'):continue
    samples=[];failed=[]
    for frame in sample_frames(c['start_frame'],c['end_frame']):
     if report:report({'phase':'visual_inventory','current':used,'total':max_frames,'label':'Verifico oggetti nel campo candidato'})
     used+=1
     try:
      row=client.observe(by[c['media_id']],frame);samples.append(row);hits+=int(row['cache_hit'])
     except (OSError,ValueError,RuntimeError,KeyError,subprocess.SubprocessError) as e:failed.append({'frame':frame,'kind':type(e).__name__})
    c['visual_inventory']={'complete':not failed,'samples':samples,'summary':summarize(samples),'errors':failed};errors.extend(failed)
 if report:report({'phase':'visual_inventory','current':used,'total':used,'label':'Inventario candidati completato'})
 return {'frames':used,'cache_hits':hits,'errors':errors,'seconds':time.perf_counter()-started,'maximum_frames':max_frames}
