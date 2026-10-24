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
  if (!plan?.decisions?.length) throw new Error('Nessuna battuta abbinata: timeline non creata');
  return { decisions: plan.decisions, omitted: plan.unmatched_beats?.length || 0 };
}

class Session {
  constructor(root, workerPath, python = process.env.PREMONTATO_PYTHON || path.join(__dirname, 'runtime', 'python.exe')) {
    this.root = root; this.workerPath = workerPath; this.python = python;
    this.state = { stage: 'idle', script: null, media: [], analysis: null, error: null };
    this.child = null; this.pending = new Map(); this.counter = 0;
  }
  async request(action, payload = {}, timeoutMs = 30000, onProgress) {
    if (!this.child) {
      this.child = spawn(this.python, ['-E', '-s', this.workerPath], { stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true,
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
    const progress = (phase, phaseIndex, percent, label, current, total) => {
      if (phaseIndex >= 0) lastPhaseIndex = phaseIndex;
      this.onProgress?.({ phase, phaseIndex, percent: Math.round(percent), label, current, total });
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
        progress('shots', 2, 24 + (i / shotSources.length) * 42, `Analizzo le inquadrature di ${source.name}`, i, shotSources.length);
        try { const result = await this.request('analyze_shots', { media: source, sample_fps: 2 }, 20 * 60 * 1000, event => progress('shots', 2, 24 + ((i + event.frame / Math.max(1, event.total)) / shotSources.length) * 42, `YuNet · ${source.name} · ${Math.round(event.frame / Math.max(1, event.total) * 100)}%`, i, shotSources.length)); shots.push(...result.segments); if (result.cache_hit) shotCacheHits += 1; }
        catch (error) { this.state.error = `Analisi inquadrature non disponibile per ${source.name}: ${error.message}`; }
        progress('shots', 2, 24 + ((i + 1) / shotSources.length) * 42, `Inquadrature: ${i + 1}/${shotSources.length} clip`, i + 1, shotSources.length);
      }
      const takes = [];
      progress('takes', 3, 68, `Individuo i confini delle take: 0/${sources.length} clip`);
      for (let i = 0; i < sources.length; i++) {
        const source = sources[i];
        const proposals = await this.request('propose_take_segments', { media: source, transcript: source.segments, fps: source.fps || this.state.fps || 25, beats });
        takes.push({ media_id: source.media_id, media_name: source.name, duration_frames: source.duration_frames,
          confirmed: proposals.length === 1 && proposals[0].boundary_source === 'whole_clip', segments: proposals });
        progress('takes', 3, 68 + ((i + 1) / Math.max(1, sources.length)) * 17, `Confini take: ${i + 1}/${sources.length} clip`, i + 1, sources.length);
      }
      const planningSources = takes.flatMap(group => group.confirmed ? group.segments.map(take => ({ ...sources.find(source => source.media_id === group.media_id), ...take,
        segments: sources.find(source => source.media_id === group.media_id).segments.filter(segment => segment.start_frame >= take.start_frame && segment.start_frame < take.end_frame) })) : []);
      progress('plan', 4, 88, 'Abbino le battute alle take confermate');
      const plan = selectedScene && takes.every(group => group.confirmed)
        ? await this.request('build_plan', { beats, sources: planningSources, shots, semantic: true, fps: this.state.fps || 25 }) : null;
      const warnings = selectedScene
        ? [...(plan?.warnings || ['Conferma i confini delle take suggerite prima di calcolare il premontato.'])]
        : ['Non ho trovato una corrispondenza sufficientemente chiara tra dialoghi e copione; controlla trascrizione e clip selezionate.'];
      if (shotCacheHits) warnings.push(`Analisi visiva riusata dalla cache locale per ${shotCacheHits} clip.`);
      if (this.state.error) warnings.push(this.state.error);
      this.state.analysis = { script: parsed, sceneSelection, selectedScene, warnings, takes, shots, plan, parsedBeats: beats };
      this.state.stage = 'review';
      progress('complete', 5, 100, 'Analisi completata');
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
    media: this.state.media.map(({ media_id, name, duration_frames, people = [] }) => ({ media_id, name, duration_frames, people })), analysis: this.state.analysis, error: this.state.error }; }
  setTranscripts(sources, fps, identity) { this.assertContext(identity); this.state.transcripts = sources; this.state.fps = fps; this.state.analysis = null; return { count: sources.reduce((sum, source) => sum + source.segments.length, 0) }; }
  updateDecision(request) {
    const plan = this.state.analysis?.plan;
    const decision = plan?.decisions.find(item => item.beat_id === request?.beat_id);
    if (!decision) throw new Error('Battuta non disponibile');
    let updated = { ...decision };
    if (request.alternative_index !== undefined) {
      const alt = decision.alternatives?.[request.alternative_index];
      if (!Number.isInteger(request.alternative_index) || !alt) throw new Error('Alternativa non valida');
      updated = { ...updated, ...alt, alternatives: [decision, ...decision.alternatives.filter((_, index) => index !== request.alternative_index)].map(({ alternatives, ...item }) => item) };
    }
    const media = this.state.media.find(item => item.media_id === updated.media_id);
    const start = request.start_frame ?? updated.start_frame, end = request.end_frame ?? updated.end_frame;
    if (!media || !Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end > media.duration_frames || end <= start) throw new Error('Intervallo sorgente non valido');
    if (request.shot_size !== undefined && !['wide','medium','close','detail','unknown'].includes(request.shot_size)) throw new Error('Scala non valida');
    Object.assign(updated, { start_frame: start, end_frame: end, shot_size: request.shot_size ?? updated.shot_size, manual: true });
    plan.decisions[plan.decisions.indexOf(decision)] = updated;
    let cursor = 0;
    for (const item of plan.decisions) { item.timeline_start_frame = cursor; cursor += item.end_frame - item.start_frame; }
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
    this.state.analysis.plan = await this.request('build_plan', { beats: this.state.analysis.parsedBeats, sources, shots: this.state.analysis.shots, semantic: true, fps: this.state.fps || 25 });
    return this.getReviewState();
  }
}

module.exports = { Session, workerEnvironment, prepareReviewTimeline };
