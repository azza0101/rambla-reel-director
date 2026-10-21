const test=require('node:test'),assert=require('node:assert/strict');let api;try{api=require('../plugin/resolve_adapter')}catch{}
function host(){let id='one';const clip={GetStart:()=>108010,GetEnd:()=>108020,GetName:()=>'<hello> 日本'};
 const tl={GetUniqueId:()=>id,GetName:()=> 'Timeline',GetSetting:()=> '30',GetStartFrame:()=>108000,GetEndFrame:()=>110000,GetStartTimecode:()=> '01:00:00:00',GetMarkInOut:()=>({video:{in:10,out:60},audio:{}}),GetTrackCount:()=>1,GetItemListInTrack:()=>({1:clip,__flags:99})};
 const project={GetUniqueId:()=> 'project',GetName:()=> 'Project',GetCurrentTimeline:()=>tl};
 return {resolve:{GetProjectManager:()=>({GetCurrentProject:()=>project})},tl,clip,switch:()=>{id='two'}};
}
test('subtitle API ignores metadata, preserves V3.1 mark bounds, never reads video',async()=>{assert.ok(api);const h=host();const s=await api.snapshot(h.resolve);assert.deepEqual(s.range,{a:108010,b:108060});assert.equal(s.captions[0].content,'<hello> 日本');assert.equal(s.captions.length,1);assert.equal(s.projectId,'project')});
test('reject unreadable numeric item instead of silently losing a caption',async()=>{assert.ok(api);const h=host();h.tl.GetItemListInTrack=()=>({1:12,__flags:99});await assert.rejects(api.snapshot(h.resolve),/leggibil/)});
test('detect timeline switch during caption enumeration',async()=>{assert.ok(api);const h=host();h.clip.GetName=()=>{h.switch();return 'text'};await assert.rejects(api.snapshot(h.resolve),/cambiat/)});
test('caption edits invalidate fingerprint; unchanged reload stays stable',async()=>{assert.ok(api);const h=host();const a=await api.snapshot(h.resolve),b=await api.snapshot(h.resolve);assert.equal(a.fingerprint,b.fingerprint);h.clip.GetName=()=> 'changed';assert.notEqual(a.fingerprint,(await api.snapshot(h.resolve)).fingerprint)});
test('missing marks retain timeline data but no range',async()=>{assert.ok(api);const h=host();h.tl.GetMarkInOut=()=>({video:{},audio:{}});assert.equal((await api.snapshot(h.resolve)).range,null)});
