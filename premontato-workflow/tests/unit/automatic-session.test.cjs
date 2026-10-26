const test=require('node:test'),assert=require('node:assert/strict');
const {Session}=require('../../plugin/session');
test('default analysis verifies speaker but defers stills and identity clustering',async()=>{
 const s=new Session('unused','unused');s.state.script={path:'script.pdf',text:'copione'};s.state.media=[{media_id:'m',path:'rush.mp4',duration_frames:100}];s.state.transcripts=[{...s.state.media[0],name:'clip',fps:25,segments:[{start_frame:0,end_frame:20,text:'prima battuta intera'}]}];const calls=[];const scene={heading:'SCENA 01',beats:[{beat_id:'b',kind:'dialogue',text:'prima battuta intera'}]};
 s.request=async(action,payload)=>{calls.push({action,payload});if(action==='parse_script')return {scenes:[scene]};if(action==='select_scene')return {scene};if(action==='analyze_shots')return {segments:[]};if(action==='propose_take_segments')return [{take_id:'t',media_id:'m',start_frame:0,end_frame:100,take_index:1,boundary_source:'whole_clip'}];if(action==='analyze_audio')return {status:'ok',silences:[]};if(action==='build_plan')return {decisions:[],warnings:[],unmatched_beats:[]};if(action==='pace_plan')return payload.plan;throw Error('Unexpected '+action);};
 await s.analyze();assert.equal(calls.some(c=>c.action==='visual_review'),false);assert.equal(calls.find(c=>c.action==='build_plan').payload.active_speaker,true);assert.equal(s.state.analysis.plan.visual_review_required,false);
});
test('loading visual debug is explicit and does not invalidate an automatic plan',async()=>{
 const s=new Session('unused','unused');s.state.transcripts=[{media_id:'m',path:'clip.mp4'}];s.state.analysis={shots:[],plan:{decisions:[],visual_review_required:false}};let count=0;
 s.request=async action=>{assert.equal(action,'visual_review');count++;return {intervals:[],faces:[],confirmed:false};};
 await s.loadVisualReview();await s.loadVisualReview();assert.equal(count,1);assert.equal(s.state.analysis.plan.visual_review_required,false);
});

test('manual movement outside checked speech clears stale active-speaker evidence',()=>{
 const s=new Session('unused','unused');s.state.media=[{media_id:'m',duration_frames:500}];s.state.analysis={plan:{decisions:[{beat_id:'b',media_id:'m',take_id:'t',start_frame:20,end_frame:90,matched_start_frame:23,matched_end_frame:86,speaker_coverage:'visible',speaker_coverage_source:'audio_visual',active_speaker:{status:'visible',sample_start_frame:25,sample_end_frame:75},alternatives:[]}]}};
 s.updateDecision({beat_id:'b',start_frame:200,end_frame:250});const d=s.state.analysis.plan.decisions[0];assert.equal(d.speaker_coverage,'unknown');assert.equal(d.active_speaker,undefined);assert.equal(d.speaker_coverage_source,'unverified');
});

test('configured Groq uses grounded preparation and local staged build, never legacy plan selection',async()=>{
 const s=new Session('unused','unused');const calls=[];
 s.groq={status:()=>({enabled:true,configured:true}),classify:async()=>({labels:{t:{S0:'1/P1'}},summary:{calls:1}})};
 s.request=async(action,payload)=>{calls.push(action);if(action==='prepare_dialogue')return {clips:[]};if(action==='build_staged')return {engine:'groq_staged_v1',decisions:[],warnings:[]};throw Error('Unexpected '+action);};
 const p=await s.buildPlan({beats:[],sources:[],shots:[],fps:25});assert.equal(p.engine,'groq_staged_v1');assert.deepEqual(calls,['prepare_dialogue','build_staged']);
});
test('moment edit updates only the requested decision within a shared screenplay beat',()=>{
 const s=new Session('unused','unused');s.state.media=[{media_id:'m',duration_frames:500}];s.state.analysis={plan:{decisions:[{decision_id:'one',beat_id:'b',media_id:'m',take_id:'t',start_frame:10,end_frame:30,alternatives:[]},{decision_id:'two',beat_id:'b',media_id:'m',take_id:'t',start_frame:40,end_frame:60,alternatives:[]}]}};
 s.updateDecision({beat_id:'b',decision_id:'two',start_frame:45});assert.equal(s.state.analysis.plan.decisions[0].start_frame,10);assert.equal(s.state.analysis.plan.decisions[1].start_frame,45);
});

test("analysis rejects missing transcripts before claiming completion",async()=>{const s=new Session("unused","unused");s.state.script={text:"copione"};s.state.media=[{media_id:"m",name:"clip"}];let called=false;s.request=async()=>{called=true;return {};};await assert.rejects(s.analyze(),/trascrizion/i);assert.equal(called,false);});
