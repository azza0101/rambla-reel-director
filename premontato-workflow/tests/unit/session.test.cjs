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
    if (action === 'pace_plan') return {...payload.plan, pacing_settings:payload.settings};
    if (action === 'build_plan') return { decisions: [], unmatched_beats: [], warnings: [] };
    throw new Error(`unexpected action ${action}`);
  };
  await session.analyze();
  const planCall = calls.find(call => call.action === 'build_plan');
  assert.deepEqual(planCall.payload.beats.map(beat => beat.beat_id), ['a1']);
  assert.equal(session.state.analysis.selectedScene.heading, 'SCENA 01');
  assert.deepEqual([...new Set(progress.map(event => event.phase))], ['script', 'scene', 'shots', 'takes', 'audio', 'plan', 'pacing', 'complete']);
  assert.equal(progress.at(-1).percent, 100);
  assert.equal(progress.every((event,index)=>!index || event.phaseIndex>=progress[index-1].phaseIndex),true);
});

test('accepts transcription results after changing timeline in the same project', () => {
  const session = new Session('unused', 'unused');
  session.setMedia([{ media_id: 'm', name: 'clip', duration_frames: 100 }], { projectId: 'p', timelineId: 't1' });
  assert.doesNotThrow(() => session.setTranscripts([], 25, { projectId: 'p', timelineId: 't2', selected:[{media_id:'m'}] }));
});

test('rejects a changed Media Pool selection even inside the same project', () => {
  const session = new Session('unused', 'unused');
  session.setMedia([{ media_id: 'm1', name: 'one', duration_frames: 100 }], { projectId: 'p', timelineId: 't' });
  assert.throws(() => session.assertContext({ projectId: 'p', timelineId: 't', selected: [{ media_id: 'm2' }] }), /selezione media è cambiata/);
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

test('manual review validates source bounds and recalculates timeline positions', async () => {
 const session=new Session('unused','unused');
 session.state.media=[{media_id:'m',duration_frames:500}];
 session.state.analysis={plan:{decisions:[{beat_id:'a',media_id:'m',start_frame:10,end_frame:50,alternatives:[]},{beat_id:'b',media_id:'m',start_frame:100,end_frame:150,alternatives:[]}]}};
 assert.throws(()=>session.updateDecision({beat_id:'a',start_frame:-1,end_frame:600}),/Intervallo/);
 session.updateDecision({beat_id:'a',start_frame:5,end_frame:80,shot_size:'close'});
 assert.equal(session.state.analysis.plan.decisions[1].timeline_start_frame,75);
 assert.equal(session.state.analysis.plan.decisions[0].shot_size,'close');
});

test('editing a paced interval invalidates its old ranges and updates the unpaced base',()=>{
 const session=new Session('unused','unused');session.state.media=[{media_id:'m',duration_frames:500}];
 session.state.analysis={plan:{base_decisions:[{beat_id:'a',media_id:'m',start_frame:10,end_frame:300}],decisions:[{beat_id:'a',media_id:'m',start_frame:20,end_frame:280,source_ranges:[{start_frame:20,end_frame:100},{start_frame:200,end_frame:280}],alternatives:[]}]}};
 session.updateDecision({beat_id:'a',start_frame:50,end_frame:120});
 assert.equal(session.state.analysis.plan.decisions[0].source_ranges,undefined);
 assert.equal(session.state.analysis.plan.base_decisions[0].end_frame,120);
});
test('a pause-only edit restores the untrimmed source interval before reapplying pacing',()=>{
 const session=new Session('unused','unused');session.state.media=[{media_id:'m',duration_frames:500}];
 session.state.analysis={plan:{base_decisions:[{beat_id:'a',media_id:'m',start_frame:10,end_frame:300}],decisions:[{beat_id:'a',media_id:'m',start_frame:20,end_frame:280,alternatives:[]}]}};
 session.updateDecision({beat_id:'a',preserve_pause:true});
 assert.equal(session.state.analysis.plan.decisions[0].start_frame,10);
 assert.equal(Boolean(session.state.analysis.plan.decisions[0].manual),false);
});

test('the real worker parses Italian text as Unicode internally rather than locale bytes',async()=>{
 const path=require('node:path'),crypto=require('node:crypto');
 const python=process.env.PREMONTATO_TEST_PYTHON || 'python';
 const session=new Session('unused',path.resolve(__dirname,'../../worker/protocol.py'),python);
 const heading='SCENA 01 INT. CITTÀ - SERA';
 const expected='scene_'+crypto.createHash('sha1').update(heading.toLowerCase()+'|0','utf8').digest('hex').slice(0,12);
 try{const result=await session.request('parse_script',{text:heading+'\n\nLUCA\nPerché è già così?'});assert.equal(result.scenes[0].scene_id,expected);assert.equal(result.scenes[0].beats[0].text,'Perché è già così?');}finally{await session.shutdownWorker();}
});

test('saving notes alone preserves manual edits without rebuilding the plan',async()=>{
 const session=new Session('unused','unused');session.state.directions={profile:'VIDEO COLICHE',notes:'old',markers:{a:'tension'}};
 const plan={decisions:[{beat_id:'a',manual:true,start_frame:7,end_frame:90,preserve_pause:true}],base_decisions:[]};
 session.state.analysis={parsedBeats:[{beat_id:'a',kind:'dialogue'}],planningSources:[{}],takes:[{confirmed:true}],plan};
 session.request=async()=>{throw Error('Must not rebuild notes-only changes');};
 await session.setDirections({...session.state.directions,notes:'new'});assert.equal(session.state.analysis.plan,plan);assert.equal(plan.decisions[0].start_frame,7);
});

test('local analysis validates project without depending on current timeline or selection',()=>{
 const session=new Session('unused','unused');session.setMedia([{media_id:'m'}],{projectId:'p',timelineId:'old'});
 assert.doesNotThrow(()=>session.assertProject({projectId:'p',timelineId:'new',selected:[]}));
 assert.throws(()=>session.assertProject({projectId:'other'}),/progetto/i);
});
test('selection identity is independent of Media Pool ordering',()=>{
 const session=new Session('unused','unused');session.setMedia([{media_id:'a'},{media_id:'b'}],{projectId:'p',timelineId:'old'});
 assert.doesNotThrow(()=>session.assertContext({projectId:'p',timelineId:'new',selected:[{media_id:'b'},{media_id:'a'}]}));
});

test('reaction toggle preserves staged base ranges and restores its verified internal overlay',()=>{const s=new Session('unused','unused');const overlay={offset_frames:35,start_frame:10,end_frame:50,media_id:'other',return_to_speaker:true};const base={beat_id:'b',decision_id:'m',media_id:'clip',start_frame:0,end_frame:120,source_ranges:[{start_frame:0,end_frame:120}],reaction_overlay:overlay,action_after:[{start_frame:200,end_frame:225}]};s.state.media=[{media_id:'clip',duration_frames:500}];s.state.analysis={plan:{engine:'groq_staged_v1',decisions:[structuredClone(base)],base_decisions:[structuredClone(base)]}};s.updateDecision({beat_id:'b',decision_id:'m',reaction_enabled:false});assert.equal(s.state.analysis.plan.decisions[0].reaction_overlay,undefined);s.updateDecision({beat_id:'b',decision_id:'m',reaction_enabled:true});assert.deepEqual(s.state.analysis.plan.decisions[0].reaction_overlay,overlay);assert.deepEqual(s.state.analysis.plan.decisions[0].source_ranges,base.source_ranges);assert.deepEqual(s.state.analysis.plan.decisions[0].action_after,base.action_after);});

test('changing editorial notes in the staged engine recalculates intentions instead of treating notes as a memo',async()=>{const s=new Session('unused','unused');s.state.directions={profile:'VIDEO COLICHE',notes:'before',markers:{}};s.state.analysis={parsedBeats:[],planningSources:[{}],shots:[],takes:[{confirmed:true}],plan:{engine:'groq_staged_v1',decisions:[]}};let built=0;s.buildPlan=async p=>{built++;assert.equal(p.directions.notes,'after');return {engine:'groq_staged_v1',decisions:[]};};s.request=async(action,p)=>p.plan;await s.setDirections({profile:'VIDEO COLICHE',notes:'after',markers:{}});assert.equal(built,1);});

test('staged planning retains separate Groq timings and reports reaction candidate progress',async()=>{const s=new Session('unused','unused');s.groq={status:()=>({configured:true,enabled:true}),classify:async()=>({labels:{},summary:{calls:0,cache_hits:1,clips:1}}),planEditorial:async()=>({events:[],summary:{status:'ready',calls:0,cache_hit:true}})};const progress=[];s.onProgress=e=>progress.push(e);s.request=async(action,p,timeout,report)=>{if(action==='prepare_dialogue')return {};report?.({phase:'listening',step:'candidate',current:1,total:3,candidates_checked:2});return {decisions:[],performance:{wall_seconds:.1}};};const result=await s.buildPlan({});assert.equal(result.performance.wall_seconds,.1);assert.equal(typeof result.performance.groq.classification_seconds,'number');assert.equal(typeof result.performance.groq.editorial_seconds,'number');assert(progress.some(e=>e.label.includes('2 candidati verificati')));});
