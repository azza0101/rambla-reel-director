'use strict';
const path=require('node:path'),fs=require('node:fs');const pluginRoot=[path.resolve(__dirname,'../../plugin'),path.resolve(__dirname,'../..')].find(p=>fs.existsSync(path.join(p,'day_catalog_resolve.js')));if(!pluginRoot)throw Error('Catalog plugin root missing');const base=require(path.join(pluginRoot,'day_catalog_resolve')),store=require(path.join(pluginRoot,'day_catalog_store'));
const CATALOG_POLICY='catalog-v3-neighbor-references';
function chooseAssignment(c,source,visual){
 const votes=new Map(),rows=c.memberships.filter(m=>m.media_id===source.media_id&&m.status!=='rejected'&&!m.stale_due_script&&c.scenes.some(s=>s.scene_id===m.scene_id));
 for(const m of rows)votes.set(m.scene_id,(votes.get(m.scene_id)||0)+(m.source_end_frame-m.source_start_frame)*(m.confidence||.6));
 const rank=[...votes].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])),total=rank.reduce((n,r)=>n+r[1],0),support=total?rank[0][1]/total:0;
 const speech=rank.length&&support>=.65?rank[0][0]:null,strong=!!speech&&support>=.85&&rows.filter(r=>r.scene_id===speech).some(r=>r.status==='auto_ready');
 let scene_id=speech,basis=speech?'speech':'unassigned',reason=speech?'SPEECH_CONTEXT':'NO_RELIABLE_MATCH';
 if(visual?.scene_id&&c.scenes.some(s=>s.scene_id===visual.scene_id)){
  if(!speech){if(visual.specificity==='setting'&&rank.length&&!votes.has(visual.scene_id)){scene_id=null;reason='SETTING_NOT_SCENE';}else{scene_id=visual.scene_id;basis='visual';reason='VISUAL_MATCH';}}
  else if(speech===visual.scene_id){basis='speech_and_visual';reason='AGREEMENT';}
  else if(visual.specificity==='setting'&&rows.some(r=>r.scene_id===speech&&(r.evidence||[]).some(e=>(e.text||'').split(/\s+/).length>=5))){basis='speech';reason='SPEECH_OVER_SETTING';}
  else if(!strong){scene_id=null;basis='conflict';reason='SPEECH_VISUAL_CONFLICT';}
 }
 const neighbor=visual?.neighbors;
 if(!strong&&visual?.category!=='broll'&&neighbor?.scene_id&&c.scenes.some(s=>s.scene_id===neighbor.scene_id)){
  const informative=rows.some(r=>r.scene_id===neighbor.scene_id&&(r.evidence||[]).some(e=>(e.text||'').split(/\s+/).length>=5));
  const speechAgrees=rank[0]?.[0]===neighbor.scene_id&&support>=.55&&informative;
  const brackets=!rank.length&&neighbor.anchors?.some(a=>a.side==='before')&&neighbor.anchors?.some(a=>a.side==='after');
  if(speechAgrees||brackets){scene_id=neighbor.scene_id;basis=speechAgrees?'speech_and_neighbors':'visual_neighbors';reason='TRUSTED_NEIGHBOR_VISUAL_MATCH';}
 }
 if(!speech&&visual?.category==='broll'){scene_id=null;basis='visual_broll';reason='VISUAL_BROLL';}
 return {media_id:source.media_id,scene_id,category:!speech&&visual?.category==='broll'?'broll':null,basis,reason,needs_visual:!strong,speech_support:support,candidate_scenes:rank.map(r=>r[0]),visual:visual||null};
}
// Capture sequence comes from the file name, never its current (possibly wrong) bin.
function sequence(source){const m=(source.name||'').match(/^(.*?)(\d+)\.[^.]+$/);return m?{camera:m[1].toLowerCase(),index:Number(m[2])}:null;}
function neighborReferences(c,source){const target=sequence(source);if(!target)return [];const plausible=chooseAssignment(c,source).candidate_scenes;const candidates=[];
 for(const other of c.sources){if(other.media_id===source.media_id)continue;const q=sequence(other);if(!q||q.camera!==target.camera||Math.abs(q.index-target.index)>20)continue;const manual=(c.clip_assignments||[]).find(a=>a.media_id===other.media_id&&a.manual&&!a.stale&&a.scene_id&&c.scenes.some(s=>s.scene_id===a.scene_id));const speech=chooseAssignment(c,other);const scene_id=manual?.scene_id||(!speech.needs_visual?speech.scene_id:null);if(!scene_id||plausible.length&&!plausible.includes(scene_id))continue;candidates.push({source:other,scene_id,side:q.index<target.index?'before':'after',distance:Math.abs(q.index-target.index),basis:manual?'manual':'strong_speech'});}
 return candidates.sort((a,b)=>a.distance-b.distance||a.source.media_id.localeCompare(b.source.media_id)).slice(0,4);
}
function assignmentKey(c,source,references=neighborReferences(c,source)){return store.hash([CATALOG_POLICY,source.media_id,source.path,source.file_size,source.mtime_ns,source.duration_frames,source.fps,c.script_fingerprint,c.scenes.map(s=>[s.scene_id,s.heading,s.beats]),c.memberships.filter(m=>m.media_id===source.media_id),references.map(r=>[r.source.media_id,r.scene_id,r.source.path,r.source.file_size,r.source.mtime_ns])]);}
function needsRefresh(c){return c.catalog_policy!==CATALOG_POLICY||c.sources.some(s=>{const a=(c.clip_assignments||[]).find(a=>a.media_id===s.media_id);return !a||!a.manual&&s.visual_catalog_key!==assignmentKey(c,s);});}
async function verify(sdk,c,a){
 if(!a.scanDayMedia)return a.verifiedSources(sdk,c);
 const scan=await a.scanDayMedia(sdk,{rootFolderId:c.source_root_folder_id});if(scan.projectId!==c.project_id)throw Error('Progetto Resolve cambiato');
 for(const source of c.sources){const actual=scan.media.find(s=>s.media_id===source.media_id);if(!actual)throw Error('Sorgente non trovata');if(actual.fingerprint!==source.fingerprint){const pending=c.operations.some(o=>o.type==='move_clip'&&o.media_id===source.media_id&&o.destination_folder_id===actual.original_folder_id);if(!pending||['path','file_size','mtime_ns','fps','duration_frames','start_tc'].some(k=>source[k]!==actual[k]))throw Error('Sorgente cambiata: rianalizza');}}
 return scan;
}
function operations(c){const names=new Map();return (c.clip_assignments||[]).filter(r=>(r.scene_id||r.category==='broll')&&!r.stale).map(r=>{const s=r.category==='broll'?{scene_id:'catalog_broll',heading:'DETTAGLI E B-ROLL',ordinal:0}:c.scenes.find(s=>s.scene_id===r.scene_id);if(!s)throw Error('Scena non più presente');let name=s.heading.replace(/[<>:"/\\|?*\x00-\x1f]/g,' ').trim().replace(/[. ]+$/,'').slice(0,120)||'Scena '+s.ordinal;const collision=c.scenes.filter(x=>x.heading.replace(/[<>:"/\\|?*\x00-\x1f]/g,' ').trim().replace(/[. ]+$/,'').slice(0,120)===name).length>1;if(collision)name+=' ['+s.ordinal+']';names.set(s.scene_id,name);return {type:'move_clip',operation_id:store.hash([c.catalog_id,r.media_id,s.scene_id]).slice(0,24),media_id:r.media_id,scene_id:s.scene_id,folder_name:name};});}
async function previewClipMoves(sdk,c,a=base){await verify(sdk,c,a);const ops=operations(c);return {kind:'whole_clip_moves',project_id:c.project_id,catalog_id:c.catalog_id,revision:c.revision,operations:ops,preview_id:store.hash([c.project_id,c.catalog_id,c.revision,ops]),blocked:!ops.length,warnings:['Sposta le clip originali intere nei bin delle scene dentro la cartella riprese. Nessuna subclip o timeline viene creata. Le clip senza scena restano al loro posto.']};}
async function applyClipMoves(sdk,c,preview,{confirmed,persist}={},a=base){
 if(!confirmed||typeof persist!=='function')throw Error('Conferma richiesta');const now=await previewClipMoves(sdk,c,a);if(now.preview_id!==preview.preview_id||now.blocked)throw Error('Anteprima scaduta');
 const {pool,pm,project}=await a.context(sdk);if(String(await project.GetUniqueId())!==c.project_id)throw Error('Progetto cambiato');if(!await pm.SaveProject())throw Error('Salvataggio Resolve fallito');const originalFolder=await pool.GetCurrentFolder(),result={applied:[],skipped:[],failed:[]};
 try{const all=await a.folders(pool),root=all.find(f=>f.id===c.source_root_folder_id);if(!root)throw Error('Cartella sorgente rimossa');
 for(const op of now.operations){let journal=c.operations.find(j=>j.operation_id===op.operation_id&&j.type==='move_clip');if(!journal){journal={...op,status:'planned'};c.operations.push(journal);}try{
  const scan=await verify(sdk,c,a),source=c.sources.find(s=>s.media_id===op.media_id),item=scan.items.get(op.media_id);if(!item)throw Error('Clip rimossa');
  const matches=[];for(const f of await root.folder.GetSubFolderList()||[])if(await f.GetName()===op.folder_name)matches.push(f);if(matches.length>1)throw Error('Bin scena duplicato');const dest=matches[0]||await pool.AddSubFolder(root.folder,op.folder_name);if(!dest)throw Error('Creazione bin fallita');
  journal.destination_folder_id=String(await dest.GetUniqueId());journal.origin_folder_id ||= source.original_folder_id;await persist(c);
  const present=async()=>{for(const m of await dest.GetClipList()||[])if(String(await m.GetMediaId())===op.media_id)return true;return false;};
  const already=await present();if(!already){journal.status='moving';await persist(c);if(!await pool.MoveClips([item],dest))throw Error('Spostamento rifiutato');if(!await present())throw Error('Clip non trovata nel bin destinazione');}
  source.catalog_origin_folder_id ||= journal.origin_folder_id;const actual=await a.sourceRecord(item,{id:journal.destination_folder_id,path:root.path+'/'+op.folder_name});Object.assign(source,actual);journal.status='applied';c.revision++;await persist(c);if(already)result.skipped.push(op.operation_id);else result.applied.push({media_id:op.media_id,scene_id:op.scene_id,folder_id:journal.destination_folder_id});
 }catch(error){journal.status='failed';journal.error_detail=String(error.message).slice(0,500);await persist(c);result.failed.push({media_id:op.media_id,message:journal.error_detail});}}
 if(!await pm.SaveProject())throw Error('Salvataggio Resolve fallito');
 }finally{if(originalFolder)await pool.SetCurrentFolder(originalFolder);}return result;
}
module.exports={chooseAssignment,neighborReferences,assignmentKey,needsRefresh,CATALOG_POLICY,previewClipMoves,applyClipMoves};
