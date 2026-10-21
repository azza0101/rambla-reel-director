const test=require('node:test');const assert=require('node:assert/strict');
const {snapshot}=require('./source_adapter');
function mock({left=0,right=0,extra=false}={}){
 const media={GetClipProperty:async key=>key==='File Path'?'C:/video/original.mov':''};
 const clip={GetLeftOffset:async()=>left,GetRightOffset:async()=>right,GetMediaPoolItem:async()=>media};
 const timeline={GetUniqueId:async()=>'timeline-1',GetName:async()=>'Full source',GetTrackCount:async()=>1,GetItemListInTrack:async()=>extra?[clip,clip]:[clip]};
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
