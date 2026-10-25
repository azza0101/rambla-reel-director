'use strict';
const fs = require('node:fs/promises');
const path = require('node:path');
const { spawn } = require('node:child_process');


const DEFAULT_DIRECTIONS={profile:'VIDEO COLICHE',notes:'Aprire con la master per il contesto. Preferire i piani di chi parla; tornare alla master soprattutto negli scambi lunghi, su un cambio di parlante, o al rilascio della tensione. Evitare alternanze a conteggio fisso. Durante tensione e crescendo mantenere le strette fino al sollievo o alla risoluzione. Aprire sulla larga per distendere. Esempio: dopo l’invito a dormire nel suo letto, primo piano di lui prima dello sbotto, larga quando rifiuta. La reazione richiede copertura verificata: non viene inventata.',markers:{}};
function validateDirections(value){
 if(!value || typeof value!=='object' || Array.isArray(value) || !['none','VIDEO COLICHE'].includes(value.profile) || typeof value.notes!=='string' || value.notes.length>20000 || !value.markers || typeof value.markers!=='object' || Array.isArray(value.markers) || Object.keys(value.markers).length>10000 || Object.entries(value.markers).some(([id,role])=>!id || id.length>128 || !['tension','resolution','free'].includes(role)))throw new Error('Direzioni di montaggio non valide');
 return JSON.parse(JSON.stringify(value));
}

function validateDraft(value){
 const obj=v=>v && typeof v==='object' && !Array.isArray(v),str=v=>typeof v==='string',list=(v,check)=>Array.isArray(v) && v.length<=10000 && v.every(check),scalar=v=>str(v)||Number.isFinite(v),sizes=['wide','medium','close','detail','unknown'];
 if(!obj(value) || Buffer.byteLength(JSON.stringify(value))>512*1024 || value.takes!==undefined && !list(value.takes,v=>obj(v)&&str(v.take_id)&&scalar(v.start_frame)&&scalar(v.end_frame)) || value.beats!==undefined && !list(value.beats,v=>obj(v)&&str(v.beat_id)&&scalar(v.start)&&scalar(v.end)&&sizes.includes(v.scale)))throw new Error('Bozza progetto non valida');
 if(value.visual!==undefined && (!obj(value.visual) || value.visual.dirty!==undefined && typeof value.visual.dirty!=='boolean' || value.visual.person_names!==undefined && (!obj(value.visual.person_names)||!Object.values(value.visual.person_names).every(str)) || value.visual.intervals!==undefined && !list(value.visual.intervals,v=>obj(v)&&str(v.segment_id)&&sizes.includes(v.shot_size)&&list(v.visible_subjects,str))))throw new Error('Bozza visiva del progetto non valida');
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

function prepareReviewTimeline(plan, confirmed) {
  if (confirmed !== true) throw new Error('Conferma gli abbinamenti prima di creare la timeline');
  if (plan?.visual_review_required) throw new Error('Conferma le inquadrature e i personaggi nella revisione visiva');
  if (!plan?.decisions?.length) throw new Error('Nessuna battuta abbinata: timeline non creata');
  return { decisions: plan.decisions, omitted: plan.unmatched_beats?.length || 0 };
}

class Session {
  constructor(root, workerPath, python = process.env.PREMONTATO_PYTHON || path.join(__dirname, 'runtime', 'python.exe')) {
    this.root = root; this.workerPath = workerPath; this.python = python;
    this.state = { directions:JSON.parse(JSON.stringify(DEFAULT_DIRECTIONS)), stage: 'idle', script: null, media: [], analysis: null, error: null, pacingSettings: { enabled: true, max_pause_seconds: .45, minimum_shot_seconds: 1.2, respect_script_pauses: true, comic_hold_seconds: 1 } };
    this.documentId=require('node:crypto').randomUUID(); this.projectFile=null; this.lastSavedAt=null; this.lastAutosaveAt=null; this.saveError=null;
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
  async setScript(file) {
    const text = path.extname(file).toLowerCase() === '.pdf'
      ? (await this.request('extract_pdf_script', { path: file })).text
      : await fs.readFile(file, 'utf8');
    this.state.directions={...(this.state.directions || DEFAULT_DIRECTIONS),markers:{}}; this.state.script = { path: file, text }; this.state.analysis = null; return { name: path.basename(file) };
  }
  setMedia(records, identity) { this.state.media = records; this.state.transcripts = []; this.state.mediaFingerprints=null; this.state.uiDraft=null; this.state.analysis = null; this.state.projectId = identity.projectId; this.state.timelineId = identity.timelineId; return records.map(({ media_id, name, duration_frames, people = [] }) => ({ media_id, name, duration_frames, people })); }
  assertContext(identity) {
    const ids = (identity.selected || []).map(item => item.media_id);
    if (identity.projectId !== this.state.projectId || identity.timelineId !== this.state.timelineId || ids.length !== this.state.media.length || ids.some((id, index) => id !== this.state.media[index].media_id)) {
      throw new Error('Progetto, timeline o selezione media cambiati: riseleziona le clip e ricalcola');
    }
  }
  async analyze() {
    if (!this.state.script || !this.state.media.length) throw new Error('Prima scegli un copione e media dal Media Pool');
    if (this.state.stage === 'analyzing') throw new Error('Analisi già in corso');
    this.state.mediaFingerprints=await this.captureMediaFingerprints();
    this.state.stage = 'analyzing';
    this.state.error = null;
    let lastPhaseIndex = 0;
    const startedAt = Date.now(); let lastPhase, phaseStartedAt = startedAt;
    const progress = (phase, phaseIndex, percent, label, current, total, skipped=false) => {
      if (phaseIndex >= 0) lastPhaseIndex = phaseIndex;
      if (phase !== lastPhase) { lastPhase = phase; phaseStartedAt = Date.now(); }
      this.onProgress?.({ phase, phaseIndex, percent: Math.round(percent), label, current, total, skipped, elapsedSeconds: Math.round((Date.now()-startedAt)/1000), phaseElapsedSeconds: Math.round((Date.now()-phaseStartedAt)/1000) });
    };
    try {
      progress('script', 0, 0, 'Leggo e separo le scene del copione');
      const parsed = await this.request('parse_script', { text: this.state.script.text });
      const sources = this.state.transcripts || [];
      progress('scene', 1, 12, 'Individuo la scena che corrisponde al parlato');
      const sceneSelection = await this.request('select_scene', {
        scenes: parsed.scenes, transcript: sources.flatMap(source => source.segments)
      });
      const selectedScene = sceneSelection.scene;
      const beats = selectedScene ? selectedScene.beats : [];
      const shots = [];
      let shotCacheHits = 0;
      const shotSources = sources.filter(source => source.path);
      progress('shots', 2, 24, shotSources.length ? `Analisi inquadrature: 0/${shotSources.length} clip` : 'Nessun file video da analizzare');
      for (let i = 0; i < shotSources.length; i++) {
        const source = shotSources[i];
        progress('shots', 2, 24 + (i / shotSources.length) * 38, `Analizzo le inquadrature di ${source.name}`, i, shotSources.length);
        try { const result = await this.request('analyze_shots', { media: source, sample_fps: 2 }, 20 * 60 * 1000, event => progress('shots', 2, 24 + ((i + event.frame / Math.max(1, event.total)) / shotSources.length) * 38, `YuNet · ${source.name} · ${Math.round(event.frame / Math.max(1, event.total) * 100)}%`, i + event.frame / Math.max(1,event.total), shotSources.length)); shots.push(...result.segments); if (result.cache_hit) shotCacheHits += 1; }
        catch (error) { this.state.error = `Analisi inquadrature non disponibile per ${source.name}: ${error.message}`; }
        progress('shots', 2, 24 + ((i + 1) / shotSources.length) * 38, `Inquadrature: ${i + 1}/${shotSources.length} clip`, i + 1, shotSources.length);
      }
      if(shotSources.length)progress('visual',3,62,'Still e volti: caricamento su richiesta',0,0,true);
      const visualReview = null; // Still and identity clustering are explicit visual-debug work.
      const takes = [];
      progress('takes', 4, 68, `Individuo i confini delle take: 0/${sources.length} clip`);
      for (let i = 0; i < sources.length; i++) {
        const source = sources[i];
        const proposals = await this.request('propose_take_segments', { media: source, transcript: source.segments, fps: source.fps || this.state.fps || 25, beats });
        takes.push({ media_id: source.media_id, media_name: source.name, duration_frames: source.duration_frames,
          confirmed: proposals.length === 1 && proposals[0].boundary_source === 'whole_clip', segments: proposals });
        progress('takes', 4, 68 + ((i + 1) / Math.max(1, sources.length)) * 12, `Confini take: ${i + 1}/${sources.length} clip`, i + 1, sources.length);
      }
      const planningSources = takes.flatMap(group => group.confirmed ? group.segments.map(take => ({ ...sources.find(source => source.media_id === group.media_id), ...take,
        segments: sources.find(source => source.media_id === group.media_id).segments.filter(segment => segment.start_frame >= take.start_frame && segment.start_frame < take.end_frame) })) : []);
      const audio = {};
      const audioSources = this.state.pacingSettings.enabled ? sources.filter(source => source.path) : [];
      progress('audio', 5, 81, 'Misuro le pause nell’audio locale');
      for (let i=0;i<audioSources.length;i++) {
        const source=audioSources[i];
        progress('audio',5,81+(i/Math.max(1,audioSources.length))*7, 'Audio · '+source.name,i,audioSources.length);
        try { audio[source.media_id] = await this.request('analyze_audio',{media:source},180000); }
        catch(error) { audio[source.media_id] = {status:'unavailable',reason:error.message}; }
        progress('audio',5,81+((i+1)/audioSources.length)*7,'Audio · '+source.name+' · '+(audio[source.media_id].status==='ok' ? (audio[source.media_id].cache_hit?'cache verificata':'misurato') : 'non disponibile: pause conservate'),i+1,audioSources.length);
      }
      progress('plan', 6, 89, 'Verifico significato e attacco delle battute nelle take confermate');
      let plan = selectedScene && takes.every(group => group.confirmed)
        ? await this.buildPlan( { beats, sources: planningSources, shots, directions:this.state.directions, semantic: true, fps: this.state.fps || 25 },300000) : null;
      progress('pacing',7,95,'Verifico pause e reazioni prima della risoluzione');
      if(plan)plan=this.keepReactionChoices(plan);
      if (plan) plan=await this.request('pace_plan',{plan,sources:planningSources,audio,beats,shots,fps:this.state.fps || 25,settings:this.state.pacingSettings});
      if (plan) plan.visual_review_required = false;
      const warnings = selectedScene
        ? [...(plan?.warnings || ['Conferma i confini delle take suggerite prima di calcolare il premontato.'])]
        : ['Non ho trovato una corrispondenza sufficientemente chiara tra dialoghi e copione; controlla trascrizione e clip selezionate.'];
      if (shotCacheHits) warnings.push(`Analisi visiva riusata dalla cache locale per ${shotCacheHits} clip.`);
      if (this.state.error) warnings.push(this.state.error);
      this.state.analysis = { script: parsed, sceneSelection, selectedScene, warnings, takes, shots, audio, planningSources, plan, visualReview, parsedBeats: beats };
      this.state.stage = 'review';
      progress('complete', 8, 100, 'Analisi completata');
      return this.getReviewState();
    } catch (error) { this.state.error = error.message; this.state.stage = 'error'; progress('error', lastPhaseIndex, 0, `Analisi interrotta: ${error.message}`); throw error; }
  }
  async buildPlan(payload, timeoutMs=300000, onProgress) {
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
  async cancelAnalysis() { this.failAll(new Error('Analisi annullata')); this.child?.kill(); this.child = null; this.state.stage = 'idle'; return true; }
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
  getReviewState() { return { projectStatus:this.projectStatus(), uiDraft:this.state.uiDraft, stage: this.state.stage, scriptName: this.state.script ? path.basename(this.state.script.path) : null,
    media: this.state.media.map(({ media_id, name, duration_frames, people = [] }) => ({ media_id, name, duration_frames, people })), analysis: this.state.analysis, directions:this.state.directions || DEFAULT_DIRECTIONS, pacingSettings: this.state.pacingSettings, error: this.state.error }; }
  setTranscripts(sources, fps, identity) { this.assertContext(identity); this.state.transcripts = sources; this.state.fps = fps; this.state.analysis = null; return { count: sources.reduce((sum, source) => sum + source.segments.length, 0) }; }
  updateDecision(request) {
    const plan = this.state.analysis?.plan;
    const decision = plan?.decisions.find(item => item.beat_id === request?.beat_id);
    if (!decision) throw new Error('Battuta non disponibile');
    const pauseOnly=(request.preserve_pause !== undefined || request.reaction_enabled !== undefined) && !['start_frame','end_frame','shot_size','alternative_index'].some(key=>request[key]!==undefined);
    const original=pauseOnly ? plan.base_decisions?.find(item=>item.beat_id===decision.beat_id) : null;
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
    delete updated.source_ranges; delete updated.pacing; delete updated.reaction_before;
    const base=plan.base_decisions?.findIndex(item=>item.beat_id===updated.beat_id);
    if (base !== undefined && base>=0) plan.base_decisions[base]={...updated};
    plan.decisions[plan.decisions.indexOf(decision)] = updated;
    let cursor = 0;
    for (const item of plan.decisions) { item.timeline_start_frame = cursor; cursor += item.source_ranges?.reduce((sum,r)=>sum+r.end_frame-r.start_frame,0) ?? item.end_frame - item.start_frame; }
    return this.getReviewState();
  }
  keepReactionChoices(plan, previous=this.state.analysis?.plan) {
    const choices=new Map((previous?.decisions || []).filter(d=>typeof d.reaction_enabled==='boolean').map(d=>[d.beat_id,d.reaction_enabled]));
    for(const decision of plan?.decisions || [])if(choices.has(decision.beat_id))decision.reaction_enabled=choices.get(decision.beat_id);
    return plan;
  }
  async applyPacing() {
    if (!this.state.analysis?.plan) return this.getReviewState();
    this.state.analysis.plan=await this.request('pace_plan',{plan:this.state.analysis.plan,sources:this.state.analysis?.planningSources || this.state.transcripts || [],audio:this.state.analysis.audio || {},shots:this.state.analysis.shots || [],beats:this.state.analysis.parsedBeats || [],fps:this.state.fps || 25,settings:this.state.pacingSettings});
    return this.getReviewState();
  }
  async setDirections(value) {
    const directions=validateDirections(value),analysis=this.state.analysis;
    const beats=analysis?.parsedBeats || [];
    if(Object.keys(directions.markers).some(id=>!beats.some(b=>b.beat_id===id && b.kind==='dialogue')))throw new Error('Battuta delle direzioni non presente nella scena');
    let plan=analysis?.plan;
    const previous=this.state.directions || DEFAULT_DIRECTIONS;
    const changed=directions.profile!==previous.profile || JSON.stringify(Object.entries(directions.markers).sort())!==JSON.stringify(Object.entries(previous.markers || {}).sort());
    if(changed && analysis?.planningSources?.length && analysis.takes?.every(group=>group.confirmed)) {
      this.onProgress?.({phase:'plan',phaseIndex:6,percent:89,label:'Ricalcolo secondo le direzioni di montaggio'});
      plan=await this.buildPlan({beats,sources:analysis.planningSources,shots:analysis.shots || [],directions,semantic:true,fps:this.state.fps || 25},300000);
      plan=this.keepReactionChoices(plan);
      this.onProgress?.({phase:'pacing',phaseIndex:7,percent:95,label:'Verifico pause e reazioni prima della risoluzione'});
      plan=await this.request('pace_plan',{plan,sources:analysis.planningSources,audio:analysis.audio || {},shots:analysis.shots || [],beats,fps:this.state.fps || 25,settings:this.state.pacingSettings});
      if(analysis.visualReview)plan.visual_review_required=Boolean(analysis.plan?.visual_review_required);
    }
    this.state.directions=directions;if(analysis)analysis.plan=plan;
    this.onProgress?.({phase:'complete',phaseIndex:8,percent:100,label:'Direzioni salvate; controlla le scelte narrative'});
    return this.getReviewState();
  }
  async setPacing(options) {
    const plan=this.state.analysis?.plan || {decisions:[],warnings:[]};
    const result=await this.request('pace_plan',{plan,sources:this.state.analysis?.planningSources || this.state.transcripts || [],audio:this.state.analysis?.audio || {},shots:this.state.analysis?.shots || [],beats:this.state.analysis?.parsedBeats || [],fps:this.state.fps || 25,settings:{...this.state.pacingSettings,...options}});
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
      plan=await this.request('pace_plan',{plan,sources:analysis.planningSources,audio:analysis.audio || {},shots:updated,beats:analysis.parsedBeats,fps:this.state.fps || 25,settings:this.state.pacingSettings});
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

module.exports = { Session, workerEnvironment, prepareReviewTimeline };
