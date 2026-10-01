"""Confirmed RAMBLA to Resolve handoff panel."""

PANEL = r'''
<section class="panel genericCoverageMicroV34">
  <details class="genericCoverageV33"><summary><strong>6 · Coperture generiche</strong><small>12 video Pexels sul tema generale, pronti per la coda della timeline</small></summary><h3>Coperture del tema</h3><button id="loadGenericCoverageV33">CERCA 12 VIDEO GENERICI</button><h3>Coperture del luogo</h3><p class="muted">I luoghi riconosciuti nel testo avranno gruppi separati di risultati.</p><button id="loadPlaceCoverageV35">COPERTURE DEL LUOGO · CERCA VIDEO</button><p id="genericCoverageStatusV33" class="muted"></p><div id="genericCoverageCardsV33" class="genericCoverageCardsV33"></div></details>
</section>
<section class="panel timelineExportV33" id="timelineExportV33">
  <div class="top"><div><h2>7 · Export timeline <span id="timelineExportCompleteV28" class="stepStatusV12" hidden></span> <span id="resolveBridgeLiveV34" class="resolveBridgeLiveV34 off">BRIDGE OFFLINE</span></h2>
  <p class="muted">Prepara sottotitoli, parole evidenziate e B-roll. Resolve li applica soltanto dopo la conferma nel bridge.</p></div></div>
  <button id="sendResolvePackageV33" class="primary resolvePrimaryV33">INVIA A RESOLVE · SUBS + FRASI + B-ROLL</button>
  <div id="resolveDeliveryV33" class="resolveDeliveryV33" hidden><div id="resolveDeliveryCheckV33" class="resolveDeliveryCheckV33" hidden>✓</div><strong id="resolveDeliveryTitleV33">Preparazione pacchetto Resolve…</strong><span id="resolveDeliverySummaryV33"></span><div id="resolveDeliveryProgressV33" class="resolveDeliveryProgressBarV34"><i></i></div><b id="resolveDeliveryPercentV37">0%</b><small id="resolveDeliveryDetailV33"></small></div>
  <details id="resolveDebugV39" hidden><summary>Diagnostica Resolve</summary><button id="copyResolveDebugV39">COPIA DIAGNOSTICA</button><textarea id="resolveDebugTextV39" readonly aria-label="Diagnostica Resolve" style="width:100%;min-height:150px;margin-top:8px"></textarea></details><details class="legacyExportsV33"><summary>Export file e strumenti precedenti</summary><div class="timelineExportActionsV33"><button id="exportTimelineXmlV33">ESPORTA XML</button><button id="exportTimelineDraV33">ESPORTA DRA</button><button id="openTimelineResolveV33">CREA SUBITO IN RESOLVE · TEMP</button></div></details>
  <p id="timelineExportStatusV33" class="muted" role="status">Puoi inviare anche soltanto subs o parole evidenziate.</p>
</section>
'''

CSS = r'''<style id="timeline-export-v33-style">
.genericCoverageV33{margin:12px 0}.genericCoverageCardsV33{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin-top:10px}.genericCardV33{border:2px solid #454e77;border-radius:12px;overflow:hidden;background:#191e38;cursor:pointer}.genericCardV33.selected{border-color:#d7bd84;box-shadow:0 0 0 2px #d7bd8444}.genericCardV33 video{width:100%;aspect-ratio:16/9;object-fit:cover;background:#0b0e1d}.genericCardV33 div{padding:8px}
.genericCoverageMicroV34{margin-top:16px;padding:13px 16px;background:linear-gradient(145deg,#312c24,#25243a);border:1px solid #8c7447}.genericCoverageMicroV34 summary{display:flex;align-items:center;gap:10px;color:#f0d59b;cursor:pointer}.genericCoverageMicroV34 summary small{color:#bbb6ad;font-weight:400}.genericCoverageMicroV34 .genericCoverageV33{margin:0}.genericCoverageMicroV34 button{margin-top:12px;border-color:#b89555;color:#f0d59b}
.timelineExportV33{margin-top:16px;background:linear-gradient(145deg,#252b4c,#1d223e);border-color:#58658f}.resolvePrimaryV33{width:100%;min-height:52px;font-size:15px;margin-top:12px}.resolveDeliveryV33{display:grid;grid-template-columns:auto 1fr;gap:7px 12px;align-items:center;margin-top:12px;padding:16px;border:1px solid #778548;border-radius:12px;background:#18263a}.resolveDeliveryV33 strong,.resolveDeliveryV33 span,.resolveDeliveryV33 progress,.resolveDeliveryV33 small{grid-column:2}.resolveDeliveryV33 strong{color:#d8ff5b;font-size:15px}.resolveDeliveryV33 progress{width:100%;height:10px}.resolveDeliveryV33.receivedV33{border-color:#48a967;background:#142d22}.resolveDeliveryCheckV33{grid-row:1/5;align-self:center;width:58px;height:58px;border-radius:50%;display:grid;place-items:center;background:#50c878;color:#08160d;font-size:38px;font-weight:950;box-shadow:0 0 24px #50c87855}.resolveDeliveryCheckV33[hidden]{display:none}.legacyExportsV33{margin-top:12px}.timelineExportActionsV33{display:flex;gap:9px;flex-wrap:wrap;margin-top:9px}.timelineExportV33.busyV33{border-color:#c69b39}.timelineExportV33.errorV33{border-color:#a54d58}@media(max-width:700px){.timelineExportActionsV33 button{flex:1 1 100%}}
.resolveBridgeLiveV34{display:inline-block;margin-left:9px;padding:4px 8px;border-radius:999px;font-size:10px;vertical-align:middle;color:#d8ff5b;background:#183727;border:1px solid #4e9d68}.resolveBridgeLiveV34.off{color:#ff9d9d;background:#3a202b;border-color:#9f5263}
.resolveDeliveryV33[hidden]{display:none}.resolveDeliveryProgressBarV34{grid-column:1/-1;width:100%;min-width:0;height:14px;border-radius:999px;background:#e5e7ee;overflow:hidden}.resolveDeliveryProgressBarV34 i{display:block;width:var(--p,0%);height:100%;background:#5576e8;transition:width .2s linear}
</style>'''

JS = r'''
let resolveHandoffIdV33=null,resolveHandoffPollV33=null,resolvePreparingV37=false,resolveDeliveryStartedV37=0;
let genericCoverageV33={items:[],selected:[]};
async function pollResolveBridgeLiveV34(){try{const row=await api('/resolve-bridge/session'),badge=$('resolveBridgeLiveV34');badge.textContent=row.connected?'BRIDGE CONNECTED':'BRIDGE OFFLINE';badge.classList.toggle('off',!row.connected)}catch(_){const badge=$('resolveBridgeLiveV34');badge.textContent='BRIDGE OFFLINE';badge.classList.add('off')}}
function renderGenericCoverageV33(){const chosen=new Set(genericCoverageV33.selected||[]);$('genericCoverageCardsV33').innerHTML=[...(genericCoverageV33.items||[])].sort((a,b)=>(a.place||'').localeCompare(b.place||'')).map((row,index,rows)=>`${index===0||row.place!==rows[index-1].place?`<h3 class="placeCoverageGroup">${esc(row.place?'Coperture del luogo · '+row.place:'Coperture del tema')}</h3>`:''}<article class="genericCardV33 ${chosen.has(String(row.provider_id))?'selected':''}" data-generic-id="${esc(row.provider_id)}"><video muted loop playsinline preload="metadata" poster="${esc(row.preview_url)}" src="${esc(row.selected_rendition_url)}"></video><div><b>${esc(row.title||row.query)}</b><br><small>Pexels · ${Math.round(row.duration||0)}s</small></div></article>`).join('');document.querySelectorAll('[data-generic-id]').forEach(card=>{card.onclick=async()=>{const id=card.dataset.genericId,set=new Set(genericCoverageV33.selected||[]);set.has(id)?set.delete(id):set.add(id);genericCoverageV33.selected=[...set];renderGenericCoverageV33();await api(`/projects/${state.pid}/generic-coverage/selection`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider_ids:genericCoverageV33.selected})})};const video=card.querySelector('video');card.onmouseenter=()=>video.play().catch(()=>{});card.onmouseleave=()=>{video.pause();video.currentTime=0}})}
async function loadGenericCoverageV33(refresh=false,scope='topic'){const pid=state.pid;if(!pid)return;const buttons=[$('loadGenericCoverageV33'),$('loadPlaceCoverageV35')];buttons.forEach(b=>b.disabled=true);$('genericCoverageStatusV33').textContent=scope==='places'?'Cerco video dei luoghi citati nel testo…':'Cerco video orizzontali sul tema generale…';try{const result=await api(`/projects/${pid}/generic-coverage?refresh=${refresh}&scope=${scope}`);if(state.pid!==pid)return;genericCoverageV33=result;renderGenericCoverageV33();$('genericCoverageStatusV33').textContent=`${result.items.length} video unici · selezionati ${result.selected.length}. ${(result.errors||[]).join(' · ')}`}catch(error){if(state.pid===pid)$('genericCoverageStatusV33').textContent=error.message||String(error)}finally{buttons.forEach(b=>b.disabled=false)}}
function syncTimelineExportV33(){const disabled=!state.pid||!!state.run||resolvePreparingV37;for(const id of ['sendResolvePackageV33','exportTimelineXmlV33','exportTimelineDraV33','openTimelineResolveV33'])$(id).disabled=disabled}
function summaryResolveHandoffV33(s={}){return `${s.broll_count||0} B-roll · ${s.subtitle_count||0} subs · ${s.title_count||0} frasi${s.generic_broll_count?` · ${s.generic_broll_count} generiche`:''}${s.unavailable_count?` · ${s.unavailable_count} non disponibili`:''}`}
function setResolveDeliveryProgressV33(value){const percent=Math.max(0,Math.min(100,Number(value)||0)),bar=$('resolveDeliveryProgressV33');bar.style.setProperty('--p',`${percent}%`);bar.setAttribute('role','progressbar');bar.setAttribute('aria-valuemin','0');bar.setAttribute('aria-valuemax','100');bar.setAttribute('aria-valuenow',String(percent));$('resolveDeliveryPercentV37').textContent=`${percent}%`}
async function pollResolveHandoffV33(){
 if(!resolveHandoffIdV33)return;
 try{
  const row=await api(`/resolve-handoffs/${resolveHandoffIdV33}/status`),received=!!row.bridge_received_at,done=row.status==='completed',applying=row.status==='applying',failed=row.status==='failed';
  const box=$('resolveDeliveryV33');box.hidden=false;box.classList.toggle('receivedV33',(received||done)&&!failed);$('resolveDeliveryCheckV33').hidden=!(received||done)||failed;
  $('resolveDeliverySummaryV33').textContent=summaryResolveHandoffV33(row.summary);
  setResolveDeliveryProgressV33((applying||failed)?row.progress?.percent:(received||done?100:90));$('resolveDebugV39').hidden=false;
  $('resolveDeliveryTitleV33').textContent=failed?'OPERAZIONE RESOLVE NON RIUSCITA':done?`TIMELINE CREATA · ${row.result?.timeline_name||''}`:applying?'APPLICAZIONE IN RESOLVE':received?'ESPORTATO SU RESOLVE · RICEVUTO DAL BRIDGE':'PACCHETTO PRONTO · ATTESA RICEZIONE';
  if(failed){$('resolveDeliveryDetailV33').textContent=row.error||'Controlla il bridge';await loadResolveDebugV39();$('resolveDebugV39').open=true;}
  else if(done)$('resolveDeliveryDetailV33').textContent='Operazione completata.';
  else if(applying)$('resolveDeliveryDetailV33').textContent=row.progress?.message||'Applicazione in corso';
  else if(received)$('resolveDeliveryDetailV33').textContent='Premi APPLICA nel bridge quando vuoi creare la timeline.';
  else {const live=await api('/resolve-bridge/session'),seconds=Math.floor((Date.now()-resolveDeliveryStartedV37)/1000);$('resolveDeliveryDetailV33').textContent=!live.connected?'Preparazione terminata. Bridge offline: aprilo in Resolve, poi ripeti INVIA.':live.bridge_session_id!==row.bridge_session_id?'Il bridge è stato riaperto: ripeti INVIA per la nuova sessione.':`Attendo conferma dal bridge da ${seconds}s. ${seconds>15?'Nessuna conferma ricevuta: la consegna non è completata.':'Nessuna modifica alla timeline fino ad APPLICA.'}`;}
  if(done||failed)clearInterval(resolveHandoffPollV33);
 }catch(error){$('resolveDeliveryDetailV33').textContent='Non riesco a verificare la consegna: '+(error.message||String(error))}
}
async function prepareResolveHandoffV33(){
 if(resolvePreparingV37)return;
 resolvePreparingV37=true;clearInterval(resolveHandoffPollV33);resolveHandoffIdV33=null;
 const panel=$('timelineExportV33'),box=$('resolveDeliveryV33');syncTimelineExportV33();panel.classList.add('busyV33');panel.classList.remove('errorV33');box.hidden=false;box.classList.remove('receivedV33');$('resolveDeliveryCheckV33').hidden=true;
 $('resolveDeliveryTitleV33').textContent='PREPARAZIONE PER RESOLVE';$('resolveDeliverySummaryV33').textContent='Controllo le selezioni salvate';setResolveDeliveryProgressV33(0);$('resolveDeliveryDetailV33').textContent='Avvio…';$('timelineExportStatusV33').textContent='';box.scrollIntoView({block:'nearest',behavior:'smooth'});
 const projectId=state.pid;
 try{
  let job=await api(`/projects/${projectId}/resolve-preparation`,{method:'POST'});
  while(true){
   setResolveDeliveryProgressV33(job.percent);$('resolveDeliverySummaryV33').textContent=job.message;$('resolveDeliveryDetailV33').textContent=`Tempo trascorso: ${job.elapsed_seconds||0}s · avanzamento aggiornato dal server`;
   if(job.status==='failed')throw Error(job.message||job.error||'Preparazione non riuscita');
   if(job.status==='ready'){resolveHandoffIdV33=job.package.package_id;break;}
   await new Promise(resolve=>setTimeout(resolve,500));job=await api(`/resolve-preparation/${job.job_id}`);
  }
  resolveDeliveryStartedV37=Date.now();resolveHandoffPollV33=setInterval(pollResolveHandoffV33,1000);await pollResolveHandoffV33();
 }catch(error){panel.classList.add('errorV33');$('resolveDeliveryTitleV33').textContent='INVIO NON RIUSCITO';$('resolveDeliveryDetailV33').textContent=error.message||String(error)}
 finally{resolvePreparingV37=false;panel.classList.remove('busyV33');syncTimelineExportV33()}
}
async function legacyTimelineExportV33(path,download){try{const response=await fetch(`/api/curation/projects/${state.pid}${path}`,{method:path.startsWith('/exports/')?'GET':'POST'});if(!response.ok){const body=await response.json().catch(()=>({}));throw Error(body.detail||`HTTP ${response.status}`)}if(download){const blob=await response.blob(),a=document.createElement('a'),url=URL.createObjectURL(blob);a.href=url;a.download=download;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}else{const result=await response.json();$('timelineExportStatusV33').textContent=`Timeline creata · ${result.timeline_name||''}`}}catch(error){if(typeof showResolveErrorV23==='function')showResolveErrorV23(error,'Timeline');$('timelineExportStatusV33').textContent=error.message||String(error)}}
async function loadResolveDebugV39(){if(!resolveHandoffIdV33)return;const report=await api(`/resolve-handoffs/${resolveHandoffIdV33}/diagnostics`);$('resolveDebugTextV39').value=JSON.stringify(report,null,2)}
$('copyResolveDebugV39').onclick=async()=>{try{await loadResolveDebugV39();await navigator.clipboard.writeText($('resolveDebugTextV39').value);$('copyResolveDebugV39').textContent='DIAGNOSTICA COPIATA'}catch(error){$('resolveDebugTextV39').select();$('copyResolveDebugV39').textContent='SELEZIONATA · PREMI CTRL+C'}};
$('sendResolvePackageV33').onclick=prepareResolveHandoffV33;$('exportTimelineXmlV33').onclick=()=>legacyTimelineExportV33('/exports/broll-timeline.xml','broll-timeline.xml');$('exportTimelineDraV33').onclick=()=>legacyTimelineExportV33('/resolve/broll-timeline.dra','broll-timeline.dra.zip');$('openTimelineResolveV33').onclick=()=>legacyTimelineExportV33('/resolve/broll-timeline',null);
document.querySelector('.genericCoverageV33').ontoggle=e=>{if(e.target.open&&!genericCoverageV33.items.length)loadGenericCoverageV33(false)};
$('loadPlaceCoverageV35').onclick=()=>loadGenericCoverageV33(true,'places');
$('loadGenericCoverageV33').onclick=()=>loadGenericCoverageV33(true);
setInterval(pollResolveBridgeLiveV34,2000);pollResolveBridgeLiveV34();

let resolveRestoreProjectV39=null;
async function restoreResolveDeliveryV39(){if(!state.pid||resolvePreparingV37||resolveRestoreProjectV39===state.pid)return;resolveRestoreProjectV39=state.pid;clearInterval(resolveHandoffPollV33);resolveHandoffIdV33=null;try{const row=await api(`/projects/${state.pid}/resolve-handoffs/latest`);if(!row.package_id||row.status==='discarded')return;resolveHandoffIdV33=row.package_id;resolveDeliveryStartedV37=Date.now();await pollResolveHandoffV33();if(!['failed','completed'].includes(row.status))resolveHandoffPollV33=setInterval(pollResolveHandoffV33,1000)}catch(_){resolveRestoreProjectV39=null}}
const hydrateTimelineBaseV33=hydrate;hydrate=async function(){const value=await hydrateTimelineBaseV33();syncTimelineExportV33();await restoreResolveDeliveryV39();return value};syncTimelineExportV33();
'''

