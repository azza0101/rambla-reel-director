const test=require('node:test'),assert=require('node:assert/strict');
const {Session}=require('../../plugin/session');
test('manual scene scope rebuilds a sequence using existing transcripts shots and take boundaries',async()=>{
 const s=new Session('unused','unused');const scenes=[{scene_id:'one',heading:'INT. CASA A',beats:[{beat_id:'b1',kind:'dialogue',text:'prima',character:'A'}]},{scene_id:'two',heading:'INT. CASA B',beats:[{beat_id:'b2',kind:'dialogue',text:'seconda',character:'B'}]}];
 const sources=[{media_id:'m',segments:[]}],shots=[{segment_id:'shot'}];s.state.analysis={script:{scenes},planningSources:sources,shots,takes:[{confirmed:true}],audio:{},plan:null};s.state.transcripts=sources;s.state.script={path:'script.pdf',text:'copione'};s.state.media=[];
 s.buildPlan=async payload=>{assert.equal(payload.sources,sources);assert.equal(payload.shots,shots);assert.deepEqual(payload.beats.map(b=>b.beat_id),['b1','b2']);return {decisions:[{beat_id:'b1'}],warnings:[]};};
 s.request=async(action,payload)=>{assert.equal(action,'pace_plan');return payload.plan;};
 await s.selectScenes({scene_ids:['two','one']});assert.equal(s.state.analysis.selectedScene.beats.length,2);assert.equal(s.state.analysis.sceneSelection.manual,true);assert.equal(s.state.analysis.plan.decisions.length,1);
});
test('unknown or repeated scene ids fail before replacing the existing analysis',async()=>{
 const s=new Session('unused','unused');const analysis={script:{scenes:[{scene_id:'one',heading:'INT A',beats:[]}]},plan:{decisions:[{}]}};s.state.analysis=analysis;
 await assert.rejects(s.selectScenes({scene_ids:['missing']}),/scen/i);await assert.rejects(s.selectScenes({scene_ids:['one','one']}),/scen/i);assert.equal(s.state.analysis,analysis);
});

test('PDF page range is optional, validated, and preserves loaded transcripts',async()=>{
 const s=new Session('unused','unused');s.state.script={path:'script.pdf',text:'full'};const sources=[{media_id:'m'}];s.state.transcripts=sources;s.request=async(action,payload)=>{assert.equal(action,'extract_pdf_script');assert.equal(payload.page_start,3);assert.equal(payload.page_end,5);return {text:'selected'};};
 await s.setScriptPages({start:3,end:5});assert.equal(s.state.transcripts,sources);assert.deepEqual(s.state.script.pages,{start:3,end:5});assert.equal(s.state.script.text,'selected');await assert.rejects(s.setScriptPages({start:5,end:3}),/pagine/);assert.equal(s.state.script.text,'selected');
});
