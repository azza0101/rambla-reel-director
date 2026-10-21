const test=require('node:test');const assert=require('node:assert/strict');
const {snapshot}=require('./source_adapter');
function mock({left=0,right=0,extra=false,marks={video:{},audio:{}},clipStart=108000}={}){
 const media={GetClipProperty:async key=>key==='File Path'?'C:/video/original.mov':''};
 const clip={GetStart:async()=>clipStart,GetEnd:async()=>clipStart+900,GetLeftOffset:async()=>left,GetRightOffset:async()=>right,GetMediaPoolItem:async()=>media};
 const timeline={GetMarkInOut:async()=>marks,GetStartFrame:async()=>108000,GetSetting:async()=>30,GetUniqueId:async()=>'timeline-1',GetName:async()=>'Full source',GetTrackCount:async()=>1,GetItemListInTrack:async()=>extra?[clip,clip]:[clip]};
 const project={GetName:async()=>'TEST',GetCurrentTimeline:async()=>timeline};
 return {GetProjectManager:async()=>({GetCurrentProject:async()=>project})};
}
test('full source snapshot is serializable and read-only',async()=>{
 assert.deepEqual(await snapshot(mock()),{path:'C:/video/original.mov',project_name:'TEST',timeline_id:'timeline-1',timeline_name:'Full source'});
});
test('trimmed source refuses instead of processing the whole wrong video',async()=>{
 await assert.rejects(snapshot(mock({left:30})),/integrale/);
 await assert.rejects(snapshot(mock({right:50})),/integrale/);
});
test('multiple clips require a future multitrack adapter',async()=>{
 await assert.rejects(snapshot(mock({extra:true})),/sola clip/);
});

test('IN OUT are relative timeline marks and OUT is inclusive',async()=>{
 const context=await snapshot(mock({marks:{video:{in:120,out:299},audio:{in:120,out:299}}}));
 assert.deepEqual(context.source_range,{in_frame:120,out_frame:300,fps:'30'});
});
test('range maps a delayed full clip back to source frames',async()=>{
 const context=await snapshot(mock({clipStart:108060,marks:{video:{in:120,out:299}}}));
 assert.deepEqual(context.source_range,{in_frame:60,out_frame:240,fps:'30'});
});
test('different audio video marks are refused',async()=>{
 await assert.rejects(snapshot(mock({marks:{video:{in:0,out:100},audio:{in:1,out:100}}})),/diversi/);
});
