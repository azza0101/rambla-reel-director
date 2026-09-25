"""Beat selection and timestamp-based JSON export; no model or provider calls."""
BUILD_JS = r'''
function buildAnimationExport(chunks, selected, projectId, videoContext=null){
 const round=n=>Math.round(n*1000000)/1000000;
 const ordered=chunks.map((c,index)=>({c,index})).sort((a,b)=>Number(a.c.start)-Number(b.c.start)||a.index-b.index);
 const chosen=ordered.map(({c},index)=>({c,index})).filter(({c})=>selected.has(c.id));
 const items=[];let previous=null,group=0,total=0;
 for(const {c,index} of chosen){
  if(typeof c.start!=='number'||typeof c.end!=='number'||!Number.isFinite(c.start)||!Number.isFinite(c.end)||c.start<0||c.end<c.start)throw Error(`Timestamp non validi per ${c.id}: impossibile calcolare la durata reale.`);
  const consecutive=!!previous&&index===previous.index+1;
  const gap=previous?round(c.start-previous.c.end):null;
  if(!consecutive)group++;
  if(previous)items.push({type:'separator',label:'────────────────',relationship:consecutive?'consecutive':'separate',gap_seconds:gap});
  const duration=round(c.end-c.start);total+=duration;
  items.push({type:'phrase',order:chosen.findIndex(x=>x.c.id===c.id)+1,id:c.id,text:c.text||c.id,duration_seconds:duration,start_seconds:c.start,end_seconds:c.end,concatenation_group:group,concatenated_with_previous:consecutive,previous_phrase_id:previous?.c.id||null,gap_from_previous_seconds:gap});
  previous={c,index};
 }
 return {video_context:videoContext,schema_version:'rambla-animation-phrases-1',project_id:projectId,timing_basis:'source transcript timestamps; duration = end - start, including internal pauses',concatenation_rule:'adjacent phrases in source timeline; gap_seconds reports pauses or overlaps',phrase_count:chosen.length,total_phrase_duration_seconds:round(total),items};
}
'''
CSS = '''<style>
.animationExport{margin:12px 0;padding:12px;border:1px solid #4c597d;border-radius:14px;background:#202743;display:grid;gap:10px}
.animationExport>button{white-space:normal;text-align:left;font-size:11px;line-height:1.5}
.animationTools{display:flex;flex-wrap:wrap;gap:7px}.animationTools button{flex:1;padding:8px;font-size:11px}
.animationExport p{font-size:11px;line-height:1.5;margin:0;color:#bbd5e4}
#phrases .phrase.animationChosen{background:#164b55!important;color:#e8ffff!important;box-shadow:inset 0 0 0 2px #57d5d0!important}
#phrases .phrase.animationChosen small{color:#a1f4eb!important}
#phrases .animationCheck{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border:1px solid #7bb8c5;border-radius:5px;float:right;margin:0 0 5px 6px;color:#bcfff8}
</style>'''
JS = BUILD_JS + r'''
let animationMode=false,animationProject=null;
const animationSelections=new Map();
function animationSelected(){if(!animationSelections.has(state.pid))animationSelections.set(state.pid,new Set());return animationSelections.get(state.pid)}
function animationJson(){const result=buildAnimationExport(state.data.chunks||[],animationSelected(),state.pid,state.data.animation_context||null);if(!result.phrase_count)throw Error('Seleziona almeno una frase.');return JSON.stringify(result,null,2)}
async function copyAnimationJson(){const text=animationJson();try{await navigator.clipboard.writeText(text)}catch(_){const area=document.createElement('textarea');area.value=text;document.body.appendChild(area);area.select();const ok=document.execCommand('copy');area.remove();if(!ok)throw Error('Copia non disponibile: usa ESPORTA JSON.')}document.getElementById('animationStatus').textContent='JSON copiato negli appunti.'}
function downloadAnimationJson(){const text=animationJson(),url=URL.createObjectURL(new Blob([text],{type:'application/json;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download=`frasi-animazione-${state.pid}.json`;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);document.getElementById('animationStatus').textContent='JSON esportato.'}
function installAnimationExport(){
 const rail=$('phrases');if(!rail)return;
 if(animationProject!==state.pid){animationMode=false;animationProject=state.pid}
 let panel=document.getElementById('animationExport');if(!panel){panel=document.createElement('section');panel.id='animationExport';panel.className='animationExport';rail.before(panel)}
 const chunks=state.data.chunks||[],selected=animationSelected(),valid=new Set(chunks.map(c=>c.id));for(const id of selected)if(!valid.has(id))selected.delete(id);
 panel.innerHTML=`<button id="animationToggle" aria-pressed="${animationMode}" ${chunks.length?'':'disabled'}>${animationMode?'FINE SELEZIONE ANIMAZIONE':'ESPORTA FRASI PER ANIMAZIONE'}</button>${animationMode?`<p>Clicca più frasi nella lista. Quelle turchesi saranno esportate, in ordine nel reel.</p><div class="animationTools"><button id="animationCopy" ${selected.size?'':'disabled'}>COPIA JSON</button><button id="animationDownload" ${selected.size?'':'disabled'}>ESPORTA JSON</button><button id="animationClear" ${selected.size?'':'disabled'}>SVUOTA</button></div><p id="animationStatus" role="status">${selected.size} frasi selezionate</p>`:''}`;
 $('animationToggle').onclick=()=>{animationMode=!animationMode;draw()};
 if(animationMode){$('animationCopy').onclick=copyAnimationJson;$('animationDownload').onclick=downloadAnimationJson;$('animationClear').onclick=()=>{selected.clear();draw()}}
 rail.querySelectorAll('[data-c]').forEach(button=>{const chosen=selected.has(button.dataset.c);button.classList.toggle('animationChosen',chosen);if(animationMode){button.setAttribute('aria-pressed',String(chosen));const check=document.createElement('span');check.className='animationCheck';check.textContent=chosen?'✓':'';check.setAttribute('aria-hidden','true');button.prepend(check);button.onclick=()=>{const id=button.dataset.c;selected.has(id)?selected.delete(id):selected.add(id);draw()}}});
}
const drawBeforeAnimation=draw;draw=()=>{drawBeforeAnimation();installAnimationExport()};
'''
