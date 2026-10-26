const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path');
const {Session}=require('../../plugin/session');
test('reaction exclusion is persisted without making the dialogue a manual cut',()=>{
 const s=new Session('unused','unused');s.state.media=[{media_id:'m',duration_frames:500}];const decision={beat_id:'b',media_id:'m',take_id:'t',start_frame:200,end_frame:240,alternatives:[]};s.state.analysis={plan:{decisions:[{...decision}],base_decisions:[{...decision}]}};
 s.updateDecision({beat_id:'b',reaction_enabled:false});assert.equal(s.state.analysis.plan.decisions[0].reaction_enabled,false);assert.equal(Boolean(s.state.analysis.plan.decisions[0].manual),false);assert.equal(s.state.analysis.plan.base_decisions[0].reaction_enabled,false);
 assert.throws(()=>s.updateDecision({beat_id:'b',reaction_enabled:'false'}),/reazione/i);
});
test('projects roundtrip reaction metadata and reject unsafe nested source ranges',async()=>{
 const dir=await fs.mkdtemp(path.join(os.tmpdir(),'premontato-reaction-'));try{
 const mediaFile=path.join(dir,'footage.mp4');await fs.writeFile(mediaFile,'fixture');const file=path.join(dir,'scene.json');const s=new Session(dir,'unused');s.state.media=[{media_id:'m',name:'clip',path:mediaFile,duration_frames:500,fps:25}];
 const reaction={kind:'reaction',media_id:'m',take_id:'t',start_frame:160,end_frame:190,shot_size:'close',character:'LUCA',enabled:true,basis:'verified_silent_preroll',speaker_coverage:'visible'};
 s.state.analysis={plan:{decisions:[{beat_id:'b',media_id:'m',take_id:'t',start_frame:200,end_frame:240,reaction_before:reaction}]}};
 await s.saveProject(file);const restored=new Session(dir,'unused');await restored.loadProject(file);assert.deepEqual(restored.state.analysis.plan.decisions[0].reaction_before,reaction);
 const original=await fs.readFile(file,'utf8');for(const bad of [{end_frame:900},{start_frame:-2},{shot_size:'unknown'},{still:{frame:180,image:'https://example.com/tracking.jpg'}},{source_ranges:[{start_frame:0,end_frame:5}]}]){const doc=JSON.parse(original);Object.assign(doc.state.analysis.plan.decisions[0].reaction_before,bad);await fs.writeFile(file,JSON.stringify(doc));await assert.rejects(restored.loadProject(file),/non validi/);}
 }finally{await fs.rm(dir,{recursive:true,force:true});}
});

test('reaction exclusion survives a full narrative replan',async()=>{
 const s=new Session('unused','unused');s.state.directions={profile:'none',notes:'',markers:{}};s.state.analysis={parsedBeats:[{beat_id:'b',kind:'dialogue',text:'risposta',character:'LUI'}],planningSources:[{}],takes:[{confirmed:true}],plan:{decisions:[{beat_id:'b',reaction_enabled:false}]}};
 s.request=async(action,payload)=>action==='build_plan'?{decisions:[{beat_id:'b'}]}:payload.plan;
 const result=await s.setDirections({profile:'VIDEO COLICHE',notes:'',markers:{b:'resolution'}});assert.equal(result.analysis.plan.decisions[0].reaction_enabled,false);
});
