'use strict';
const fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto');
const VERSION='editorial-grounded-v3',MODEL='qwen/qwen3.8-27b';
const norm=s=>String(s||'').normalize('NFKC').toLowerCase().replace(/[^\p{L}\p{N}]+/gu,' ').trim().replace(/\s+/g,' ');
function spokenByBeat(scene,labels){const result={};for(const c of scene.clips)for(const u of c.units){const label=labels[c.key]?.[u.id];if(!label||label==='X')continue;const number=Number(label.split('/')[0]),b=scene.beats.find(b=>b.number===number);if(!b||b.kind!=='dialogue')continue;const key=b.id||b.beat_id;result[key]??=[];if(!result[key].includes(u.text))result[key].push(u.text);}return result;}
function validateEditorial(scene,labels,value){
 if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>k!=='events')||!Array.isArray(value.events)||value.events.length>Math.min(64,scene.beats.length*2))throw Error('Piano editoriale non valido');
 const spoken=spokenByBeat(scene,labels),allowed=['beat_id','anchor_text','kind','reactor','return_to_speaker','hold_reason','priority','reason'];const events=[];const seen=new Set();
 for(const e of value.events){
  if(!e||typeof e!=='object'||Object.keys(e).length!==allowed.length||Object.keys(e).some(k=>!allowed.includes(k)))throw Error('Evento editoriale non valido');
  const b=scene.beats.find(b=>(b.id||b.beat_id)===e.beat_id),anchor=norm(e.anchor_text);
  if(!b||b.kind!=='dialogue'||typeof e.anchor_text!=='string'||!anchor||e.anchor_text.length>100||anchor.split(' ').length>12||!spoken[e.beat_id]?.some(t=>(' '+norm(t)+' ').includes(' '+anchor+' ')))throw Error('Ancora editoriale non presente nel parlato');
  if(!['escalation','reveal','challenge','hesitation','release','pause'].includes(e.kind)||!['normal','high'].includes(e.priority)||typeof e.return_to_speaker!=='boolean'||!['none','listener_answers','gag_ending','suspense'].includes(e.hold_reason)||typeof e.reason!=='string'||!e.reason.trim()||e.reason.length>280)throw Error('Significato editoriale non valido');
  if(e.reactor!==null&&(!Object.hasOwn(scene.cast,e.reactor)||scene.cast[e.reactor]==='UNKNOWN'||scene.cast[e.reactor]===b.character))throw Error('Destinatario editoriale non valido');
  if(!e.return_to_speaker&&e.hold_reason==='none')throw Error('Manca motivazione del mancato ritorno al parlante');
  const key=e.beat_id+'|'+anchor+'|'+e.reactor;if(seen.has(key))throw Error('Evento editoriale duplicato');seen.add(key);events.push({...e});
 }
 return {events};
}
function makeEditorialRequest(scene,labels,directions){
 const spoken=spokenByBeat(scene,labels);const input={cast:scene.cast,script:scene.beats.map(b=>({id:b.id||b.beat_id,kind:b.kind,character:b.character,text:b.text})),spoken:Object.entries(spoken).map(([beat_id,variants])=>({beat_id,variants:variants.slice(-7)})),style:directions||{}};
 if(directions?.profile==='VIDEO COLICHE')input.reference_preferences=require('./video_coliche.json');
 const prompt='You are the editorial director of a filmed dialogue scene. Analyze the SCRIPT, actual SPOKEN lines and STYLE as source data. Preserve the dialogue, its order and audio. Identify a small set of meaningful changes of dramatic temperature: a sudden call, accusation, revelation, power shift, hesitation, release or intentional silence. A listener reaction must serve a story event, not a quota. Distinguish the person CALLED BY NAME from the visible listener AFFECTED by the call: they may be different. Use cast IDs, never invent a person. You are proposing editorial intentions, NOT choosing clips or timecodes. Local code will verify who is listening and whether footage is usable. Use verbatim anchor_text from a SPOKEN variant for the chosen beat_id, preferably the short exact phrase that triggers the change. Do not infer emotion as visually verified. For ordinary internal reactions prefer speaker-listener-speaker, returning legibly before the line ends. Stay on a listener only for an intentional answer pickup, gag ending or sustained suspense. Minimum reaction duration is 1.5 seconds; never propose repeated arbitrary alternation or a master that may not exist. Mark high priority only for clear decisive turns. Review the whole sequence for decisive turns, including sudden calls, threats or changes of addressee even if they follow an earlier revelation. Do not annotate every sentence; empty events is valid. Anchor the intention on the shortest verbatim trigger (often 1-4 words), not the entire line: a long anchor at the end prevents an internal reaction. Return-to-speaker is a preference rather than a quota: for a line-ending revelation followed by the affected listener answering, an intentional listener_answers ending is appropriate. If suspense resolves into a new scene, gag_ending or suspense can justify holding. Never assert an observed facial expression: describe only the narrative intention. Return ONLY JSON {"events":[{"beat_id":"supplied ID","anchor_text":"verbatim words","kind":"escalation|reveal|challenge|hesitation|release|pause","reactor":"cast ID or null","return_to_speaker":true,"hold_reason":"none|listener_answers|gag_ending|suspense","priority":"normal|high","reason":"short editorial reason"}]}. For null reactor use JSON null, not a string. No timestamps, source paths, clip IDs or extra keys. A false return_to_speaker requires a non-none hold_reason.\nSOURCE DATA\n'+JSON.stringify(input);
 if(Buffer.byteLength(prompt)>50000)throw Error('Scena troppo lunga per il passaggio editoriale');
 return {model:MODEL,reasoning_effort:'none',temperature:.2,max_completion_tokens:2500,messages:[{role:'user',content:prompt}]};
}
async function planEditorial(client,scene,labels,directions,onProgress=()=>{}){
 const request=makeEditorialRequest(scene,labels,directions),key=crypto.createHash('sha256').update(JSON.stringify({version:VERSION,request})).digest('hex'),file=path.join(client.root,'cache','editorial',key+'.json');
 try{const cached=validateEditorial(scene,labels,JSON.parse(await fs.readFile(file,'utf8')));onProgress({phase:'editorial',cache_hit:true});return {...cached,summary:{status:'ready',version:VERSION,model:MODEL,calls:0,cache_hit:true}};}catch{}
 const token=await client.key();client.controller=new AbortController();const signal=client.controller.signal;let calls=0;
 try{
  let body;
  for(let attempt=0;attempt<3;attempt++){
   if(signal.aborted)throw Error('Piano editoriale annullato');onProgress({phase:'editorial',cache_hit:false});const timeout=setTimeout(()=>client.controller?.abort(),60000);let response;
   try{response=await (client.request ? client.request.bind(client) : client.fetchImpl)('https://api.groq.com/openai/v1/chat/completions',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify(request),signal},'editorial');}catch{throw Error(signal.aborted?'Piano editoriale annullato o scaduto':'Connessione editoriale Groq non riuscita');}finally{clearTimeout(timeout);}
   calls++;body=await response.json().catch(()=>({}));if(response.status===429){const quota=client.quotaError?await client.quotaError(body,response,'editorial'):require('./groq_client').dailyQuotaError(body,client.responseProvider?.(response)||'Groq');if(quota)throw quota;}if(response.status===429&&attempt<2){const seconds=Math.min(60,Math.max(2,Number(response.headers?.get?.('retry-after'))||20));onProgress({phase:'quota',seconds});await client.sleep(seconds*1000);continue;}
   if(!response.ok)throw Error('Piano editoriale Groq non disponibile (HTTP '+response.status+')');break;
  }
  const choice=body?.choices?.[0];if(choice?.finish_reason!=='stop')throw Error('Risposta editoriale incompleta');let parsed;try{parsed=JSON.parse(choice.message?.content||'');}catch{throw Error('Risposta editoriale JSON non valida');}const result=validateEditorial(scene,labels,parsed);
  await fs.mkdir(path.dirname(file),{recursive:true});const tmp=file+'.'+crypto.randomUUID()+'.tmp';try{await fs.writeFile(tmp,JSON.stringify(result));await fs.rename(tmp,file);}finally{await fs.rm(tmp,{force:true}).catch(()=>{});}
  return {...result,summary:{status:'ready',version:VERSION,model:MODEL,calls,cache_hit:false}};
 }finally{client.controller=null;}
}
module.exports={validateEditorial,makeEditorialRequest,planEditorial,spokenByBeat};
