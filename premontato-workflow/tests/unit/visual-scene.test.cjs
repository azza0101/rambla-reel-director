const test=require('node:test'),assert=require('node:assert/strict');
test('catalogued silent action is planned even with a missing dialogue line',()=>{
 const {planVisualScene}=require('../../plugin/session');
 const scene={scene_id:'s',heading:'Esterno',beats:[{beat_id:'a',kind:'action',text:'Una persona bussa alla porta.'},{beat_id:'b',kind:'dialogue',text:'Entra.'}]};
 const source={media_id:'m',take_id:'t',duration_frames:250,fps:25,catalog_context:{media_id:'m',coverage_eligible:true,role:'visual_coverage',scene:{scene_id:'s'}}};
 const p=planVisualScene(scene,[source],25);assert.equal(p.decisions.length,1);assert.equal(p.decisions[0].kind,'action');assert.equal(p.decisions[0].media_id,'m');assert.deepEqual(p.unmatched_beats,['b']);assert.equal(p.decisions[0].end_frame,250);
 assert.equal(planVisualScene({...scene,scene_id:'other'},[source],25),null);
 assert.equal(planVisualScene(scene,[{...source,catalog_context:{...source.catalog_context,coverage_eligible:false}}],25),null);
});
