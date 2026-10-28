const test=require('node:test'),assert=require('node:assert/strict');
test('catalogued silent scenes remain in automatic scope with fully catalogued speech',()=>{
 const {automaticScope}=require('../../runtime/premontato/automatic_editing');const scenes=[{scene_id:'s1',heading:'Uno',beats:[]},{scene_id:'s2',heading:'Due',beats:[]}];
 const result=automaticScope(scenes,{},[{media_id:'spoken',scene:{scene_id:'s1'}},{media_id:'silent',scene:{scene_id:'s2'},coverage_eligible:true,role:'visual_coverage'}],['spoken']);assert.deepEqual(result.scene.source_scene_ids,['s1','s2']);
});
