'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {renderSrt,fileName,mergeRanges}=require('./core');
function atomicJson(target,value){const tmp=target+'.'+crypto.randomUUID()+'.tmp';try{fs.writeFileSync(tmp,JSON.stringify(value,null,2),{flag:'wx',mode:0o600});fs.renameSync(tmp,target)}finally{if(fs.existsSync(tmp))fs.unlinkSync(tmp)}}
class Session{
 constructor(root,read){this.root=root;this.read=read;this.busy=false;this.mode='SINGLE';this.lastFolder=null;fs.mkdirSync(root,{recursive:true});this.file=path.join(root,'state.json');this.db={schema:1,timelines:{}};
  if(fs.existsSync(this.file)){try{if(fs.lstatSync(this.file).isSymbolicLink()||fs.statSync(this.file).size>4*1024*1024)throw Error();this.db=JSON.parse(fs.readFileSync(this.file,'utf8'));if(this.db.schema!==1||!this.db.timelines||Array.isArray(this.db.timelines))throw Error()}catch{throw Error('File di salvataggio danneggiato. Conservato in '+this.file+'; rinominalo per ripartire.')}}
 }
 assertIdle(){if(this.busy)throw Error('Operazione in corso: attendi il completamento')}
 key(s){return crypto.createHash('sha256').update(JSON.stringify([s.projectId,s.timelineId])).digest('hex')}
 state(){const saved=this.db.timelines[this.key(this.current)]||{ranges:[],original:true,context:false,folder:'',filename:'',geometry:this.current.geometry};
  if(!Array.isArray(saved.ranges)||typeof saved.folder!=='string'||typeof saved.filename!=='string')throw Error('Dati di salvataggio non validi');
  return {...saved,mode:this.mode,snapshot:this.current};
 }
 async refresh(){this.assertIdle();const fresh=await this.read();if(this.current&&this.key(this.current)!==this.key(fresh))this.mode='SINGLE';this.current=fresh;return this.state()}
 save(patch){this.assertIdle();if(!this.current)throw Error('Aggiorna la timeline');const state=this.state();
  for(const key of Object.keys(patch))if(!['mode','original','context','folder','filename'].includes(key))throw Error('Preferenza non valida');
  if('mode' in patch&&!['SINGLE','MULTI'].includes(patch.mode))throw Error('Modalità non valida');
  for(const key of ['original','context'])if(key in patch&&typeof patch[key]!=='boolean')throw Error('Opzione non valida');
  for(const key of ['folder','filename'])if(key in patch&&(typeof patch[key]!=='string'||patch[key].length>4096||patch[key].includes('\0')))throw Error('Percorso non valido');
  const {snapshot,mode,...saved}={...state,...patch};const db={...this.db,timelines:{...this.db.timelines,[this.key(this.current)]:saved}};atomicJson(this.file,db);this.db=db;this.mode=mode;return this.state();
 }
 storeRanges(ranges,geometry){const key=this.key(this.current),{snapshot,mode,...saved}=this.state();const db={...this.db,timelines:{...this.db.timelines,[key]:{...saved,ranges,geometry}}};atomicJson(this.file,db);this.db=db;return this.state()}
 async addRange(){this.assertIdle();if(!this.current)throw Error('Aggiorna la timeline');const fresh=await this.read();if(this.key(fresh)!==this.key(this.current))throw Error('Timeline cambiata: aggiorna IN / OUT');const state=this.state();if(state.ranges.length&&state.geometry!==fresh.geometry)throw Error('Timecode/FPS cambiati: svuota gli intervalli');if(!fresh.range)throw Error('IN - OUT not found');if(state.ranges.length>=10000)throw Error('Troppi intervalli');this.current=fresh;const ranges=[...state.ranges];if(!ranges.some(r=>r.a===fresh.range.a&&r.b===fresh.range.b))ranges.push(fresh.range);return this.storeRanges(ranges,fresh.geometry)}
 removeRange(index){this.assertIdle();const state=this.state();if(index===null)return this.storeRanges([],this.current.geometry);if(!Number.isInteger(index)||index<0||index>=state.ranges.length)throw Error('Intervallo non valido');return this.storeRanges(state.ranges.filter((_,i)=>i!==index),state.geometry)}
 async prepareOutput(){
  const state=this.state(),fresh=await this.read();if(this.key(fresh)!==this.key(this.current)||fresh.fingerprint!==this.current.fingerprint)throw Error('Timeline o sottotitoli cambiati: aggiorna IN / OUT prima di esportare');
   if(state.mode==='SINGLE'&&JSON.stringify(fresh.range)!==JSON.stringify(this.current.range))throw Error('IN / OUT cambiati: aggiorna prima di esportare');
   if(state.mode==='MULTI'&&state.geometry!==fresh.geometry)throw Error('Timecode/FPS cambiati: ricattura gli intervalli');
   const ranges=state.mode==='MULTI'?state.ranges:(fresh.range?[fresh.range]:[]);mergeRanges(ranges);

   return {state,fresh,ranges,output:renderSrt(fresh.timeline,fresh.captions,ranges,state)};
 }
 async copy(){this.assertIdle();if(!this.current)throw Error('Aggiorna la timeline');this.busy=true;try{return (await this.prepareOutput()).output}finally{this.busy=false}}
 async export(){this.assertIdle();if(!this.current)throw Error('Aggiorna la timeline');this.busy=true;
  try{const {state,fresh,ranges,output}=await this.prepareOutput();
   if(!state.folder||!fs.statSync(state.folder).isDirectory())throw Error('Seleziona una cartella valida');
   const name=fileName(state.filename,fresh.timeline.name,state.mode),target=path.join(state.folder,name);
   // Exclusive create: never destroy an existing export or follow its symlink.
   let fd;try{fd=fs.openSync(target,'wx',0o600)}catch(e){if(e.code==='EEXIST')throw Error('Il file esiste già: scegli un altro nome');throw e}
   try{fs.writeFileSync(fd,output,'utf8');fs.fsyncSync(fd)}catch(e){fs.closeSync(fd);fd=null;fs.unlinkSync(target);throw e}finally{if(fd!==null)fs.closeSync(fd)}
   this.lastFolder=state.folder;return {path:target,bytes:Buffer.byteLength(output),ranges:mergeRanges(ranges).length};
  }finally{this.busy=false}
 }
}
module.exports={Session,atomicJson};
