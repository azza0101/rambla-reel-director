'use strict';
const fs = require('node:fs/promises');
const path = require('node:path');
const { spawn } = require('node:child_process');
const connectorPath=[path.join(__dirname,'runtime','premontato','groq_client.js'),path.join(__dirname,'..','runtime','premontato','groq_client.js')].find(p=>require('node:fs').existsSync(p));
const {GroqClient}=require(path.join(path.dirname(connectorPath),'local_gemma')); 
const catalogEdit=require(path.join(path.dirname(connectorPath),'catalog_edit_context'));
const automaticEditing=require(path.join(path.dirname(connectorPath),'automatic_editing'));


const DEFAULT_DIRECTIONS={profile:'VIDEO COLICHE',notes:'Aprire con la master per il contesto. Privilegiare i primi piani verificati di chi parla; tornare alla master soprattutto negli scambi lunghi, su un cambio di parlante, o al rilascio della tensione. Evitare alternanze a conteggio fisso. Durante tensione e crescendo mantenere le strette fino al sollievo o alla risoluzione. Aprire sulla larga per distendere. Esempio: dopo l’invito a dormire nel suo letto, primo piano di lui prima dello sbotto, larga quando rifiuta. La reazione richiede copertura verificata: non viene inventata.',markers:{}};
function validateDirections(value){
 if(!value || typeof value!=='object' || Array.isArray(value) || !['none','VIDEO COLICHE'].includes(value.profile) || typeof value.notes!=='string' || value.notes.length>20000 || !value.markers || typeof value.markers!=='object' || Array.isArray(value.markers) || Object.keys(value.markers).length>10000 || Object.entries(value.markers).some(([id,role])=>!id || id.length>128 || !['tension','resolution','free'].includes(role)))throw new Error('Direzioni di montaggio non valide');
 return JSON.parse(JSON.stringify(value));
}

function validateDraft(value){
 const obj=v=>v && typeof v==='object' && !Array.isArray(v),str=v=>typeof v==='string',list=(v,check)=>Array.isArray(v) && v.length<=10000 && v.every(check),scalar=v=>str(v)||Number.isFinite(v),sizes=['wide','medium','close','detail','unknown'];
 if(!obj(value) || Buffer.byteLength(JSON.stringify(value))>512*1024 || value.takes!==undefined && !list(value.takes,v=>obj(v)&&str(v.take_id)&&scalar(v.start_frame)&&scalar(v.end_frame)) || value.beats!==undefined && !list(value.beats,v=>obj(v)&&str(v.beat_id)&&scalar(v.start)&&scalar(v.end)&&sizes.includes(v.scale)))throw new Error('Bozza progetto non valida');
 if(value.visual!==undefined && (!obj(value.visual) || value.visual.dirty!==undefined && typeof value.visual.dirty!=='boolean' || value.visual.person_names!==undefined && (!obj(value.visual.person_names)||!Object.values(value.visual.person_names).every(str)) || value.visual.intervals!==undefined && !list(value.visual.intervals,v=>obj(v)&&str(v.segment_id)&&sizes.includes(v.shot_size)&&list(v.visible_subjects,str))))throw new Error('Bozza visiva del progetto non valida');
 if(value.interfaceMode!==undefined && !['scene','catalog'].includes(value.interfaceMode))throw Error('Modalità progetto non valida');
 if(value.sceneDebug!==undefined && typeof value.sceneDebug!=='boolean')throw Error('Opzione debug scene non valida');
 if(value.directions!==undefined)validateDirections(value.directions);
 if(value.pacing!==undefined && (!obj(value.pacing)||typeof value.pacing.enabled!=='boolean'||typeof value.pacing.script!=='boolean'||!scalar(value.pacing.gap)||!scalar(value.pacing.minimum)))throw new Error('Bozza ritmo non valida');
}
function validateProjectState(state){
 const fail=()=>{throw new Error('Campi del progetto Premontato non validi');},obj=v=>v&&typeof v==='object'&&!Array.isArray(v),str=v=>typeof v==='string',int=v=>Number.isSafeInteger(v)&&v>=0;
 const array=(v,check,optional=false)=>{if(v===undefined&&optional)return;if(!Array.isArray(v)||v.length>100000||!v.every(check))fail();};
 if(!obj(state)||!Array.isArray(state.media))fail();const media=new Map();
 for(const item of state.media){if(!obj(item)||!str(item.media_id)||media.has(item.media_id)||!int(item.duration_frames)||!item.duration_frames||!str(item.path)||item.name!==undefined&&!str(item.name))fail();media.set(item.media_id,item);}
 if(state.script!==null&&state.script!==undefined&&(!obj(state.script)||!str(state.script.text)||!str(state.script.path)))fail();
 for(const key of ['projectId','timelineId'])if(state[key]!==undefined&&!str(state[key]))fail();
 const range=(row,bounds)=>obj(row)&&int(row.start_frame)&&int(row.end_frame)&&row.end_frame>row.start_frame&&row.end_frame<=bounds;
 const beat=row=>obj(row)&&str(row.beat_id)&&str(row.kind)&&str(row.text)&&(row.character===undefined||row.character===null||str(row.character));
 const scene=row=>obj(row)&&str(row.heading)&&Array.isArray(row.beats)&&row.beats.every(beat);
 // Earlier Resolve imports retained nonspoken '(...)' rows at frame -1. Drop only
 // punctuation placeholders; malformed spoken timing still fails validation.
 for(const sources of [state.transcripts,state.analysis?.planningSources])if(Array.isArray(sources))for(const source of sources)if(Array.isArray(source?.segments))source.segments=source.segments.filter(segment=>typeof segment?.text!=='string'||/[\p{L}\p{N}]/u.test(segment.text));
 const sizes=['wide','medium','close','detail','unknown'];
 const decision=(row,alt=false)=>{
  if(!obj(row)||!media.has(row.media_id)||!str(row.take_id)||!alt&&!str(row.beat_id)||!range(row,media.get(row.media_id)?.duration_frames))return false;
  for(const key of ['score','confidence','coverage','semantic_score','shot_confidence'])if(row[key]!==undefined&&row[key]!==null&&!Number.isFinite(row[key]))return false;
  if(row.shot_size!==undefined&&!sizes.includes(row.shot_size)||row.matched_text!==undefined&&!str(row.matched_text))return false;
  if(row.reaction_enabled!==undefined && typeof row.reaction_enabled!=='boolean')return false;
  if(row.reaction_before!==undefined){try{require('./ipc_security').validateReaction(row.reaction_before,media.get(row.reaction_before?.media_id));}catch{return false;}}
  if(row.reaction_overlay!==undefined){try{require('./ipc_security').validateOverlay(row.reaction_overlay,row,media.get(row.reaction_overlay?.media_id));}catch{return false;}}
  if(row.action_after!==undefined){if(!Array.isArray(row.action_after) || row.action_after.length>100)return false;try{for(const action of row.action_after)require('./ipc_security').validateAction(action,media.get(action?.media_id));}catch{return false;}}
  if(row.alternatives===undefined && !alt)row.alternatives=[];
  if(row.alternatives!==undefined&&(!Array.isArray(row.alternatives)||!row.alternatives.every(value=>decision(value,true))))return false;
  if(row.source_ranges!==undefined&&(!Array.isArray(row.source_ranges)||!row.source_ranges.every(value=>range(value,row.end_frame)&&value.start_frame>=row.start_frame)))return false;
  if(row.warnings!==undefined&&(!Array.isArray(row.warnings)||!row.warnings.every(str)))return false;return true;
 };
 const shot=row=>obj(row)&&media.has(row.media_id)&&str(row.segment_id)&&range(row,media.get(row.media_id)?.duration_frames)&&sizes.includes(row.shot_size)&&(row.visible_subjects===undefined||Array.isArray(row.visible_subjects)&&row.visible_subjects.every(str));
 const source=row=>obj(row)&&media.has(row.media_id)&&(row.path===undefined||row.path===media.get(row.media_id).path)&&Array.isArray(row.segments)&&row.segments.every(segment=>obj(segment)&&str(segment.text)&&range(segment,media.get(row.media_id).duration_frames)&&(segment.words===undefined||Array.isArray(segment.words)&&segment.words.every(word=>obj(word)&&str(word.text)&&int(word.start_frame)&&int(word.end_frame)&&word.end_frame>=word.start_frame&&word.end_frame<=media.get(row.media_id).duration_frames)));
 if(state.directions!==undefined)validateDirections(state.directions);
 if(state.pacingSettings!==undefined&&!obj(state.pacingSettings))fail();state.pacingSettings={enabled:true,max_pause_seconds:.45,minimum_shot_seconds:1.2,respect_script_pauses:true,comic_hold_seconds:1,...state.pacingSettings};for(const key of ['enabled','respect_script_pauses'])if(typeof state.pacingSettings[key]!=='boolean')fail();for(const key of ['max_pause_seconds','minimum_shot_seconds','comic_hold_seconds'])if(!Number.isFinite(state.pacingSettings[key])||state.pacingSettings[key]<0)fail();
 array(state.transcripts,source,true);if(state.uiDraft!==undefined&&state.uiDraft!==null)validateDraft(state.uiDraft);
 const analysis=state.analysis;if(analysis===null||analysis===undefined)return;if(!obj(analysis))fail();
 array(analysis.parsedBeats,beat,true);if(analysis.shots===undefined)analysis.shots=[];array(analysis.shots,shot);array(analysis.planningSources,source,true);array(analysis.warnings,str,true);
 if(analysis.selectedScene!==undefined&&analysis.selectedScene!==null&&!scene(analysis.selectedScene))fail();
 if(analysis.script!==undefined&&(!obj(analysis.script)||!Array.isArray(analysis.script.scenes)||!analysis.script.scenes.every(scene)))fail();
 if(analysis.plan!==undefined&&analysis.plan!==null){if(!obj(analysis.plan))fail();array(analysis.plan.decisions,v=>decision(v));array(analysis.plan.base_decisions,v=>decision(v),true);if(analysis.plan.unmatched_beats===undefined)analysis.plan.unmatched_beats=[];array(analysis.plan.unmatched_beats,str);if(analysis.plan.pacing_summary!==undefined){const summary=analysis.plan.pacing_summary;if(!obj(summary))fail();if(summary.unavailable_media===undefined)summary.unavailable_media=[];array(summary.unavailable_media,str);}}
 array(analysis.takes,group=>obj(group)&&media.has(group.media_id)&&str(group.media_name)&&int(group.duration_frames)&&group.duration_frames===media.get(group.media_id).duration_frames&&Array.isArray(group.segments)&&group.segments.every(segment=>obj(segment)&&str(segment.take_id)&&int(segment.take_index)&&range(segment,group.duration_frames)),true);
 const review=analysis.visualReview;if(review!==undefined&&review!==null){if(!obj(review))fail();array(review.intervals,row=>shot(row)&&Array.isArray(row.stills)&&row.stills.every(still=>obj(still)&&int(still.frame)&&still.frame>=row.start_frame&&still.frame<row.end_frame&&str(still.image)&&Array.isArray(still.face_ids)&&still.face_ids.every(str)));array(review.faces,face=>obj(face)&&str(face.observation_id)&&(face.person_id===null||str(face.person_id))&&int(face.face_number)&&str(face.thumbnail));if(review.personNames!==undefined&&(!obj(review.personNames)||!Object.values(review.personNames).every(str)))fail();}
}

function workerEnvironment(source = process.env, cachePath) {
  const result = { PREMONTATO_CACHE_DIR: cachePath };
  for (const key of ['PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'USERPROFILE', 'LOCALAPPDATA', 'HOMEDRIVE', 'HOMEPATH']) {
    if (source[key]) result[key] = source[key];
  }
  return result;
}

function prepareReviewTimeline(plan, confirmed, allowIncomplete=false) {
  if (confirmed !== true) throw new Error('Conferma gli abbinamenti prima di creare la timeline');
  if(plan?.ready_for_timeline===false&&allowIncomplete!==true)throw new Error('Montaggio incompleto: scegli esplicitamente la creazione di una bozza');
  if (plan?.visual_review_required) throw new Error('Conferma le inquadrature e i personaggi nella revisione visiva');
  if (!plan?.decisions?.length) throw new Error('Nessuna battuta abbinata: timeline non creata');
  return { decisions: plan.decisions, omitted: plan.unmatched_beats?.length || 0, ...(plan.ready_for_timeline===false?{partial:true}:{}) };
}


// Resolve scene boundaries only from script beat identity; never from camera changes.
function annotateSceneEdits(analysis, decisions) {
 const scenes=analysis?.script?.scenes || [], byBeat=new Map();
 scenes.forEach((scene,index)=>{for(const beat of scene.beats || [])byBeat.set(beat.beat_id,{id:scene.scene_id,number:index+1,heading:scene.heading});});
 return decisions.map(edit=>{
  const scene=byBeat.get(edit.beat_id);
  if(!scene?.id)throw Error('Scena del taglio non identificabile: ricalcola il piano oppure disattiva il debug scene');
  return {...edit,scene_debug:scene,...(edit.reaction_before?{reaction_before:{...edit.reaction_before,scene_debug:scene}}:{}),...(edit.action_after?{action_after:edit.action_after.map(action=>({...action,scene_debug:byBeat.get(action.beat_id) || scene}))}:{})};
 });
}

class Session {
  constructor(root, workerPath, python = process.env.PREMONTATO_PYTHON || path.join(__dirname, 'runtime', 'python.exe')) {
    this.root = root; this.workerPath = workerPath; this.python = python;
    this.state = { directions:JSON.parse(JSON.stringify(DEFAULT_DIRECTIONS)), stage: 'idle', script: null, media: [], analysis: null, error: null, pacingSettings: { enabled: true, max_pause_seconds: .45, minimum_shot_seconds: 1.2, respect_script_pauses: true, comic_hold_seconds: 1 } };
    this.documentId=require('node:crypto').randomUUID(); this.projectFile=null; this.lastSavedAt=null; this.lastAutosaveAt=null; this.saveError=null;
    this.groq = new GroqClient(root);
    this.child = null; this.pending = new Map(); this.counter = 0;
  }
  async request(action, payload = {}, timeoutMs = 30000, onProgress) {
    if (!this.child) {
      this.child = spawn(this.python, ['-X', 'utf8', '-E', '-s', this.workerPath], { stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true,
        env: workerEnvironment(process.env, path.join(this.root, 'cache', 'shots')) });
      this.child.stdout.setEncoding('utf8'); let buffer = '';
      this.child.stdout.on('data', chunk => { buffer += chunk; let index; while ((index = buffer.indexOf('\n')) >= 0) { const line = buffer.slice(0, index); buffer = buffer.slice(index + 1); try { this.receive(JSON.parse(line)); } catch { this.failAll(new Error('Risposta worker non valida')); } } });
      this.child.stderr.setEncoding('utf8'); this.child.stderr.on('data', chunk => { this.lastWorkerLog = (this.lastWorkerLog || '').concat(chunk).slice(-4000); });
      this.child.on('error', error => this.failAll(error));
      this.child.on('exit', code => { this.child = null; if (code) this.failAll(new Error(`Worker terminato (${code})`)); });
    }
    const request_id = `req-${++this.counter}`;
    const promise = new Promise((resolve, reject) => {
      const timer = setTimeout(() => { this.pending.delete(request_id); reject(new Error('Timeout analisi locale')); }, timeoutMs);
      this.pending.set(request_id, { resolve, reject, timer, onProgress });
    });
    this.child.stdin.write(JSON.stringify({ protocol: 1, request_id, action, payload }) + '\n');
    return promise;
  }
  receive(message) {
    const task = this.pending.get(message.request_id); if (!task) return;
    if (message.status === 'progress') { task.onProgress?.(message.result); return; }
    clearTimeout(task.timer); this.pending.delete(message.request_id);
    message.status === 'ok' ? task.resolve(message.result) : task.reject(new Error(message.error?.message || 'Errore worker'));
  }
  failAll(error) { for (const task of this.pending.values()) { clearTimeout(task.timer); task.reject(error); } this.pending.clear(); }
  async prepareTimelineDebug(decisions,enabled,settings) {
    if(typeof enabled!=='boolean')throw Error('Opzione debug scene non valida');
    if(!enabled)return {decisions,sceneDebug:{enabled:false}};
    const annotated=annotateSceneEdits(this.state.analysis,decisions),frames=new Map();
    const add=row=>{const duration=(row.source_ranges || [row]).reduce((n,r)=>n+r.end_frame-r.start_frame,0);frames.set(row.scene_debug.number,(frames.get(row.scene_debug.number)||0)+duration);};
    for(const edit of annotated){if(edit.reaction_before && edit.reaction_enabled!==false && edit.reaction_before.enabled!==false)add(edit.reaction_before);add(edit);for(const action of edit.action_after || [])add(action);}
    const rendered=await this.request('render_scene_debug_titles',{...settings,scenes:[...frames].map(([number,frames])=>({number,frames}))},600000);
    return {decisions:annotated,sceneDebug:{enabled:true,gap_frames:Math.round(2*settings.fps),assets:rendered.assets}};
  }
  setIgnoredBeats(request) {
    if(this.retryingScene)throw Error('Attendi il ricontrollo in corso');
    const p=this.state.analysis?.plan,ids=request?.beat_ids;
    if(request?.scene_id){const job=p?.scene_jobs?.find(j=>j.scene_id===request.scene_id);if(!job||job.status==='ready'||job.missing?.length||typeof request.ignored!=='boolean')throw Error('Scena visiva non valida');const scenes=new Set(p.ignored_scenes||[]);request.ignored?scenes.add(job.scene_id):scenes.delete(job.scene_id);p.ignored_scenes=[...scenes];this.refreshIgnoredBeats(p);return this.getReviewState();}
    const missing=new Set(p?.scene_jobs?.flatMap(j=>j.missing||[])||[]);
    if(!p||typeof request?.ignored!=='boolean'||!Array.isArray(ids)||!ids.length||ids.length>10000||ids.some(id=>!missing.has(id)))throw Error('Puoi ignorare soltanto battute mancanti segnalate');
    const ignored=new Set(p.ignored_beats||[]);for(const id of ids)request.ignored?ignored.add(id):ignored.delete(id);
    p.ignored_beats=[...ignored];this.refreshIgnoredBeats(p);return this.getReviewState();
  }
  refreshIgnoredBeats(p) {
    const ignored=new Set(p.ignored_beats||[]);
    p.unmatched_beats=p.scene_jobs.flatMap(j=>j.missing||[]).filter(id=>!ignored.has(id));
    p.ready_for_timeline=!p.unmatched_beats.length&&!p.scene_jobs.some(j=>j.status==='failed'&&!(p.ignored_scenes||[]).includes(j.scene_id)&&!(j.missing?.length&&j.missing.every(id=>ignored.has(id))));
  }
  async retryScene(request) {
    const a=this.state.analysis,old=a?.plan,scenes=a?.script?.scenes||[];
    const scene=scenes.find(s=>s.scene_id===request?.scene_id);
    if(!scene||old?.engine!=='scene_jobs_v1'||!old.scene_jobs?.some(j=>j.scene_id===scene.scene_id))throw Error('Scena non disponibile per il ricontrollo');
    if(!['local','online'].includes(request.engine))throw Error('Motore di ricontrollo non valido');
    if(this.retryingScene)throw Error('Un ricontrollo scena è già in corso');
    this.retryingScene=true;const original=this.groq,nonce=original.retryNonce;
    try{
      if(request.engine==='online'){
        this.groq=new (require(connectorPath).GroqClient)(this.root,{vault:original.vault,fetchImpl:original.fetchImpl,diagnostic:original.diagnostic,keyProvider:original.keyProvider});
        const status=this.groq.status();if(!status.configured)throw Error('Fornitore online non configurato');this.groq.status=()=>({...status,enabled:true});
      }else if(this.groq.status().provider!=='local')throw Error('Gemma locale non attivo: selezionalo nelle impostazioni');
      this.groq.retryNonce=require('node:crypto').randomUUID();
      this.onProgress?.({phase:'plan',phaseIndex:6,percent:0,label:'Ricontrollo solo '+scene.heading});
      const routed=await this.request('route_scene_edits',{scenes,sources:a.planningSources,fps:this.state.fps||25},300000);
      const job=routed.jobs.find(j=>j.scene.scene_id===scene.scene_id);
      if(!job?.sources.length)throw Error('Nessun parlato attribuito a questa scena: le altre scene sono conservate');
      const part=await this.buildPlanCore({scene_id:scene.scene_id,beats:scene.beats,sources:job.sources,shots:a.shots||[],directions:this.state.directions,semantic:true,fps:this.state.fps||25},300000);
      const ids=new Set(scene.beats.map(b=>b.beat_id));
      const byBeat=new Map(scenes.flatMap(s=>s.beats.map(b=>[b.beat_id,s.scene_id])));
      const order=new Map(scenes.map((s,i)=>[s.scene_id,i]));
      const decisions=[...old.decisions.filter(d=>!ids.has(d.beat_id)),...part.decisions].map(d=>structuredClone(d)).sort((x,y)=>(order.get(byBeat.get(x.beat_id))??999)-(order.get(byBeat.get(y.beat_id))??999));
      let cursor=0;for(const d of decisions){d.timeline_start_frame=cursor;cursor+=d.end_frame-d.start_frame+(d.action_after||[]).reduce((n,x)=>n+x.end_frame-x.start_frame,0);}
      const jobs=old.scene_jobs.map(j=>j.scene_id===scene.scene_id?{scene_id:j.scene_id,heading:j.heading,status:part.unmatched_beats?.length?'incomplete':'ready',missing:part.unmatched_beats||[],decisions:part.decisions.length}:j);
      const plan={...old,decisions,base_decisions:structuredClone(decisions),review_beats:[...(old.review_beats||[]).filter(b=>!ids.has(b.beat_id)),...(part.review_beats||[])],unmatched_beats:jobs.flatMap(j=>j.missing||[]),scene_jobs:jobs,ready_for_timeline:!jobs.some(j=>j.status==='failed'||j.missing?.length),planning_summary:{...old.planning_summary,scene_jobs:jobs},warnings:[...(old.warnings||[]),...(part.warnings||[])]};
      this.refreshIgnoredBeats(plan);this.state.analysis={...a,plan};this.state.stage='review';this.state.uiDraft=null;
      this.onProgress?.({phase:'complete',phaseIndex:8,percent:100,label:'Ricontrollo completato: '+scene.heading});
      return this.getReviewState();
    }finally{original.retryNonce=nonce;this.groq=original;this.retryingScene=false;}
  }
  async selectScenes(request) {
    const analysis=this.state.analysis,scenes=analysis?.script?.scenes || [],ids=request?.scene_ids;
    if(!Array.isArray(ids) || !ids.length || ids.length>100 || new Set(ids).size!==ids.length || ids.some(id=>typeof id!=='string' || !scenes.some(scene=>scene.scene_id===id)))throw new Error('Selezione scene non valida');
    const members=scenes.filter(scene=>ids.includes(scene.scene_id));
    const selectedScene=members.length===1?members[0]:{scene_id:'selection_'+require('node:crypto').createHash('sha1').update(members.map(scene=>scene.scene_id).join('|')).digest('hex').slice(0,12),heading:'SEQUENZA · scene '+members.map(scene=>scenes.indexOf(scene)+1).join(', '),source_scene_ids:members.map(scene=>scene.scene_id),beats:members.flatMap(scene=>scene.beats).map((beat,order)=>({...beat,order}))};
    if(!selectedScene.beats.some(beat=>beat.kind==='dialogue'))throw new Error('Le scene scelte non contengono dialoghi');
    if(!analysis.planningSources?.length || !analysis.takes?.every(group=>group.confirmed))throw new Error('Conferma prima i confini delle take');
    const directions={...(this.state.directions || DEFAULT_DIRECTIONS),markers:{}};
    this.onProgress?.({phase:'plan',phaseIndex:6,percent:89,label:'Preparo il montaggio delle scene selezionate'});
    let plan=await this.buildPlan({beats:selectedScene.beats,sources:analysis.planningSources,shots:analysis.shots || [],directions,semantic:true,fps:this.state.fps || 25},300000);
    plan=await this.pacePlan({plan,sources:analysis.planningSources,audio:analysis.audio || {},beats:selectedScene.beats,shots:analysis.shots || [],fps:this.state.fps || 25,settings:this.state.pacingSettings});
    plan.visual_review_required=false;
    this.state.analysis={...analysis,selectedScene,parsedBeats:selectedScene.beats,sceneSelection:{scene:selectedScene,confidence:1,manual:true,candidates:analysis.sceneSelection?.candidates || []},plan,warnings:plan.warnings || [],visualReview:null};
    this.state.directions=directions;this.state.uiDraft=null;this.state.stage='review';
    this.onProgress?.({phase:'complete',phaseIndex:8,percent:100,label:'Montaggio pronto per la revisione'});
    return this.getReviewState();
  }
  async setScriptPages(request) {
    if(!this.state.script || path.extname(this.state.script.path).toLowerCase()!=='.pdf')throw new Error('Scegli un copione PDF');
    const {start,end}=request || {},all=start===null && end===null;
    if(!all && (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start<1 || end<start || end>10000))throw new Error('Intervallo pagine non valido');
    const result=await this.request('extract_pdf_script',{path:this.state.script.path,...(all?{}:{page_start:start,page_end:end})});
    this.state.script={...this.state.script,text:result.text,pages:all?null:{start,end}};
    this.state.analysis=null;this.state.uiDraft=null;this.state.directions={...(this.state.directions || DEFAULT_DIRECTIONS),markers:{}};
    this.state.stage='idle';return this.getReviewState();
  }
  async setScript(file) {
    const text = path.extname(file).toLowerCase() === '.pdf'
      ? (await this.request('extract_pdf_script', { path: file })).text
      : await fs.readFile(file, 'utf8');
    this.state.directions={...(this.state.directions || DEFAULT_DIRECTIONS),markers:{}}; this.state.script = { path: file, text }; this.state.analysis = null; return { name: path.basename(file),isPdf:path.extname(file).toLowerCase()==='.pdf' };
  }
  setMedia(records, identity) { this.state.media = records; this.state.transcripts = []; this.state.mediaFingerprints=null; this.state.uiDraft=null; this.state.analysis = null; this.state.projectId = identity.projectId; this.state.timelineId = identity.timelineId; return records.map(({ media_id, name, duration_frames, people = [] }) => ({ media_id, name, duration_frames, people })); }
  assertProject(identity) {
    if (!identity.projectId || identity.projectId !== this.state.projectId) throw new Error('Progetto Resolve cambiato: riapri il progetto delle clip caricate oppure carica una nuova selezione');
  }
  timelineCreationContext(identity) {
    this.assertProject(identity);
    if(!identity.timelineId)throw Error('Apri una timeline Resolve prima di crearne una nuova');
    if(!Number.isFinite(identity.fps)||!Number.isFinite(this.state.fps)||Math.abs(identity.fps-this.state.fps)>.001)throw Error('Il frame rate della timeline aperta è diverso da quello del piano: apri una timeline con '+this.state.fps+' fps');
    return {...this.state,timelineId:identity.timelineId};
  }
  assertContext(identity) {
    this.assertProject(identity);
    const ids = new Set((identity.selected || []).map(item => item.media_id));
    if (ids.size !== this.state.media.length || this.state.media.some(item => !ids.has(item.media_id))) {
      throw new Error('La selezione media è cambiata: seleziona le clip caricate prima di trascrivere');
    }
  }
  async analyze({catalogContext}={}) {
    if (!this.state.script || !this.state.media.length) throw new Error('Prima scegli un copione e media dal Media Pool');
    if (this.state.stage === 'analyzing') throw new Error('Analisi già in corso');
    const contextValid=catalogContext?.schema_version===1&&catalogContext.project_id===this.state.projectId&&catalogContext.analysis_script_fingerprint===catalogEdit.hash(this.state.script.text);
    const entries=new Map((contextValid?catalogContext.entries:[]).filter(c=>c.schema_version===1&&c.project_id===this.state.projectId).map(c=>[c.media_id,c]));
    const coverageSources=this.state.media.filter(m=>entries.has(m.media_id)&&!(this.state.transcripts||[]).some(s=>s.media_id===m.media_id&&catalogEdit.validSpeech(s))).map(m=>({...m,segments:[],catalog_context:entries.get(m.media_id)}));
    const contextWarnings=coverageSources.length?[coverageSources.length+' clip catalogate senza trascrizione: disponibili come materiali visivi, non usate per ricostruire le battute.']:[];
    if(contextValid)contextWarnings.push(...(catalogContext.warnings||[]));
    const missing=this.state.media.filter(media=>!(this.state.transcripts || []).some(source=>source.media_id===media.media_id && source.segments?.some(segment=>segment.end_frame>segment.start_frame && /[\p{L}\p{N}]/u.test(segment.text || ''))));
    if(missing.some(m=>!entries.has(m.media_id)))throw new Error('Trascrizioni mancanti o vuote: '+missing.map(media=>media.name || media.media_id).join(', ')+'. Trascrivi le clip e riprova.');
    this.state.mediaFingerprints=await this.captureMediaFingerprints();
    this.state.uiDraft=null;
    this.state.stage = 'analyzing';
    this.state.error = null;
    let lastPhaseIndex = 0;
    const startedAt = Date.now(); let lastPhase, phaseStartedAt = startedAt;
    const phaseSeconds={};
    const progress = (phase, phaseIndex, percent, label, current, total, skipped=false) => {
      if (phaseIndex >= 0) lastPhaseIndex = phaseIndex;
      if (phase !== lastPhase) { if(lastPhase)phaseSeconds[lastPhase]=(phaseSeconds[lastPhase] || 0)+(Date.now()-phaseStartedAt)/1000;lastPhase = phase; phaseStartedAt = Date.now(); }
      this.onProgress?.({ phase, phaseIndex, percent: Math.round(percent), label, current, total, skipped, elapsedSeconds: Math.round((Date.now()-startedAt)/1000), phaseElapsedSeconds: Math.round((Date.now()-phaseStartedAt)/1000) });
    };
    try {
      progress('script', 0, 0, 'Leggo e separo le scene del copione');
      const scriptStructure=this.useGroq()&&this.groq.prepareScript?await this.groq.prepareScript(this.state.script.text,event=>progress('script',0,4,event.phase==='quota'?'Attendo quota Groq per il copione':'Distinguo dialoghi e azioni nel copione')):{text:this.state.script.text,normalized:false};
      const parsed = await this.request('parse_script', { text: scriptStructure.text });parsed.normalized=scriptStructure.normalized;
      const sources = (this.state.transcripts || []).filter(catalogEdit.validSpeech);
      if(!sources.length){this.state.analysis={script:parsed,selectedScene:null,sceneSelection:{scene:null,candidates:[]},warnings:[...contextWarnings,'Nessun dialogo trascritto: consulta le coperture del catalogo. Il montaggio automatico di scene solo visive non viene inventato.'],takes:[],shots:[],audio:{},planningSources:[],plan:null,coverageSources,parsedBeats:[]};this.state.stage='review';progress('awaiting-scene',1,12,'Solo materiali visivi: nessun dialogo trascritto da montare');return this.getReviewState();}
      progress('scene', 1, 12, 'Individuo la scena che corrisponde al parlato');
      const detectedScene = await this.request('select_scene', {
        scenes: parsed.scenes, transcript: sources.flatMap(source => source.segments)
      });
      const sceneSelection=automaticEditing.automaticScope(parsed.scenes,detectedScene,[...entries.values()],sources.map(s=>s.media_id));
      let selectedScene = sceneSelection.scene;
      if(!selectedScene?.beats?.length)throw new Error('Nessuna scena leggibile nel copione: verifica il PDF.');
      if(sceneSelection.scope_basis==='script_search')contextWarnings.push('Nessuna scena unica: il motore cerca automaticamente le battute nel copione completo. Solo gli intervalli abbinati entrano nel piano.');
      const beats = selectedScene ? selectedScene.beats : [];
      const shots = [];
      let shotCacheHits = 0;
      const decodeBackends=new Set();
      const shotSources = sources.filter(source => source.path);
      progress('shots', 2, 24, shotSources.length ? `Analisi inquadrature: 0/${shotSources.length} clip` : 'Nessun file video da analizzare');
      for (let i = 0; i < shotSources.length; i++) {
        const source = shotSources[i];
        progress('shots', 2, 24 + (i / shotSources.length) * 38, `Analizzo le inquadrature di ${source.name}`, i, shotSources.length);
        try { const result = await this.request('analyze_shots', { media: source, sample_fps: 2 }, 20 * 60 * 1000, event => progress('shots', 2, 24 + ((i + event.frame / Math.max(1, event.total)) / shotSources.length) * 38, `YuNet · ${source.name} · ${Math.round(event.frame / Math.max(1, event.total) * 100)}%`, i + event.frame / Math.max(1,event.total), shotSources.length)); shots.push(...result.segments); if (result.cache_hit) shotCacheHits += 1; else if(result.decode_backend)decodeBackends.add(result.decode_backend); }
        catch (error) { this.state.error = `Analisi inquadrature non disponibile per ${source.name}: ${error.message}`; }
        progress('shots', 2, 24 + ((i + 1) / shotSources.length) * 38, `Inquadrature: ${i + 1}/${shotSources.length} clip`, i + 1, shotSources.length);
      }
      if(shotSources.length)progress('visual',3,62,'Still e volti: caricamento su richiesta',0,0,true);
      const visualReview = null; // Still and identity clustering are explicit visual-debug work.
      const takes = [];
      progress('takes', 4, 68, `Individuo i confini delle take: 0/${sources.length} clip`);
      for (let i = 0; i < sources.length; i++) {
        const source = sources[i];
        const proposals = this.useGroq() ? [{take_id:source.take_id || source.media_id+':take:1',media_id:source.media_id,start_frame:0,end_frame:source.duration_frames,take_index:1,camera_id:source.camera_id || 'camera_1',boundary_source:'whole_clip',confirmed:true}] : await this.request('propose_take_segments', { media: source, transcript: source.segments, fps: source.fps || this.state.fps || 25, beats });
        const accepted=automaticEditing.automaticTakes({...this.state.media.find(m=>m.media_id===source.media_id),...source},proposals);
        if(accepted.fallback)contextWarnings.push('Confini take non affidabili per '+(source.name||source.media_id)+': il motore lavora sulla clip intera per conservare il parlato.');
        takes.push({media_id:source.media_id,media_name:source.name,duration_frames:source.duration_frames,confirmed:true,selection_mode:'automatic',segments:accepted.segments});
        progress('takes', 4, 68 + ((i + 1) / Math.max(1, sources.length)) * 12, `Confini take: ${i + 1}/${sources.length} clip`, i + 1, sources.length);
      }
      const planningSources = takes.flatMap(group => group.confirmed ? group.segments.map(take => ({ ...sources.find(source => source.media_id === group.media_id), ...take,
        catalog_context: entries.get(group.media_id), segments: sources.find(source => source.media_id === group.media_id).segments.filter(segment => segment.start_frame >= take.start_frame && segment.start_frame < take.end_frame) })) : []);
      const audio = {};
      // groq_staged_v1 preserves timing; targeted listener/breath checks load shared RMS only when needed.
      // Active-speaker checks still load their own PCM samples when needed.
      const measurePauses = this.state.pacingSettings.enabled && !this.useGroq();
      const audioSources = measurePauses ? sources.filter(source => source.path) : [];
      const audioLabel = audioSources.length ? 'Misuro le pause nell’audio locale'
        : !this.state.pacingSettings.enabled ? 'Misura pause disattivata'
        : !measurePauses ? 'Pause originali conservate nel montaggio dialogato'
        : 'Nessun file audio da analizzare';
      progress('audio', 5, 81, audioLabel, 0, audioSources.length, !audioSources.length);
      for (let i=0;i<audioSources.length;i++) {
        const source=audioSources[i];
        progress('audio',5,81+(i/Math.max(1,audioSources.length))*7, 'Audio · '+source.name,i,audioSources.length);
        try { audio[source.media_id] = await this.request('analyze_audio',{media:source},180000); }
        catch(error) { audio[source.media_id] = {status:'unavailable',reason:error.message}; }
        progress('audio',5,81+((i+1)/audioSources.length)*7,'Audio · '+source.name+' · '+(audio[source.media_id].status==='ok' ? (audio[source.media_id].cache_hit?'cache verificata':'misurato') : 'non disponibile: pause conservate'),i+1,audioSources.length);
      }
      progress('plan', 6, 89, 'Scelgo automaticamente battute, take e inquadrature');
      let plan = selectedScene && takes.every(group => group.confirmed)
        ? await this.buildPlan( { beats, sources: planningSources, shots, catalog_coverage:coverageSources,scene_id:selectedScene.scene_id, scenes:parsed.scenes, script_structured:parsed.normalized, directions:this.state.directions, semantic: true, fps: this.state.fps || 25 },300000) : null;
      progress('pacing',7,95,'Verifico pause e reazioni prima della risoluzione');
      if(plan)plan=this.keepReactionChoices(plan);
      if (plan) plan=await this.pacePlan({plan,sources:planningSources,audio,beats,shots,fps:this.state.fps || 25,settings:this.state.pacingSettings});
      if (plan) plan.visual_review_required = false;
      const warnings = selectedScene
        ? [...(plan?.warnings || ['Conferma i confini delle take suggerite prima di calcolare il premontato.'])]
        : ['Non ho trovato una corrispondenza sufficientemente chiara tra dialoghi e copione; controlla trascrizione e clip selezionate.'];
      warnings.push(...contextWarnings);
      if(decodeBackends.size)warnings.push('Lettura video: '+[...decodeBackends].map(name=>name==='CPU'?'CPU':'GPU / '+name).join(', ')+'. YuNet resta sulla CPU.');
      if (shotCacheHits) warnings.push(`Analisi visiva riusata dalla cache locale per ${shotCacheHits} clip.`);
      if (this.state.error) warnings.push(this.state.error);
      if(plan)plan.performance={...(plan.performance || {}),session:{total_seconds:(Date.now()-startedAt)/1000,phase_seconds:{...phaseSeconds,[lastPhase]:(phaseSeconds[lastPhase] || 0)+(Date.now()-phaseStartedAt)/1000}}};
      if(plan?.engine==='scene_jobs_v1')selectedScene={scene_id:'scene_jobs',heading:'SEQUENZA · scene in ordine di copione',source_scene_ids:plan.scene_jobs.filter(j=>j.decisions).map(j=>j.scene_id),beats:parsed.scenes.flatMap(s=>s.beats)};
      this.state.analysis = { script: parsed, sceneSelection, selectedScene, warnings, takes, shots, audio, planningSources, plan, visualReview, coverageSources, parsedBeats: selectedScene.beats };
      this.state.stage = selectedScene?'review':'awaiting_scene';
      if(selectedScene)progress('complete',8,100,plan?.decisions?.length?'Montaggio preparato · puoi creare la timeline':'Analisi completata · nessun taglio utilizzabile');
      else progress('awaiting-scene',1,12,'Scena ambigua: scegli una o più scene del copione per proseguire');
      return this.getReviewState();
    } catch (error) { this.state.error = error.message; this.state.stage = 'error'; progress('error', lastPhaseIndex, 0, `Analisi interrotta: ${error.message}`); throw error; }
  }
  useGroq(){const s=this.groq?.status();return Boolean(s?.configured && s.enabled);}
  async buildPlan(payload,timeoutMs=300000,onProgress){let plan;
    if(payload.scenes?.length>1){
      if(!payload.script_structured&&this.useGroq()&&this.groq.prepareScript&&this.state.script?.text){const structured=await this.groq.prepareScript(this.state.script.text);if(structured.normalized){const parsed=await this.request('parse_script',{text:structured.text},timeoutMs);const scope=new Set(payload.scenes.map(s=>s.scene_id));payload={...payload,script_structured:true,scenes:parsed.scenes.filter(s=>scope.has(s.scene_id)),beats:parsed.scenes.filter(s=>scope.has(s.scene_id)).flatMap(s=>s.beats)};}}
      const routed=await this.request('route_scene_edits',{scenes:payload.scenes,sources:payload.sources,fps:payload.fps},timeoutMs);const plans=[],jobs=[];
      for(const [index,job] of routed.jobs.entries()){
        const scene=job.scene;this.onProgress?.({phase:'plan',phaseIndex:6,percent:89+Math.round(6*index/Math.max(1,routed.jobs.length)),label:'Scena '+(index+1)+'/'+routed.jobs.length+' · '+scene.heading});
        if(!job.sources.length){jobs.push({scene_id:scene.scene_id,heading:scene.heading,status:'no_coverage',missing:scene.beats.filter(b=>b.kind==='dialogue').map(b=>b.beat_id)});continue;}
        try{const scenePayload={...payload,scenes:undefined,scene_id:scene.scene_id,beats:scene.beats,sources:job.sources};
          const checkpoint=path.isAbsolute(this.root)&&job.sources.every(s=>s.path)?path.join(this.root,'cache','scene-edits',require('node:crypto').createHash('sha256').update(JSON.stringify({version:'scene-jobs-12-close-first',provider:this.groq?.cacheIdentity||this.groq?.status?.().model||'local',groq:this.useGroq(),payload:scenePayload,settings:this.state.pacingSettings})).digest('hex')+'.json'):null;
          let part;if(checkpoint)try{part=JSON.parse(await fs.readFile(checkpoint,'utf8'));if(part.recovery?.retryable)part=null;}catch{}
          if(!part){part=await this.buildPlanCore(scenePayload,timeoutMs,onProgress);if(this.useGroq()&&part.unmatched_beats?.length){this.onProgress?.({phase:'plan',phaseIndex:6,percent:93,label:scene.heading+' · ricontrollo '+part.unmatched_beats.length+' battute nelle trascrizioni originali'});const recovery=await this.request('expand_scene_edits',{scene,scenes:payload.scenes,missing:part.unmatched_beats,sources:payload.sources,selected_sources:job.sources,fps:payload.fps},timeoutMs);let recoveryFailed=false;if(recovery.expanded_media||recovery.focus_ranges?.length){try{const retry=await this.buildPlanCore({...scenePayload,sources:recovery.sources,recovery_focus:recovery.focus_ranges,missing_focus:part.unmatched_beats},timeoutMs,onProgress);if((retry.unmatched_beats?.length||0)<part.unmatched_beats.length&&(retry.unmatched_beats||[]).every(id=>part.unmatched_beats.includes(id)))part=retry;}catch(error){if(error.code==='GROQ_DAILY_QUOTA'||/annullat|cancel|abort/i.test(error.message))throw error;recoveryFailed=true;part.warnings=(part.warnings||[]).concat('Recupero aggiuntivo non completato: '+error.message);}}part.recovery={attempted:true,expanded_media:recovery.expanded_media,retryable:recoveryFailed};}if(part.engine!=='groq_staged_v1')part=await this.pacePlan({plan:part,sources:job.sources,beats:scene.beats,shots:payload.shots,audio:{},fps:payload.fps,settings:this.state.pacingSettings});if(checkpoint){await fs.mkdir(path.dirname(checkpoint),{recursive:true});await fs.writeFile(checkpoint+'.tmp',JSON.stringify(part));await fs.rename(checkpoint+'.tmp',checkpoint);}}
          for(const b of part.review_beats||[])b.beat_id=scene.scene_id+':'+b.beat_id;
          for(const d of part.decisions){d.scene_id=scene.scene_id;d.decision_id=scene.scene_id+':'+(d.decision_id||d.beat_id);}if(part.base_decisions)part.base_decisions=JSON.parse(JSON.stringify(part.decisions));
          plans.push(part);jobs.push({scene_id:scene.scene_id,heading:scene.heading,status:part.unmatched_beats?.length?'incomplete':'ready',missing:part.unmatched_beats||[],decisions:part.decisions.length});
        }catch(error){if(error.code==='GROQ_DAILY_QUOTA'||/annullat|cancel|abort/i.test(error.message))throw error;this.onProgress?.({phase:'plan',phaseIndex:6,percent:89+Math.round(6*index/Math.max(1,routed.jobs.length)),label:scene.heading+' · problema: '+error.message});jobs.push({scene_id:scene.scene_id,heading:scene.heading,status:'failed',error:error.message,missing:scene.beats.filter(b=>b.kind==='dialogue').map(b=>b.beat_id)});}
      }
      const decisions=plans.flatMap(p=>p.decisions);let cursor=0;for(const d of decisions){d.timeline_start_frame=cursor;cursor+=d.end_frame-d.start_frame+ (d.action_after||[]).reduce((n,a)=>n+a.end_frame-a.start_frame,0);}
      plan={engine:'scene_jobs_v1',plan_id:'scene-jobs',fps:payload.fps,scene_id:payload.scene_id,decisions,base_decisions:JSON.parse(JSON.stringify(decisions)),review_beats:plans.flatMap(p=>p.review_beats||[]),unmatched_beats:jobs.flatMap(j=>j.missing||[]),warnings:plans.flatMap(p=>p.warnings||[]),script_scenes:payload.scenes,scene_jobs:jobs,ready_for_timeline:!jobs.some(j=>j.status==='failed'||j.missing?.length),planning_summary:{scene_jobs:jobs,unassigned_units:routed.unassigned.length},visual_review_required:false};
    }else plan=await this.buildPlanCore(payload,timeoutMs,onProgress);const pool=payload.catalog_coverage||this.state.analysis?.coverageSources;if(pool?.length){const ids=new Set((payload.beats||[]).map(b=>b.scene_id).filter(Boolean));if(payload.scene_id)ids.add(payload.scene_id);plan.catalog_coverage=pool.filter(s=>!ids.size||!s.catalog_context?.scene||ids.has(s.catalog_context.scene.scene_id)).map(s=>({media_id:s.media_id,name:s.name,fps:s.fps,duration_frames:s.duration_frames,catalog_context:s.catalog_context}));}return plan;}
  async buildPlanCore(payload, timeoutMs=300000, onProgress) {
    if(this.useGroq()){
      const prepared=await this.request('prepare_dialogue',payload,timeoutMs);
      const classificationStarted=performance.now();
      const classification=await this.groq.classify(prepared,event=>{
        const label=event.phase==='quota'?'Quota Groq: attendo '+event.seconds+' secondi': 'Pulizia e allineamento Groq · '+event.current+'/'+event.total+(event.cache_hit?' · cache verificata':Number.isFinite(event.batch)?' · blocco '+(Math.floor(event.batch/20)+1)+'/'+Math.ceil(event.units/20):'');
        this.onProgress?.({phase:'plan',phaseIndex:6,percent:89+Math.round(3*event.current/Math.max(1,event.total)),label,current:event.current,total:event.total});
      });
      if(payload.recovery_focus?.length){
        const focusClips=prepared.clips.map(clip=>({...clip,units:clip.units.filter(u=>payload.recovery_focus.some(r=>r.take_id===clip.key&&u.start<r.end_frame&&r.start_frame<u.end))})).filter(c=>c.units.length);
        if(focusClips.length){const focus_beats=prepared.beats.filter(b=>(payload.missing_focus||[]).includes(b.beat_id)).map(b=>b.number);const checked=await this.groq.classify({...prepared,focus_beats,clips:focusClips},event=>this.onProgress?.({phase:'plan',phaseIndex:6,percent:94,label:'Ricontrollo mirato del parlato · '+event.current+'/'+event.total+(event.phase==='quota'?' · attendo quota '+event.seconds+' s':''),current:event.current,total:event.total}));for(const [key,labels] of Object.entries(checked.labels))Object.assign(classification.labels[key],labels);classification.summary={...classification.summary,recovery_calls:checked.summary.calls,recovery_cache_hits:checked.summary.cache_hits};}
      }
      const classificationSeconds=(performance.now()-classificationStarted)/1000;
      const editorialStarted=performance.now();
      let editorial;
      if(typeof this.groq.planEditorial==='function'){
        try{editorial=await this.groq.planEditorial(prepared,classification.labels,payload.directions || this.state.directions,event=>this.onProgress?.({phase:'plan',phaseIndex:6,percent:92,label:event.phase==='quota'?'Piano editoriale: attendo quota Groq '+event.seconds+' s':'Lettura editoriale del testo'+(event.cache_hit?' · cache verificata':''),current:0,total:1}));}
        catch(error){if(/annullat|cancel|abort/i.test(error.message))throw error;editorial={events:[],summary:{status:'unavailable'},warnings:['Lettura editoriale non disponibile: '+error.message+'. Uso solo regole locali conservative.']};}
      }
      const editorialSeconds=(performance.now()-editorialStarted)/1000;
      const result=await this.request('build_staged',{...payload,prepared,classifications:classification.labels,classification_summary:classification.summary,editorial,settings:this.state.pacingSettings},timeoutMs,event=>this.onProgress?.({phase:'plan',phaseIndex:6,percent:event.phase==='speaker'?92+Math.round(3*event.current/Math.max(1,event.total)):95,label:event.phase==='speaker-final'?'Verifico i campi finali · '+event.current+'/'+event.total:event.phase==='speaker'?'Controllo locale del parlante · '+event.current+'/'+event.total:event.phase==='listening'?(event.step==='breaths'?'Verifico respiri':'Cerco reazioni')+' · '+event.current+'/'+event.total+(event.candidates_checked!==undefined?' · '+event.candidates_checked+' candidati verificati':''):'Scelta locale delle camere e verifica continuità',current:event.current,total:event.total}));
      result.performance={...(result.performance || {}),groq:{classification_seconds:classificationSeconds,editorial_seconds:editorialSeconds}};
      return result;
    }

    let lastPercent=89;
    return this.request('build_plan',{...payload,active_speaker:true},timeoutMs,onProgress || (event=>{
      lastPercent=Math.max(lastPercent,89+6*((event.beat-1+(event.done?.5:0))/Math.max(1,event.total)));
      this.onProgress?.({phase:'plan',phaseIndex:6,percent:Math.round(lastPercent),label:'Parlante · battuta '+event.beat+'/'+event.total+' · '+event.name+' · '+event.checked+' campioni, '+event.cache_hits+' da cache',current:event.beat-1,total:event.total});
    }));
  }
  async loadVisualReview() {
    const analysis=this.state.analysis;
    if(!analysis || this.state.stage==='analyzing')throw new Error('Completa prima l’analisi del montaggio');
    if(analysis.visualReview)return this.getReviewState();
    const sources=(this.state.transcripts || []).filter(source=>source.path);
    this.onProgress?.({phase:'visual',phaseIndex:3,percent:62,label:'Preparo il controllo visivo facoltativo'});
    try {
      const result=await this.request('visual_review',{media:sources,shots:analysis.shots || []},20*60*1000,event=>this.onProgress?.({phase:'visual',phaseIndex:3,percent:62+Math.round(6*(event.clip_index+event.current/Math.max(1,event.total))/Math.max(1,event.clip_total)),label:'Still e volti · '+event.name,current:event.current,total:event.total}));
      analysis.visualReview=result;
      this.onProgress?.({phase:'complete',phaseIndex:8,percent:100,label:'Controllo visivo pronto; associazioni dei nomi facoltative'});
      return this.getReviewState();
    } catch(error) {this.onProgress?.({phase:'error',phaseIndex:3,percent:0,label:error.message});throw error;}
  }
  async cancelAnalysis() { this.groq?.cancel(); this.failAll(new Error('Analisi annullata')); this.child?.kill(); this.child = null; this.state.stage = 'idle'; return true; }
  async shutdownWorker(timeoutMs = 8000) {
    const child = this.child;
    if (!child) return false;
    this.failAll(new Error('Worker arrestato per aggiornare il runtime'));
    const exited = new Promise(resolve => child.once('exit', resolve));
    child.kill();
    let timer;
    await Promise.race([exited, new Promise(resolve => { timer = setTimeout(resolve, timeoutMs); })]);
    clearTimeout(timer);
    if (this.child === child) { child.kill(); this.child = null; }
    return true;
  }
  async captureMediaFingerprints(media=this.state.media) {
    return Promise.all(media.map(async item=>{try{const stat=await fs.stat(item.path);return {media_id:item.media_id,path:item.path,size:stat.size,mtimeMs:stat.mtimeMs};}catch{return {media_id:item.media_id,path:item.path,unavailable:true};}}));
  }
  async validateMediaUnchanged() {
    if(!this.state.mediaFingerprints)return;
    const current=await this.captureMediaFingerprints();
    if(current.some((item,i)=>item.unavailable || item.size!==this.state.mediaFingerprints[i]?.size || item.mtimeMs!==this.state.mediaFingerprints[i]?.mtimeMs))throw new Error('Riprese modificate o non disponibili: riseleziona e ricalcola prima della timeline');
  }
  projectStatus(){return {name:this.projectFile?path.basename(this.projectFile):'Sessione senza nome',lastSavedAt:this.lastSavedAt,lastAutosaveAt:this.lastAutosaveAt,error:this.saveError,warning:this.state.restoreWarning || null};}
  setDraft(value){
    validateDraft(value);
    this.state.uiDraft=JSON.parse(JSON.stringify(value));if(value.visual?.dirty && this.state.analysis?.plan){this.state.analysis.plan.visual_review_required=true;if(this.state.analysis.visualReview)this.state.analysis.visualReview.confirmed=false;}return true;
  }
  async writeProject(file){
    const keys=['script','media','transcripts','fps','projectId','timelineId','analysis','pacingSettings','directions','uiDraft','mediaFingerprints'];
    const state=Object.fromEntries(keys.filter(key=>this.state[key]!==undefined).map(key=>[key,this.state[key]]));
    state.mediaFingerprints=state.mediaFingerprints || await this.captureMediaFingerprints();
    const document={format:'premontato-project',schema_version:1,document_id:this.documentId,savedAt:new Date().toISOString(),state};
    const target=path.resolve(file),temporary=target+'.'+require('node:crypto').randomUUID()+'.tmp';
    await fs.mkdir(path.dirname(target),{recursive:true});
    try{const handle=await fs.open(temporary,'wx',0o600);try{await handle.writeFile(JSON.stringify(document));await handle.sync();}finally{await handle.close();}await fs.rename(temporary,target);}
    finally{await fs.rm(temporary,{force:true}).catch(()=>{});}
    return document.savedAt;
  }
  async writeBinding(){
    const target=path.join(this.root,'projects','current.json'),temporary=target+'.'+require('node:crypto').randomUUID()+'.tmp';
    await fs.mkdir(path.dirname(target),{recursive:true});
    this.projectFingerprint=this.projectFile?await fs.stat(this.projectFile).then(stat=>({size:stat.size,mtimeMs:stat.mtimeMs})):null;
    try{await fs.writeFile(temporary,JSON.stringify({document_id:this.documentId,path:this.projectFile,fingerprint:this.projectFingerprint}),{flag:'wx',mode:0o600});await fs.rename(temporary,target);}finally{await fs.rm(temporary,{force:true}).catch(()=>{});}
  }
  async saveProject(file=this.projectFile){
    if(!file)throw new Error('Scegli un nome per il progetto Premontato');
    const saved=await this.writeProject(file);this.projectFile=path.resolve(file);this.lastSavedAt=saved;await this.writeBinding();this.saveError=null;return this.getReviewState();
  }
  async saveAutosave(){
    this.lastAutosaveAt=await this.writeProject(path.join(this.root,'projects','autosave.premontato.json'));
    if(this.projectFile){
      const stat=await fs.stat(this.projectFile).catch(()=>null);
      if(!stat || !this.projectFingerprint || stat.size!==this.projectFingerprint.size || stat.mtimeMs!==this.projectFingerprint.mtimeMs){this.projectFile=null;this.state.restoreWarning='Il file progetto è stato modificato fuori dal plugin: recupero locale conservato, usa Apri o Salva con nome.';}
      else this.lastSavedAt=await this.writeProject(this.projectFile);
    }
    await this.writeBinding();this.saveError=null;return this.projectStatus();
  }
  async loadProject(file,{recovery=false}={}){
    const stat=await fs.stat(file);if(stat.size>100*1024*1024)throw new Error('Progetto Premontato troppo grande');
    let document;try{document=JSON.parse(await fs.readFile(file,'utf8'));}catch{throw new Error('File progetto Premontato non leggibile');}
    const state=document?.state;
    if(document?.format!=='premontato-project' || document.schema_version!==1 || !state || !Array.isArray(state.media) || (state.script && typeof state.script.text!=='string') || (state.transcripts && !Array.isArray(state.transcripts)) || (state.analysis && (typeof state.analysis!=='object' || (state.analysis.plan && !Array.isArray(state.analysis.plan.decisions)))))throw new Error('Formato progetto Premontato non valido');
    validateProjectState(state);
    if(state.media.length)require('./ipc_security').validateMediaRecords(state.media);
    const current=await this.captureMediaFingerprints(state.media),stored=state.mediaFingerprints || [];
    const changed=current.some((item,i)=>item.unavailable || item.path!==stored[i]?.path || item.size!==stored[i]?.size || item.mtimeMs!==stored[i]?.mtimeMs);
    const restored={...state,stage:state.analysis?'review':'idle',error:null};
    if(changed){restored.analysis=null;restored.transcripts=[];restored.uiDraft=null;restored.stage='idle';restored.restoreWarning='Riprese modificate o non disponibili: riseleziona le clip, trascrivi e ripeti l’analisi.';}
    await this.shutdownWorker();this.documentId=typeof document.document_id==='string' && /^[a-f0-9-]{36}$/.test(document.document_id)?document.document_id:require('node:crypto').randomUUID();this.state=restored;this.projectFile=recovery?null:path.resolve(file);this.lastSavedAt=recovery?null:document.savedAt;this.projectFingerprint=recovery?null:{size:stat.size,mtimeMs:stat.mtimeMs};this.lastAutosaveAt=recovery?document.savedAt:null;this.saveError=null;
    return this.getReviewState();
  }
  async restoreAutosave(){
    const file=path.join(this.root,'projects','autosave.premontato.json');
    try{await fs.access(file);}catch(error){if(error.code==='ENOENT')return false;throw error;}
    await this.loadProject(file,{recovery:true});
    try{const binding=JSON.parse(await fs.readFile(path.join(this.root,'projects','current.json'),'utf8'));if(binding.document_id===this.documentId && typeof binding.path==='string' && path.isAbsolute(binding.path)){const stat=await fs.stat(binding.path);if(stat.isFile() && stat.size===binding.fingerprint?.size && stat.mtimeMs===binding.fingerprint?.mtimeMs){this.projectFile=binding.path;this.projectFingerprint=binding.fingerprint;this.lastSavedAt=this.lastAutosaveAt;}else{this.state.restoreWarning='Il file progetto è stato modificato fuori dal plugin: recupero aperto senza sovrascriverlo. Apri il file aggiornato oppure salva con un nuovo nome.';}}}catch{}
    return true;
  }
  getReviewState() { return { groq:this.groq?.status(), projectStatus:this.projectStatus(), uiDraft:this.state.uiDraft, stage: this.state.stage, scriptName: this.state.script ? path.basename(this.state.script.path) : null, scriptIsPdf:path.extname(this.state.script?.path || '').toLowerCase()==='.pdf',scriptPages:this.state.script?.pages || null,
    media: this.state.media.map(({ media_id, name, duration_frames, people = [] }) => ({ media_id, name, duration_frames, people })), analysis: this.state.analysis, directions:this.state.directions || DEFAULT_DIRECTIONS, pacingSettings: this.state.pacingSettings, error: this.state.error }; }
  setTranscripts(sources, fps, identity) { this.assertContext(identity); this.state.transcripts = sources; this.state.fps = fps; this.state.analysis = null; return { count: sources.reduce((sum, source) => sum + source.segments.length, 0) }; }
  updateDecision(request) {
    const plan = this.state.analysis?.plan;
    const decision = plan?.decisions.find(item => request?.decision_id ? item.decision_id===request.decision_id && item.beat_id===request.beat_id : item.beat_id===request?.beat_id);
    if (!decision) throw new Error('Battuta non disponibile');
    const pauseOnly=(request.preserve_pause !== undefined || request.reaction_enabled !== undefined) && !['start_frame','end_frame','shot_size','alternative_index'].some(key=>request[key]!==undefined);
    const original=pauseOnly ? plan.base_decisions?.find(item=>(item.decision_id || item.beat_id)===(decision.decision_id || decision.beat_id)) : null;
    let updated = { ...(original || decision) };
    if (request.alternative_index !== undefined) {
      const alt = decision.alternatives?.[request.alternative_index];
      if (!Number.isInteger(request.alternative_index) || !alt) throw new Error('Alternativa non valida');
      updated = { ...updated, ...alt, alternatives: [decision, ...decision.alternatives.filter((_, index) => index !== request.alternative_index)].map(({ alternatives, ...item }) => item) };
    }
    const media = this.state.media.find(item => item.media_id === updated.media_id);
    const start = request.start_frame ?? updated.start_frame, end = request.end_frame ?? updated.end_frame;
    if (!media || !Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end > media.duration_frames || end <= start) throw new Error('Intervallo sorgente non valido');
    if (request.shot_size !== undefined && !['wide','medium','close','detail','unknown'].includes(request.shot_size)) throw new Error('Scala non valida');
    if(request.reaction_enabled!==undefined && typeof request.reaction_enabled!=='boolean')throw new Error('Stato reazione non valido');
    if (request.preserve_pause !== undefined && typeof request.preserve_pause !== 'boolean') throw new Error('Blocco pausa non valido');
    if(updated.speaker_coverage_source==='audio_visual' && ((request.start_frame!==undefined && start!==updated.start_frame) || (request.end_frame!==undefined && end!==updated.end_frame))) {
      delete updated.active_speaker;updated.speaker_coverage='unknown';updated.speaker_coverage_source='unverified';updated.matched_start_frame=start;updated.matched_end_frame=end;
    }
    const manual=updated.manual || ['start_frame','end_frame','shot_size','alternative_index'].some(key=>request[key]!==undefined);
    Object.assign(updated, { start_frame: start, end_frame: end, shot_size: request.shot_size ?? updated.shot_size, manual, reaction_enabled:request.reaction_enabled ?? updated.reaction_enabled, preserve_pause: request.preserve_pause ?? updated.preserve_pause });
    if(!pauseOnly){delete updated.source_ranges; delete updated.pacing; delete updated.reaction_before; delete updated.reaction_overlay; delete updated.action_after;delete updated.editorial_event;}
    else if(updated.reaction_enabled===false){delete updated.reaction_before;delete updated.reaction_overlay;}
    const base=plan.base_decisions?.findIndex(item=>(item.decision_id || item.beat_id)===(updated.decision_id || updated.beat_id));
    if (base !== undefined && base>=0){if(!pauseOnly)plan.base_decisions[base]={...updated};else{if(request.reaction_enabled!==undefined)plan.base_decisions[base].reaction_enabled=request.reaction_enabled;if(request.preserve_pause!==undefined)plan.base_decisions[base].preserve_pause=request.preserve_pause;}}
    plan.decisions[plan.decisions.indexOf(decision)] = updated;
    let cursor = 0;
    for (const item of plan.decisions) { item.timeline_start_frame = cursor; cursor += item.source_ranges?.reduce((sum,r)=>sum+r.end_frame-r.start_frame,0) ?? item.end_frame - item.start_frame; }
    return this.getReviewState();
  }
  keepReactionChoices(plan, previous=this.state.analysis?.plan) {
    const choices=new Map((previous?.decisions || []).filter(d=>typeof d.reaction_enabled==='boolean').map(d=>[d.decision_id || d.beat_id,d.reaction_enabled]));
    for(const decision of plan?.decisions || [])if(choices.has(decision.decision_id || decision.beat_id))decision.reaction_enabled=choices.get(decision.decision_id || decision.beat_id);
    return plan;
  }
  async pacePlan(payload) {
    if(payload.plan?.engine==='scene_jobs_v1')return payload.plan;
    const audio=payload.audio || {};
    let measuredAudio=false;
    // Saved Groq projects and analyses made with pacing off may lack RMS data.
    // Fill it only when the actual local plan needs it, including alternate cameras.
    if(!['groq_staged_v1','scene_jobs_v1'].includes(payload.plan?.engine) && payload.plan?.decisions?.length && payload.settings?.enabled===true) {
      const originals=new Map([...(this.state.media || []),...(this.state.transcripts || [])].map(source=>[source.media_id,source]));
      const missing=new Map();
      for(const source of payload.sources || []) {
        const media=originals.get(source.media_id) || source;
        if(media.path && !Object.hasOwn(audio,media.media_id))missing.set(media.media_id,media);
      }
      let current=0;
      for(const media of missing.values()) {
        measuredAudio=true;
        this.onProgress?.({phase:'pacing',phaseIndex:7,percent:95,label:'Misuro le pause · '+(media.name || media.media_id),current,total:missing.size});
        try { audio[media.media_id]=await this.request('analyze_audio',{media},180000); }
        catch(error) { audio[media.media_id]={status:'unavailable',reason:error.message}; }
        current++;
      }
      if(this.state.analysis)this.state.analysis.audio=audio;
    }
    try {
      const result=await this.request('pace_plan',{...payload,audio});
      if(measuredAudio)this.onProgress?.({phase:'complete',phaseIndex:8,percent:100,label:'Ritmo aggiornato'});
      return result;
    } catch(error) {
      if(measuredAudio)this.onProgress?.({phase:'error',phaseIndex:7,percent:0,label:'Verifica pause interrotta: '+error.message});
      throw error;
    }
  }
  async applyPacing() {
    if (!this.state.analysis?.plan) return this.getReviewState();
    this.state.analysis.plan=await this.pacePlan({plan:this.state.analysis.plan,sources:this.state.analysis?.planningSources || this.state.transcripts || [],audio:this.state.analysis.audio || {},shots:this.state.analysis.shots || [],beats:this.state.analysis.parsedBeats || [],fps:this.state.fps || 25,settings:this.state.pacingSettings});
    return this.getReviewState();
  }
  async setDirections(value) {
    const directions=validateDirections(value),analysis=this.state.analysis;
    const beats=analysis?.parsedBeats || [];
    if(Object.keys(directions.markers).some(id=>!beats.some(b=>b.beat_id===id && b.kind==='dialogue')))throw new Error('Battuta delle direzioni non presente nella scena');
    let plan=analysis?.plan;
    const previous=this.state.directions || DEFAULT_DIRECTIONS;
    const changed=(analysis?.plan?.engine==='groq_staged_v1' && directions.notes!==previous.notes) || directions.profile!==previous.profile || JSON.stringify(Object.entries(directions.markers).sort())!==JSON.stringify(Object.entries(previous.markers || {}).sort());
    if(changed && analysis?.planningSources?.length && analysis.takes?.every(group=>group.confirmed)) {
      this.onProgress?.({phase:'plan',phaseIndex:6,percent:89,label:'Ricalcolo secondo le direzioni di montaggio'});
      plan=await this.buildPlan({beats,sources:analysis.planningSources,shots:analysis.shots || [],directions,semantic:true,fps:this.state.fps || 25},300000);
      plan=this.keepReactionChoices(plan);
      this.onProgress?.({phase:'pacing',phaseIndex:7,percent:95,label:'Verifico pause e reazioni prima della risoluzione'});
      plan=await this.pacePlan({plan,sources:analysis.planningSources,audio:analysis.audio || {},shots:analysis.shots || [],beats,fps:this.state.fps || 25,settings:this.state.pacingSettings});
      if(analysis.visualReview)plan.visual_review_required=Boolean(analysis.plan?.visual_review_required);
    }
    this.state.directions=directions;if(analysis)analysis.plan=plan;
    this.onProgress?.({phase:'complete',phaseIndex:8,percent:100,label:'Direzioni salvate; controlla le scelte narrative'});
    return this.getReviewState();
  }
  async setPacing(options) {
    const plan=this.state.analysis?.plan || {decisions:[],warnings:[]};
    const result=await this.pacePlan({plan,sources:this.state.analysis?.planningSources || this.state.transcripts || [],audio:this.state.analysis?.audio || {},shots:this.state.analysis?.shots || [],beats:this.state.analysis?.parsedBeats || [],fps:this.state.fps || 25,settings:{...this.state.pacingSettings,...options}});
    this.state.pacingSettings=result.pacing_settings;
    if(this.state.analysis?.plan)this.state.analysis.plan=result;
    return this.getReviewState();
  }
  async confirmVisualReview(request) {
    const analysis=this.state.analysis, review=analysis?.visualReview;
    if (!review || request?.confirmed !== true || !Array.isArray(request.intervals) || request.intervals.length !== review.intervals.length) throw new Error('Conferma tutte le inquadrature della revisione visiva');
    const cast=new Set((analysis.parsedBeats || []).filter(b=>b.kind==='dialogue').map(b=>b.character).filter(Boolean));
    const names=request.person_names || {};
    const people=new Set((review.faces || []).map(face=>face.person_id).filter(Boolean));
    if (!names || typeof names!=='object' || Array.isArray(names) || Object.entries(names).some(([id,name])=>!people.has(id) || (name!=='' && !cast.has(name)))) throw new Error('Associazione personaggio non valida');
    const seen=new Set();
    const updated=request.intervals.map(item=>{
      const original=review.intervals.find(s=>s.segment_id===item.segment_id);
      if (!original || seen.has(item.segment_id)) throw new Error('Intervallo visivo inatteso'); seen.add(item.segment_id);
      if (!['wide','medium','close','detail','unknown'].includes(item.shot_size)) throw new Error('Scala non valida');
      if (!Array.isArray(item.visible_subjects) || item.visible_subjects.some(name=>!cast.has(name))) throw new Error('Personaggio non presente nel copione');
      return {...original,shot_size:item.shot_size,confidence:1,visible_subjects:[...new Set(item.visible_subjects)],reviewed:true,source:'manual'};
    });
    if (!updated.length) throw new Error('Nessuna still disponibile: ripeti la revisione visiva');
    // Compute first: a failed rebuild must not mark stale decisions as confirmed.
    let plan=analysis.plan;
    if (analysis.planningSources?.length && analysis.takes?.every(t=>t.confirmed)) {
      this.onProgress?.({phase:'plan',phaseIndex:6,percent:89,label:'Ricalcolo con campi e personaggi confermati'});
      plan=await this.buildPlan({beats:analysis.parsedBeats,sources:analysis.planningSources,shots:updated,directions:this.state.directions,semantic:true,fps:this.state.fps || 25},300000);
      plan=this.keepReactionChoices(plan);
      this.onProgress?.({phase:'pacing',phaseIndex:7,percent:95,label:'Verifico pause e reazioni prima della risoluzione'});
      plan=await this.pacePlan({plan,sources:analysis.planningSources,audio:analysis.audio || {},shots:updated,beats:analysis.parsedBeats,fps:this.state.fps || 25,settings:this.state.pacingSettings});
    }
    if(plan)plan.visual_review_required=false;
    analysis.shots=updated; analysis.visualReview={...review,intervals:updated,confirmed:true,personNames:names};analysis.plan=plan;
    this.onProgress?.({phase:'complete',phaseIndex:8,percent:100,label:'Campi e personaggi confermati; piano aggiornato'});
    return this.getReviewState();
  }
  async confirmTakes(segments) {
    const grouped = new Map();
    for (const segment of segments) { if (!grouped.has(segment.media_id)) grouped.set(segment.media_id, []); grouped.get(segment.media_id).push(segment); }
    const takes = this.state.analysis?.takes || [];
    if (grouped.size !== takes.length || [...grouped.keys()].some(mediaId => !takes.some(take => take.media_id === mediaId))) throw new Error('Elenco take inatteso; ripeti l’analisi');
    for (const group of takes) {
      const items = grouped.get(group.media_id);
      if (!items) throw new Error(`Confini take mancanti per ${group.media_name}`);
      items.sort((a, b) => a.start_frame - b.start_frame);
      if (items[0].start_frame !== 0 || items[items.length - 1].end_frame !== group.duration_frames || items.some((item, index) => !Number.isInteger(item.start_frame) || !Number.isInteger(item.end_frame) || item.end_frame <= item.start_frame || (index && items[index - 1].end_frame !== item.start_frame))) throw new Error(`Segmenti sovrapposti o fuori dal media ${group.media_name}`);
      group.segments = items.map((item, index) => ({ ...item, take_index: index + 1, boundary_source: item.start_frame === 0 && item.end_frame === group.duration_frames ? 'whole_clip' : 'manual', confirmed: true }));
      group.confirmed = true;
    }
    const sources = takes.flatMap(group => group.segments.map(take => ({ ...this.state.transcripts.find(source => source.media_id === group.media_id), ...take,
      segments: this.state.transcripts.find(source => source.media_id === group.media_id).segments.filter(segment => segment.start_frame >= take.start_frame && segment.start_frame < take.end_frame) })));
    this.state.analysis.planningSources = sources;
    const previousPlan=this.state.analysis.plan;
    this.state.analysis.plan = await this.buildPlan( { beats: this.state.analysis.parsedBeats, sources, shots: this.state.analysis.shots, directions:this.state.directions, semantic: true, fps: this.state.fps || 25 },300000);
    this.keepReactionChoices(this.state.analysis.plan,previousPlan);
    if (this.state.analysis.visualReview) this.state.analysis.plan.visual_review_required=Boolean(this.state.uiDraft?.visual?.dirty);
    return this.applyPacing();
  }
}

module.exports = { annotateSceneEdits, Session, GroqClient, workerEnvironment, prepareReviewTimeline };
