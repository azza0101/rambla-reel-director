'use strict';
const fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto');
const hash=v=>crypto.createHash('sha256').update(JSON.stringify(v)).digest('hex');
const validSpeech=s=>Array.isArray(s?.segments)&&s.segments.some(r=>Number.isFinite(r.start_frame)&&r.end_frame>r.start_frame&&/[\p{L}\p{N}]/u.test(r.text||''));
function buildContext(c,source){
 const assignment=(c.clip_assignments||[]).find(a=>a.media_id===source.media_id&&!a.stale),scene=c.scenes.find(s=>s.scene_id===assignment?.scene_id),spoken=validSpeech(source),visual=assignment?.visual;
 const role=spoken?'dialogue':assignment?.category==='broll'?'broll':scene?'visual_coverage':'unassigned';
 return {schema_version:1,catalog_id:c.catalog_id,project_id:c.project_id,script_fingerprint:c.script_fingerprint,media_id:source.media_id,scene:scene?{scene_id:scene.scene_id,heading:scene.heading,ordinal:scene.ordinal,number:Number(scene.heading?.match(/^\s*scena\s*(\d+)/i)?.[1])||scene.ordinal}:null,role,transcript_status:spoken?'available':source.transcript_status==='failed'?'unavailable':'missing',audio_status:'unverified',assignment:{basis:assignment?.basis||'unassigned',reason:assignment?.reason||null,manual:!!assignment?.manual,proposed:!assignment?.manual},evidence:{visual_score:visual?.score??null,visual_reason:visual?.reason||null,reference_media_ids:(visual?.neighbors?.anchors||[]).map(a=>a.media_id)},coverage_eligible:['visual_coverage','broll'].includes(role)&&source.duration_frames/source.fps>=1.5,automatic_insert:false};
}
function stampCatalog(c){let changed=false;for(const source of c.sources){const context=buildContext(c,source);if(JSON.stringify(source.edit_context)!==JSON.stringify(context)){source.edit_context=context;changed=true;}}return changed;}
async function collectContext(c,media,{projectId,scriptFingerprint,stat=filename=>fs.stat(filename,{bigint:true})}){
 const result={schema_version:1,project_id:projectId,analysis_script_fingerprint:scriptFingerprint,entries:[],cached_sources:[],warnings:[]};
 if(c.project_id!==projectId||c.script_fingerprint!==scriptFingerprint){result.warnings.push('Catalogo di altro progetto o copione: dati non riusati.');return result;}
 const norm=p=>{const n=path.normalize(String(p));return process.platform==='win32'?n.toLowerCase():n;};
 for(const item of media){const source=c.sources.find(s=>s.media_id===item.media_id);if(!source)continue;
 try{if(norm(source.path)!==norm(item.path)||item.duration_frames!==source.duration_frames||item.fps!==undefined&&Math.abs(item.fps-source.fps)>.001||item.start_tc!==undefined&&item.start_tc!==source.start_tc)throw Error('Identità diversa');const actual=await stat(item.path);if(String(actual.size)!==source.file_size||String(actual.mtimeNs)!==source.mtime_ns)throw Error('File cambiato');result.entries.push(buildContext(c,source));if(validSpeech(source))result.cached_sources.push({...source,segments:source.segments});}
 catch{result.warnings.push('Dati catalogo non riusati per '+(item.name||item.media_id)+': sorgente cambiata o non disponibile.');}}
 return result;
}
async function prepareSources(media,existing,context,read){const rows=[];for(const item of media){const cached=existing.find(s=>s.media_id===item.media_id&&validSpeech(s))||(context?.cached_sources||[]).find(s=>s.media_id===item.media_id&&validSpeech(s)),entry=context?.entries?.find(c=>c.media_id===item.media_id);let source=cached;
 if(!source){try{source=(await read([item],{skipTranscribeIds:entry?[item.media_id]:[]}))[0];}catch(error){if(!entry)throw error;source={...item,segments:[],transcript_error:String(error.message)};}}
 rows.push({...item,...source,item:undefined,take_id:source?.take_id||item.media_id+':take:1',take_index:source?.take_index||rows.length+1,camera_id:source?.camera_id||'camera_1',segments:source?.segments||[],...(entry?{catalog_context:entry}:{})});}return rows;}
const OPEN='[OMNICUT CATALOG v1]',CLOSE='[/OMNICUT CATALOG]';
function mergeComment(before,context){const text=String(before||''),role={dialogue:'Dialogo',visual_coverage:'Copertura visiva',broll:'DETTAGLI E B-ROLL',unassigned:'Da assegnare'}[context.role],block=OPEN+'\nScena: '+(context.scene?.heading||'Non assegnata')+'\nRuolo: '+role+'\nTrascrizione: '+(context.transcript_status==='available'?'disponibile':'non disponibile; assenza di parlato non verificata')+'\nAssegnazione: '+(context.assignment.manual?'manuale':'proposta')+' | '+context.assignment.basis+'\nCatalogo: '+context.catalog_id+' | Media: '+context.media_id+'\n'+CLOSE;
 const start=text.indexOf(OPEN),end=text.indexOf(CLOSE);if(start<0&&end<0)return text+(text&&!text.endsWith('\n')?'\n':'')+block;
 if(start<0||end<start||text.indexOf(OPEN,start+1)>=0||text.indexOf(CLOSE,end+CLOSE.length)>=0)throw Error('Blocco metadati Omni-Cut incompleto o duplicato: note conservate');return text.slice(0,start)+block+text.slice(end+CLOSE.length);}
const ascii=value=>String(value||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').replace(/[^\x20-\x7e]/g,' ');
function searchableFields(context){const number=context.scene?.number||context.scene?.ordinal,tag=number?'OMNICUT_SCENA_'+String(number).padStart(2,'0'):'OMNICUT_SENZA_SCENA',role={dialogue:'Dialogo',visual_coverage:'Copertura visiva',broll:'DETTAGLI E B-ROLL',unassigned:'Da assegnare'}[context.role];return {'OmniCut Scena':ascii(context.scene?.heading||'Non assegnata'),'OmniCut Ruolo':role,'OmniCut Trascrizione':context.transcript_status==='available'?'Disponibile':'Non disponibile - assenza di parlato non verificata','OmniCut Tags':tag+' OMNICUT_'+context.role.toUpperCase()+' OMNICUT_TRANSCRIPT_'+context.transcript_status.toUpperCase(),'OmniCut Data':JSON.stringify(context).replace(/[\u007f-\uffff]/g,ch=>'\\u'+ch.charCodeAt(0).toString(16).padStart(4,'0'))};}
async function writeMetadata(item,context,{journal,persist}){
 if(typeof item.GetThirdPartyMetadata==='function'&&typeof item.SetThirdPartyMetadata==='function'){
  const current=await item.GetThirdPartyMetadata(),fields=searchableFields(context);
  if(current&&typeof current==='object'){
   if(Object.entries(fields).every(([key,value])=>current[key]===value))return {status:'unchanged',field:'third_party'};
   journal.catalog_metadata={...(journal.catalog_metadata||{}),field:'third_party',before:(journal.catalog_metadata?.field==='third_party'?journal.catalog_metadata.before:undefined)??Object.fromEntries(Object.keys(fields).map(key=>[key,current[key]??null])),last_before:Object.fromEntries(Object.keys(fields).map(key=>[key,current[key]??null])),after_hash:hash(fields),status:'writing'};await persist();
   if(await item.SetThirdPartyMetadata(fields)){const check=await item.GetThirdPartyMetadata();if(Object.entries(fields).some(([key,value])=>check?.[key]!==value))throw Error('Verifica metadati personalizzati Resolve fallita');journal.catalog_metadata.status='written';await persist();return {status:'written',field:'third_party'};}
  }
 }
 const all=await item.GetMetadata();if(!all||typeof all!=='object'||typeof item.SetMetadata!=='function')return {status:'unsupported',message:'Metadati Resolve non disponibili: dati conservati nel catalogo locale'};
 const before=all.Comments||'';if(/[^\x00-\x7f]/.test(before))return {status:'unsupported',message:'Annotazioni Unicode conservate: sintesi disponibile nel catalogo locale'};
 const after=mergeComment(before,{...context,scene:context.scene?{...context.scene,heading:ascii(context.scene.heading)}:null});if(after===before)return {status:'unchanged'};
 journal.catalog_metadata={...(journal.catalog_metadata||{}),field:'Comments',before:(journal.catalog_metadata?.field==='Comments'?journal.catalog_metadata.before:undefined)??before,last_before:before,after_hash:hash(after),status:'writing'};await persist();if(!await item.SetMetadata({Comments:after}))throw Error('Scrittura metadati Resolve rifiutata');const check=await item.GetMetadata();if(check?.Comments!==after)throw Error('Verifica metadati Resolve fallita');journal.catalog_metadata.status='written';await persist();return {status:'written',field:'Comments'};
}
module.exports={hash,validSpeech,buildContext,stampCatalog,collectContext,prepareSources,mergeComment,searchableFields,writeMetadata};
