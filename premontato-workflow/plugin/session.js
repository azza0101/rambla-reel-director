'use strict';
const fs = require('node:fs/promises');
const path = require('node:path');
const { spawn } = require('node:child_process');

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
    this.state = { stage: 'idle', script: null, media: [], analysis: null, error: null, pacingSettings: { enabled: true, max_pause_seconds: .45, minimum_shot_seconds: 1.2, respect_script_pauses: true, comic_hold_seconds: 1 } };
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
    this.state.script = { path: file, text }; this.state.analysis = null; return { name: path.basename(file) };
  }
  setMedia(records, identity) { this.state.media = records; this.state.transcripts = []; this.state.analysis = null; this.state.projectId = identity.projectId; this.state.timelineId = identity.timelineId; return records.map(({ media_id, name, duration_frames, people = [] }) => ({ media_id, name, duration_frames, people })); }
  assertContext(identity) {
    const ids = (identity.selected || []).map(item => item.media_id);
    if (identity.projectId !== this.state.projectId || identity.timelineId !== this.state.timelineId || ids.length !== this.state.media.length || ids.some((id, index) => id !== this.state.media[index].media_id)) {
      throw new Error('Progetto, timeline o selezione media cambiati: riseleziona le clip e ricalcola');
    }
  }
  async analyze() {
    if (!this.state.script || !this.state.media.length) throw new Error('Prima scegli un copione e media dal Media Pool');
    if (this.state.stage === 'analyzing') throw new Error('Analisi già in corso');
    this.state.stage = 'analyzing';
    this.state.error = null;
    let lastPhaseIndex = 0;
    const startedAt = Date.now(); let lastPhase, phaseStartedAt = startedAt;
    const progress = (phase, phaseIndex, percent, label, current, total) => {
      if (phaseIndex >= 0) lastPhaseIndex = phaseIndex;
      if (phase !== lastPhase) { lastPhase = phase; phaseStartedAt = Date.now(); }
      this.onProgress?.({ phase, phaseIndex, percent: Math.round(percent), label, current, total, elapsedSeconds: Math.round((Date.now()-startedAt)/1000), phaseElapsedSeconds: Math.round((Date.now()-phaseStartedAt)/1000) });
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
      let visualReview = null;
      if (shotSources.length) {
        progress('visual', 3, 62, 'Estraggo le still e confronto i volti localmente');
        visualReview = await this.request('visual_review', {media:shotSources,shots}, 20*60*1000, event => progress('visual',3,62+((event.clip_index+event.current/Math.max(1,event.total))/Math.max(1,event.clip_total))*6,'Still e volti · '+event.name+' · '+event.current+'/'+event.total,event.clip_index+event.current/Math.max(1,event.total),event.clip_total));
      }
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
      progress('plan', 6, 89, 'Abbino il significato delle battute alle take confermate');
      let plan = selectedScene && takes.every(group => group.confirmed)
        ? await this.request('build_plan', { beats, sources: planningSources, shots, semantic: true, fps: this.state.fps || 25 },300000) : null;
      progress('pacing',7,95,'Regolo pause e durata delle inquadrature');
      if (plan) plan=await this.request('pace_plan',{plan,sources:planningSources,audio,beats,fps:this.state.fps || 25,settings:this.state.pacingSettings});
      if (plan && visualReview) plan.visual_review_required = !visualReview.confirmed;
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
  getReviewState() { return { stage: this.state.stage, scriptName: this.state.script ? path.basename(this.state.script.path) : null,
    media: this.state.media.map(({ media_id, name, duration_frames, people = [] }) => ({ media_id, name, duration_frames, people })), analysis: this.state.analysis, pacingSettings: this.state.pacingSettings, error: this.state.error }; }
  setTranscripts(sources, fps, identity) { this.assertContext(identity); this.state.transcripts = sources; this.state.fps = fps; this.state.analysis = null; return { count: sources.reduce((sum, source) => sum + source.segments.length, 0) }; }
  updateDecision(request) {
    const plan = this.state.analysis?.plan;
    const decision = plan?.decisions.find(item => item.beat_id === request?.beat_id);
    if (!decision) throw new Error('Battuta non disponibile');
    const pauseOnly=request.preserve_pause !== undefined && !['start_frame','end_frame','shot_size','alternative_index'].some(key=>request[key]!==undefined);
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
    if (request.preserve_pause !== undefined && typeof request.preserve_pause !== 'boolean') throw new Error('Blocco pausa non valido');
    const manual=updated.manual || ['start_frame','end_frame','shot_size','alternative_index'].some(key=>request[key]!==undefined);
    Object.assign(updated, { start_frame: start, end_frame: end, shot_size: request.shot_size ?? updated.shot_size, manual, preserve_pause: request.preserve_pause ?? updated.preserve_pause });
    delete updated.source_ranges; delete updated.pacing;
    const base=plan.base_decisions?.findIndex(item=>item.beat_id===updated.beat_id);
    if (base !== undefined && base>=0) plan.base_decisions[base]={...updated};
    plan.decisions[plan.decisions.indexOf(decision)] = updated;
    let cursor = 0;
    for (const item of plan.decisions) { item.timeline_start_frame = cursor; cursor += item.source_ranges?.reduce((sum,r)=>sum+r.end_frame-r.start_frame,0) ?? item.end_frame - item.start_frame; }
    return this.getReviewState();
  }
  async applyPacing() {
    if (!this.state.analysis?.plan) return this.getReviewState();
    this.state.analysis.plan=await this.request('pace_plan',{plan:this.state.analysis.plan,sources:this.state.analysis?.planningSources || this.state.transcripts || [],audio:this.state.analysis.audio || {},beats:this.state.analysis.parsedBeats || [],fps:this.state.fps || 25,settings:this.state.pacingSettings});
    return this.getReviewState();
  }
  async setPacing(options) {
    const plan=this.state.analysis?.plan || {decisions:[],warnings:[]};
    const result=await this.request('pace_plan',{plan,sources:this.state.analysis?.planningSources || this.state.transcripts || [],audio:this.state.analysis?.audio || {},beats:this.state.analysis?.parsedBeats || [],fps:this.state.fps || 25,settings:{...this.state.pacingSettings,...options}});
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
      plan=await this.request('build_plan',{beats:analysis.parsedBeats,sources:analysis.planningSources,shots:updated,semantic:true,fps:this.state.fps || 25},300000);
      plan=await this.request('pace_plan',{plan,sources:analysis.planningSources,audio:analysis.audio || {},beats:analysis.parsedBeats,fps:this.state.fps || 25,settings:this.state.pacingSettings});
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
    this.state.analysis.plan = await this.request('build_plan', { beats: this.state.analysis.parsedBeats, sources, shots: this.state.analysis.shots, semantic: true, fps: this.state.fps || 25 },300000);
    if (this.state.analysis.visualReview) this.state.analysis.plan.visual_review_required=!this.state.analysis.visualReview.confirmed;
    return this.applyPacing();
  }
}

module.exports = { Session, workerEnvironment, prepareReviewTimeline };
