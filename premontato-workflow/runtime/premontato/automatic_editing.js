'use strict';
const crypto=require('node:crypto');
function combineScenes(scenes){
 if(!scenes.length)return null;
 if(scenes.length===1)return scenes[0];
 const ids=scenes.map(s=>s.scene_id);
 return {scene_id:'automatic_'+crypto.createHash('sha1').update(ids.join('|')).digest('hex').slice(0,12),heading:'SEQUENZA AUTOMATICA · '+scenes.length+' scene',source_scene_ids:ids,beats:scenes.flatMap(s=>s.beats||[]).map((beat,order)=>({...beat,order}))};
}
function automaticScope(scenes,selection={},entries=[],spokenIds=[]){
 const validIds=new Set(scenes.map(s=>s.scene_id)),byMedia=new Map(entries.filter(e=>validIds.has(e.scene?.scene_id)).map(e=>[e.media_id,e.scene.scene_id]));
 if(spokenIds.length&&spokenIds.every(id=>byMedia.has(id))){const ids=new Set(spokenIds.map(id=>byMedia.get(id)));return {...selection,scene:combineScenes(scenes.filter(s=>ids.has(s.scene_id))),automatic:true,scope_basis:'catalog'};}
 if(selection.scene)return {...selection,automatic:true,scope_basis:'speech'};
 // This is a search scope, not evidence that every scene was filmed. The existing
 // planner must still ground every selected interval in the source transcript.
 return {...selection,scene:combineScenes(scenes),automatic:true,scope_basis:'script_search'};
}
function automaticTakes(source,proposals){
 const length=source.duration_frames;
 if(!Number.isSafeInteger(length)||length<=0)throw Error('Durata sorgente non valida per le take automatiche');
 const rows=Array.isArray(proposals)?proposals.slice().sort((a,b)=>a.start_frame-b.start_frame):[];
 const ids=new Set();
 const valid=rows.length&&rows[0].start_frame===0&&rows.at(-1).end_frame===length&&rows.every((row,i)=>{const unique=typeof row.take_id==='string'&&row.take_id.length>0&&!ids.has(row.take_id);ids.add(row.take_id);return unique&&row.media_id===source.media_id&&Number.isSafeInteger(row.start_frame)&&Number.isSafeInteger(row.end_frame)&&row.end_frame>row.start_frame&&(!i||rows[i-1].end_frame===row.start_frame);})&&rows.slice(1).every(row=>!(source.segments||[]).some(s=>s.start_frame<row.start_frame&&s.end_frame>row.start_frame));
 const selected=valid?rows:[{media_id:source.media_id,take_id:source.take_id||source.media_id+':take:1',start_frame:0,end_frame:length,take_index:source.take_index||1,camera_id:source.camera_id||'camera_1',boundary_source:'whole_clip'}];
 return {fallback:!valid,segments:selected.map((row,i)=>({...row,take_index:row.take_index||i+1,confirmed:true,selection_mode:'automatic'}))};
}
module.exports={automaticScope,automaticTakes};
