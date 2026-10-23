'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const { Session, workerEnvironment, prepareReviewTimeline } = require('../../plugin/session');

test('worker process does not inherit unrelated API credentials', () => {
  const env = workerEnvironment({ PATH: 'C:/Python', SYSTEMROOT: 'C:/Windows', GROQ_API_KEY: 'secret', OPENAI_API_KEY: 'secret' }, 'C:/cache');
  assert.equal(env.PATH, 'C:/Python');
  assert.equal(env.PREMONTATO_CACHE_DIR, 'C:/cache');
  assert.equal(env.GROQ_API_KEY, undefined);
  assert.equal(env.OPENAI_API_KEY, undefined);
});

test('media reselection invalidates transcripts and records Resolve identity', () => {
  const session = new Session('unused', 'unused');
  session.state.transcripts = [{ media_id: 'old' }];
  session.setMedia([{ media_id: 'new', name: 'clip', duration_frames: 100 }], { projectId: 'p', timelineId: 't' });
  assert.deepEqual(session.state.transcripts, []);
  assert.equal(session.state.projectId, 'p');
  assert.equal(session.state.timelineId, 't');
});

test('PDF scripts are extracted by the local worker instead of being decoded as UTF-8', async () => {
  const session = new Session('unused', 'unused');
  let request;
  session.request = async (...args) => { request = args; return { text: 'SCENA 01 INT. SALOTTO - SERA' }; };
  const selected = await session.setScript('Z:/scripts/Pare brutto.pdf');
  assert.equal(request[0], 'extract_pdf_script');
  assert.equal(request[1].path, 'Z:/scripts/Pare brutto.pdf');
  assert.equal(session.state.script.text, 'SCENA 01 INT. SALOTTO - SERA');
  assert.equal(selected.name, 'Pare brutto.pdf');
});

test('analysis scopes planning to the single automatically matched screenplay scene', async () => {
  const session = new Session('unused', 'unused');
  session.state.script = { path: 'script.pdf', text: 'full script' };
  session.setMedia([{ media_id: 'm', name: 'rushes', duration_frames: 100 }], { projectId: 'p', timelineId: 't' });
  session.setTranscripts([{ media_id: 'm', name: 'rushes', duration_frames: 100, fps: 25, path: '', segments: [
    { segment_id: 's', media_id: 'm', start_frame: 5, end_frame: 20, text: 'line', speaker_name: 'LUCA' }
  ] }], 25, { projectId: 'p', timelineId: 't', selected: [{ media_id: 'm' }] });
  const calls = [];
  const progress = [];
  session.onProgress = event => progress.push(event);
  session.request = async (action, payload) => {
    calls.push({ action, payload });
    if (action === 'parse_script') return { scenes: [
      { scene_id: 'scene-a', heading: 'SCENA 01', beats: [{ beat_id: 'a1', kind: 'dialogue', text: 'line' }] },
      { scene_id: 'scene-b', heading: 'SCENA 02', beats: [{ beat_id: 'b1', kind: 'dialogue', text: 'other' }] }
    ] };
    if (action === 'select_scene') return { scene: { scene_id: 'scene-a', heading: 'SCENA 01', beats: [{ beat_id: 'a1', kind: 'dialogue', text: 'line' }] }, confidence: 0.91, candidates: [] };
    if (action === 'propose_take_segments') return [{ take_id: 'm:take:1', media_id: 'm', start_frame: 0, end_frame: 100, take_index: 1, boundary_source: 'whole_clip' }];
    if (action === 'build_plan') return { decisions: [], unmatched_beats: [], warnings: [] };
    throw new Error(`unexpected action ${action}`);
  };
  await session.analyze();
  const planCall = calls.find(call => call.action === 'build_plan');
  assert.deepEqual(planCall.payload.beats.map(beat => beat.beat_id), ['a1']);
  assert.equal(session.state.analysis.selectedScene.heading, 'SCENA 01');
  assert.deepEqual([...new Set(progress.map(event => event.phase))], ['script', 'scene', 'shots', 'takes', 'plan', 'complete']);
  assert.equal(progress.at(-1).percent, 100);
});

test('rejects transcription results from a different timeline', () => {
  const session = new Session('unused', 'unused');
  session.setMedia([{ media_id: 'm', name: 'clip', duration_frames: 100 }], { projectId: 'p', timelineId: 't1' });
  assert.throws(() => session.setTranscripts([], 25, { projectId: 'p', timelineId: 't2' }), /cambiati/);
});

test('rejects a changed Media Pool selection even inside the same project', () => {
  const session = new Session('unused', 'unused');
  session.setMedia([{ media_id: 'm1', name: 'one', duration_frames: 100 }], { projectId: 'p', timelineId: 't' });
  assert.throws(() => session.assertContext({ projectId: 'p', timelineId: 't', selected: [{ media_id: 'm2' }] }), /selezione media cambiati/);
});

test('rejects take edits with source gaps before rebuilding a plan', async () => {
  const session = new Session('unused', 'unused');
  session.state.transcripts = [{ media_id: 'm', segments: [] }];
  session.state.analysis = { parsedBeats: [], shots: [], takes: [{ media_id: 'm', media_name: 'clip', duration_frames: 100,
    segments: [{ media_id: 'm', take_id: 'a', start_frame: 0, end_frame: 50 }, { media_id: 'm', take_id: 'b', start_frame: 50, end_frame: 100 }] }] };
  await assert.rejects(session.confirmTakes([{ media_id: 'm', take_id: 'a', start_frame: 0, end_frame: 45 },
    { media_id: 'm', take_id: 'b', start_frame: 50, end_frame: 100 }]), /sovrapposti o fuori/);
});

test('stops the idle Python worker before replacing its embedded runtime', async () => {
  const session = new Session('unused', 'unused');
  const child = new EventEmitter();
  child.kill = () => setImmediate(() => child.emit('exit', 0));
  session.child = child;
  assert.equal(await session.shutdownWorker(), true);
  assert.equal(session.child, null);
});

test('creates a confirmed review timeline from matched beats and reports unmatched beats as omitted', () => {
  const plan = { decisions: [{ beat_id: 'a' }, { beat_id: 'b' }], unmatched_beats: ['c', 'd'] };
  assert.deepEqual(prepareReviewTimeline(plan, true), { decisions: plan.decisions, omitted: 2 });
  assert.throws(() => prepareReviewTimeline(plan, false), /conferma/i);
  assert.throws(() => prepareReviewTimeline({ decisions: [], unmatched_beats: ['c'] }, true), /nessuna battuta abbinata/i);
});
