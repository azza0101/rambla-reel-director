const test=require('node:test'),assert=require('node:assert/strict');
const {annotateSceneEdits}=require('../../plugin/session');
test('scene debug derives script ordinal from canonical beat IDs without altering the edit plan',()=>{
 const analysis={script:{scenes:[{scene_id:'s1',heading:'CASA',beats:[{beat_id:'a'}]},{scene_id:'s2',heading:'STRADA',beats:[{beat_id:'b'}]}]}};
 const edits=[{beat_id:'a',decision_id:'moment-1',reaction_before:{media_id:'r'},action_after:[{beat_id:'a',media_id:'m'}]},{beat_id:'b',decision_id:'moment-2'}],before=JSON.stringify(edits);
 const out=annotateSceneEdits(analysis,edits);assert.deepEqual(out.map(x=>x.scene_debug),[{id:'s1',number:1,heading:'CASA'},{id:'s2',number:2,heading:'STRADA'}]);assert.equal(JSON.stringify(edits),before);assert.equal(out[0].reaction_before.scene_debug.id,'s1');assert.equal(out[0].action_after[0].scene_debug.id,'s1');
});
test('scene debug refuses untraceable beats rather than inventing scene boundaries',()=>{assert.throws(()=>annotateSceneEdits({script:{scenes:[{scene_id:'s',beats:[{beat_id:'a'}]}]}},[{beat_id:'unknown'}]),/scena/i);});

test('title generation accounts for standalone reactions/actions but does not lengthen speech for overlays',async()=>{
 const {Session}=require('../../plugin/session');const s=new Session('unused','unused');s.state.analysis={script:{scenes:[{scene_id:'s',heading:'CASA',beats:[{beat_id:'a'}]}]}};
 const decisions=[{beat_id:'a',start_frame:0,end_frame:100,reaction_before:{start_frame:200,end_frame:240},reaction_overlay:{start_frame:300,end_frame:340},action_after:[{beat_id:'a',start_frame:400,end_frame:450}]}];
 let calls=0;s.request=async(action,payload)=>{calls++;assert.equal(action,'render_scene_debug_titles');assert.deepEqual(payload.scenes,[{number:1,frames:190}]);return {assets:{1:'C:/scene.mov'}};};
 const prepared=await s.prepareTimelineDebug(decisions,true,{fps:25,width:1920,height:1080});assert.equal(prepared.sceneDebug.gap_frames,50);assert.equal(prepared.decisions[0].scene_debug.number,1);assert.equal(calls,1);
 const plain=await s.prepareTimelineDebug(decisions,false,{fps:25});assert.equal(plain.decisions,decisions);assert.equal(plain.sceneDebug.enabled,false);assert.equal(calls,1);
});

test('debug preference is retained as a project draft and rejects non-boolean values',()=>{const {Session}=require('../../plugin/session'),s=new Session('unused','unused');s.setDraft({sceneDebug:false});assert.equal(s.getReviewState().uiDraft.sceneDebug,false);assert.throws(()=>s.setDraft({sceneDebug:'yes'}),/debug scene/i);assert.equal(s.getReviewState().uiDraft.sceneDebug,false);});
