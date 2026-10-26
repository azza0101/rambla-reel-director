'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {Session}=require('../../plugin/session');

function fixture({configured=true,enabled=true,pacing=true}={}) {
  const session=new Session('unused','unused'),calls=[],events=[];
  const scene={heading:'SCENA 01',beats:[{beat_id:'b',kind:'dialogue',character:'ALICE',text:'Aspettami qui.'}]};
  const source={media_id:'m',name:'clip',path:'rush.mp4',duration_frames:100,fps:25,
    segments:[{text:'Aspettami qui.',start_frame:10,end_frame:60,words:[
      {text:'Aspettami',start_frame:10,end_frame:35},{text:'qui.',start_frame:40,end_frame:60}]}]};
  const decision={beat_id:'b',media_id:'m',take_id:'m:take:1',start_frame:8,end_frame:63,
    matched_start_frame:10,matched_end_frame:60,alternatives:[]};
  session.state.script={path:'script.pdf',text:'copione'};
  session.state.media=[source];session.state.transcripts=[source];session.state.pacingSettings.enabled=pacing;
  session.onProgress=event=>events.push(event);
  session.groq={status:()=>({configured,enabled}),classify:async prepared=>{
    calls.push({action:'classify',payload:prepared});return {labels:{'m:take:1':{S0:'1/P1'}},summary:{calls:0}};
  }};
  session.request=async(action,payload)=>{
    calls.push({action,payload});
    switch(action){
      case 'parse_script':return {scenes:[scene]};
      case 'select_scene':return {scene};
      case 'analyze_shots':return {segments:[]};
      case 'propose_take_segments':return [{take_id:'m:take:1',media_id:'m',start_frame:0,end_frame:100,take_index:1,boundary_source:'whole_clip'}];
      case 'analyze_audio':return {status:'ok',silences:[{start_frame:60,end_frame:75}]};
      case 'prepare_dialogue':return {clips:[{key:'m:take:1',units:[]}],cast:{P1:'ALICE'},beats:scene.beats};
      case 'build_staged':return {engine:'groq_staged_v1',decisions:[structuredClone(decision)],warnings:[],unmatched_beats:[]};
      case 'build_plan':return {decisions:[structuredClone(decision)],warnings:[],unmatched_beats:[]};
      case 'pace_plan':return {...payload.plan,pacing_settings:payload.settings};
      default:throw Error('Unexpected '+action);
    }
  };
  return {session,calls,events,source,decision};
}

test('Groq analysis skips unused RMS work and keeps source words and chosen intervals',async()=>{
  const {session,calls,events,source,decision}=fixture(),original=structuredClone(source);
  await session.analyze();
  assert.equal(calls.some(c=>c.action==='analyze_audio'),false);
  assert.equal(calls.some(c=>c.action==='build_staged'),true);
  assert.equal(calls.some(c=>c.action==='build_plan'),false);
  assert.deepEqual(calls.find(c=>c.action==='pace_plan').payload.audio,{});
  assert.deepEqual(session.state.analysis.plan.decisions,[decision]);
  assert.deepEqual(calls.find(c=>c.action==='prepare_dialogue').payload.sources[0].segments,original.segments);
  assert.deepEqual(source,original);
  const audio=events.filter(e=>e.phase==='audio');
  assert.equal(audio.length,1);assert.equal(audio[0].skipped,true);assert.doesNotMatch(audio[0].label,/misuro|misurato/i);
});

for(const [name,options] of [['disabled',{enabled:false}],['unconfigured',{configured:false}]]) {
  test(`local planner still receives measured pauses when Groq is ${name}`,async()=>{
    const {session,calls,events}=fixture(options);
    await session.analyze();
    assert.equal(calls.filter(c=>c.action==='analyze_audio').length,1);
    assert.equal(calls.find(c=>c.action==='build_plan').payload.active_speaker,true);
    assert.equal(calls.some(c=>c.action==='classify'),false);
    assert.deepEqual(calls.find(c=>c.action==='pace_plan').payload.audio.m.silences,[{start_frame:60,end_frame:75}]);
    assert.equal(events.find(e=>e.phase==='audio').skipped,false);
  });
}

test('disabled pacing skips RMS work and reports the audio phase as skipped',async()=>{
  const {session,calls,events}=fixture({enabled:false,pacing:false});
  await session.analyze();
  assert.equal(calls.some(c=>c.action==='analyze_audio'),false);
  assert.equal(calls.some(c=>c.action==='build_plan'),true);
  assert.deepEqual(session.state.analysis.audio,{});
  const audio=events.filter(e=>e.phase==='audio');
  assert.equal(audio.length,1);assert.equal(audio[0].skipped,true);assert.doesNotMatch(audio[0].label,/misuro|misurato/i);
});

test('saved Groq project lazily measures pauses once when reopened with the local planner',async t=>{
  const fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path');
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'premontato-audio-reuse-'));
  t.after(()=>fs.rm(root,{recursive:true,force:true}));
  const initial=fixture();initial.session.root=path.join(root,'initial');initial.source.path=path.join(root,'rush.mp4');
  await fs.writeFile(initial.source.path,'fixture');
  await initial.session.analyze();
  assert.deepEqual(initial.session.state.analysis.audio,{});
  const document=path.join(root,'project.premontato');
  await initial.session.saveProject(document);
  const reopened=fixture({enabled:false});
  await reopened.session.loadProject(document);
  await reopened.session.setDirections({profile:'none',notes:'',markers:{}});
  const measured=reopened.calls.filter(c=>c.action==='analyze_audio');
  assert.equal(measured.length,1);assert.equal(measured[0].payload.media.path,initial.source.path);
  assert.deepEqual(reopened.calls.find(c=>c.action==='pace_plan').payload.audio.m.silences,[{start_frame:60,end_frame:75}]);
  await reopened.session.applyPacing();
  assert.equal(reopened.calls.filter(c=>c.action==='analyze_audio').length,1);
  assert.equal(reopened.session.state.analysis.audio.m.status,'ok');
});

test('enabling local pacing measures each missing full source including alternative cameras once',async()=>{
  const {session,calls,events,source}=fixture({enabled:false,pacing:false});
  await session.analyze();
  const other={...structuredClone(source),media_id:'other',path:'alternative.mp4'};
  session.state.transcripts.push(other);session.state.media.push(other);
  // Multiple takes share a media source; analysis must keep its original duration.
  session.state.analysis.planningSources=[
    {...source,start_frame:0,end_frame:50,duration_frames:50},
    {...source,take_id:'m:take:2',start_frame:50,end_frame:100,duration_frames:50},
    {...other,start_frame:0,end_frame:50,duration_frames:50},
  ];
  await session.setPacing({enabled:true});
  const measured=calls.filter(c=>c.action==='analyze_audio');
  assert.deepEqual(measured.map(c=>c.payload.media.media_id),['m','other']);
  assert.equal(measured.every(c=>c.payload.media.duration_frames===100),true);
  assert.deepEqual(Object.keys(session.state.analysis.audio).sort(),['m','other']);
  assert.equal(events.at(-1).phase,'complete');assert.equal(events.at(-1).percent,100);
  await session.applyPacing();
  assert.equal(calls.filter(c=>c.action==='analyze_audio').length,2);
});

test('failed lazy audio is retained as unavailable without repeated extraction attempts',async()=>{
  const {session,calls}=fixture({enabled:false,pacing:false});
  await session.analyze();
  const request=session.request;
  session.request=async(action,payload)=>{
    if(action==='analyze_audio'){calls.push({action,payload});throw Error('audio unavailable');}
    return request(action,payload);
  };
  await session.setPacing({enabled:true});
  await session.applyPacing();
  assert.equal(calls.filter(c=>c.action==='analyze_audio').length,1);
  assert.deepEqual(session.state.analysis.audio.m,{status:'unavailable',reason:'audio unavailable'});
});

test('pacing without a plan does not start audio extraction',async()=>{
  const {session,calls}=fixture({enabled:false});
  await session.setPacing({enabled:true});
  assert.equal(calls.some(c=>c.action==='analyze_audio'),false);
});

test('failed pacing closes the progress started by lazy audio measurement',async()=>{
  const {session,events}=fixture({enabled:false,pacing:false});
  await session.analyze();
  const request=session.request;
  session.request=async(action,payload)=>{
    if(action==='pace_plan')throw Error('pacing failed');
    return request(action,payload);
  };
  await assert.rejects(session.setPacing({enabled:true}),/pacing failed/);
  assert.equal(events.at(-1).phase,'error');
});
