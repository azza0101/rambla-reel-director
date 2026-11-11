"""Confirmed RAMBLA to Resolve handoff panel."""

PANEL = r'''
<section class="panel genericCoverageMicroV34" data-workflow-step-v42="8">
  <details class="genericCoverageV33"><summary><strong>8 · Coperture generiche</strong><small>Video aggiuntivi e ricerca personalizzata</small></summary>
    <h3>Coperture generiche</h3><button id="loadGenericCoverageV33" type="button">CERCA VIDEO GENERICI</button><div id="genericCoverageCardsV33" class="genericCoverageCardsV33"></div>
    <h3>Coperture luogo</h3><button id="loadPlaceCoverageV35" type="button">CERCA VIDEO DEI LUOGHI</button><div id="placeCoverageCardsV138" class="genericCoverageCardsV33"></div>
    <div id="customCoverageV138"><h3>CUSTOM B-ROLL</h3><form id="customSearchV138" class="manualQuery"><input id="customQueryV138" aria-label="Cerca B-roll personalizzato" maxlength="180" placeholder="Cerca un soggetto, es. passaporto o Sri Lanka"><button type="submit">CERCA SU PEXELS ED ENVATO</button></form>
    <h4>PEXELS</h4><div id="customPexelsCardsV138" class="genericCoverageCardsV33"></div>
    <h4>ENVATO ELEMENTS</h4><div id="customEnvatoCardsV138" class="genericCoverageCardsV33"></div></div>
    <p id="genericCoverageStatusV33" class="muted" role="status"></p>
  </details>
</section>
<section class="panel timelineExportV33" id="timelineExportV33" data-workflow-step-v42="9">
  <div class="top"><div><h2>9 · Export timeline <span id="timelineExportCompleteV28" class="stepStatusV12" hidden></span> <span id="resolveBridgeLiveV34" class="resolveBridgeLiveV34 off">BRIDGE OFFLINE</span></h2>
  <p class="muted">Prepara sottotitoli, parole evidenziate e B-roll. Resolve li applica soltanto dopo la conferma nel bridge.</p></div></div>
  <div class="resolveExportSelectionV133" id="resolveExportSelectionV133">
    <div class="resolveExportSelectionTitleV133"><strong>Componenti da esportare</strong><span>✓ Seleziona le componenti da includere</span></div>
    <div id="resolveComponentsV71" class="resolveExportComponentGridV133"></div>
    <p id="resolveComponentsReasonV71" class="muted"></p>
  </div>
  <p id="resolveOriginalInfoV129" class="muted" style="margin:8px 0 0" hidden>Video originale con audio, senza AutoCut. Nel bridge puoi scegliere se applicare alla timeline attiva oppure creare una nuova timeline.</p>
  <button id="sendResolvePackageV33" class="primary resolvePrimaryV33">INVIA A RESOLVE</button>
  <label><input type="checkbox" id="includeOfflineDra"> Includi progetto Resolve DRA nello ZIP · senza Resolve</label>
  <small class="muted">Titoli KURA modificabili: sul computer di destinazione installa il preset incluso nello ZIP e il font Montserrat.</small>
  <button id="exportMediaPackV125" class="ghost" type="button" style="margin-top:8px;width:100%">ESPORTA ZIP · SENZA BRIDGE</button>
  <div id="resolveDeliveryV33" class="resolveDeliveryV33" hidden><div id="resolveDeliveryCheckV33" class="resolveDeliveryCheckV33" hidden>✓</div><strong id="resolveDeliveryTitleV33">Preparazione pacchetto Resolve…</strong><span id="resolveDeliverySummaryV33"></span><div id="resolveDeliveryProgressV33" class="resolveDeliveryProgressBarV34"><i></i></div><b id="resolveDeliveryPercentV37">0%</b><small id="resolveDeliveryDetailV33"></small><div id="resolveCurrentMediaV136" class="resolveCurrentMediaV136" hidden><strong id="resolveCurrentMediaTitleV136"></strong><div id="resolveCurrentMediaBarV136" class="resolveCurrentMediaBarV136"><i></i></div><small id="resolveCurrentMediaDetailV136"></small></div></div>
  <button id="reconnectResolveV145" class="ghost" type="button" hidden>↻ RICOLLEGA BRIDGE</button><small id="reconnectResolveMessageV145" role="status" hidden></small>
  <button id="stopResolvePrepareV139" type="button" hidden>■ STOP INVIO</button>
  <dialog id="resolveStopDialogV139" class="resolveDialogV139"><h3>Interrompere l’invio?</h3><p>Scegli cosa fare con i file scaricati durante questo invio. I file già presenti e il progetto restano al sicuro.</p><div class="row"><button id="resolveStopKeepV139" type="button">STOP · MANTIENI I FILE</button><button id="resolveStopDiscardV139" type="button">STOP · ELIMINA I NUOVI FILE</button><button id="resolveStopBackV139" type="button">ANNULLA</button></div></dialog>
  <dialog id="resolveIssueDialogV139" class="resolveDialogV139"><h3>Problema con una copertura</h3><p id="resolveIssueTitleV139"></p><p id="resolveIssueDetailV139"></p><p>Apri la pagina, risolvi il problema e premi Riprova; oppure ignora questa clip.</p><p id="resolveIssueMessageV139" role="status"></p><div class="row"><button id="resolveIssueOpenV139" type="button">APRI PAGINA</button><button id="resolveIssueRetryV139" type="button">RIPROVA</button><button id="resolveIssueIgnoreV139" type="button">IGNORA QUESTA CLIP</button><button id="resolveIssueIgnoreAllV139" type="button">IGNORA TUTTI GLI ERRORI</button><button id="resolveIssueStopV139" type="button">STOP INVIO</button></div></dialog>
  <dialog id="zipIssueDialogV164" class="resolveDialogV139"><h3>Alcune coperture non sono disponibili</h3><p>I video sotto 720p non vengono inclusi. Controlla le clip, riprova oppure crea lo ZIP senza quelle indicate.</p><ul id="zipIssueListV164" style="max-height:35vh;overflow:auto"></ul><div class="row"><button id="zipIssueRetryV164" type="button">RIPROVA</button><button id="zipIssueContinueV164" type="button">CONTINUA SENZA QUESTE CLIP</button><button id="zipIssueCancelV164" type="button">ANNULLA ESPORTAZIONE</button></div></dialog>
  <div id="resolveMediaIssuesV48" class="resolveMediaIssuesV48" hidden></div>
  <details id="resolveDebugV39" hidden><summary>Diagnostica Resolve</summary><button id="copyResolveDebugV39">COPIA DIAGNOSTICA</button><textarea id="resolveDebugTextV39" readonly aria-label="Diagnostica Resolve" style="width:100%;min-height:150px;margin-top:8px"></textarea></details><details class="legacyExportsV33"><summary>Export file e strumenti precedenti</summary><div class="timelineExportActionsV33"><button id="exportTimelineXmlV33">ESPORTA XML</button><button id="exportTimelineDraV33">ESPORTA DRA</button><button id="openTimelineResolveV33">CREA SUBITO IN RESOLVE · TEMP</button></div></details>
  <p id="timelineExportStatusV33" class="muted" role="status">Puoi inviare anche soltanto subs o parole evidenziate.</p>
</section>
'''

CSS = r'''<style id="timeline-export-v33-style">
.genericCoverageV33{margin:12px 0}.genericCoverageCardsV33{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px;margin-top:10px}.genericCardV33{border:2px solid #454e77;border-radius:12px;overflow:hidden;background:#191e38;cursor:pointer}.genericCardV33.selected{border-color:#d7bd84;box-shadow:0 0 0 2px #d7bd8444}.genericCardV33 video,.genericCardV33 img{display:block;width:100%;aspect-ratio:16/9;object-fit:cover;background:#0b0e1d}.genericCardV33 div{padding:6px;font-size:11px}.genericCardV33 b{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.genericCoverageMicroV34{margin-top:16px;padding:13px 16px;background:linear-gradient(145deg,#312c24,#25243a);border:1px solid #8c7447}.genericCoverageMicroV34 summary{display:flex;align-items:center;gap:10px;color:#f0d59b;cursor:pointer}.genericCoverageMicroV34 summary small{color:#bbb6ad;font-weight:400}.genericCoverageMicroV34 .genericCoverageV33{margin:0}.genericCoverageMicroV34 button{margin-top:12px;border-color:#b89555;color:#f0d59b}
.timelineExportV33{margin-top:16px;background:linear-gradient(145deg,#252b4c,#1d223e);border-color:#58658f}.resolvePrimaryV33{width:100%;min-height:52px;font-size:15px;margin-top:12px}.resolveDeliveryV33{display:grid;grid-template-columns:auto 1fr;gap:7px 12px;align-items:center;margin-top:12px;padding:16px;border:1px solid #778548;border-radius:12px;background:#18263a}.resolveDeliveryV33 strong,.resolveDeliveryV33 span,.resolveDeliveryV33 progress,.resolveDeliveryV33 small{grid-column:2}.resolveDeliveryV33 strong{color:#d8ff5b;font-size:15px}.resolveDeliveryV33 progress{width:100%;height:10px}.resolveDeliveryV33.receivedV33{border-color:#48a967;background:#142d22}.resolveDeliveryCheckV33{grid-row:1/5;align-self:center;width:58px;height:58px;border-radius:50%;display:grid;place-items:center;background:#50c878;color:#08160d;font-size:38px;font-weight:950;box-shadow:0 0 24px #50c87855}.resolveDeliveryCheckV33[hidden]{display:none}.legacyExportsV33{margin-top:12px}.timelineExportActionsV33{display:flex;gap:9px;flex-wrap:wrap;margin-top:9px}.timelineExportV33.busyV33{border-color:#c69b39}.timelineExportV33.errorV33{border-color:#a54d58}@media(max-width:700px){.timelineExportActionsV33 button{flex:1 1 100%}}
.resolveBridgeLiveV34{display:inline-block;margin-left:9px;padding:4px 8px;border-radius:999px;font-size:10px;vertical-align:middle;color:#d8ff5b;background:#183727;border:1px solid #4e9d68}.resolveBridgeLiveV34.off{color:#ff9d9d;background:#3a202b;border-color:#9f5263}
.resolveDeliveryV33[hidden]{display:none}.resolveDeliveryProgressBarV34{grid-column:1/-1;width:100%;min-width:0;height:14px;border-radius:999px;background:#e5e7ee;overflow:hidden}.resolveDeliveryProgressBarV34 i{display:block;width:var(--p,0%);height:100%;background:#5576e8;transition:width .2s linear}
.resolveExportSelectionV133{margin-top:16px;padding:14px;border:1px solid #6875ac;border-radius:12px;background:#141b33}.resolveExportSelectionTitleV133{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:6px;margin-bottom:10px;color:#f1f4ff}.resolveExportSelectionTitleV133 span{font-size:11px;color:#acb6d4}.resolveExportComponentGridV133{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:7px}.resolveExportComponentGridV133 label{display:flex;align-items:center;gap:9px;padding:10px 12px;border:1px solid #4d597e;border-radius:9px;background:#232c48;cursor:pointer;color:#f7f9ff;font-size:13px}.resolveExportComponentGridV133 label:has(input:checked){border-color:#b9d971;background:#273d30}.resolveExportComponentGridV133 label:has(input:disabled){opacity:.52;cursor:not-allowed}.resolveExportComponentGridV133 label input{accent-color:#d8ff5b;min-width:18px;width:18px;height:18px}.resolveExportComponentGridV133 label small{margin-left:auto;color:#cfdbff;font-weight:700;white-space:nowrap}.resolveExportSelectionV133 .muted{display:block;margin:9px 0 0;font-size:12px}.resolvePrimaryV33:disabled{opacity:.6;cursor:not-allowed}
.resolveMediaIssuesV48{margin-top:12px;padding:12px;border:1px solid #c69b39;border-radius:12px;background:#2a2519}.resolveMediaIssuesV48[hidden]{display:none}.resolveMediaIssueV48{display:grid;grid-template-columns:1fr auto;gap:5px 12px;padding:9px 0;border-bottom:1px solid #ffffff1b}.resolveMediaIssueV48:last-of-type{border-bottom:0}.resolveMediaIssueV48 span{grid-column:1}.resolveMediaIssueV48 a{grid-column:2;grid-row:1/3;align-self:center;padding:9px 12px;border:1px solid #d8ff5b;border-radius:8px;color:#d8ff5b;font-weight:800;text-decoration:none}.resolveMediaIssuesV48>button{margin-top:10px}
 .resolveCurrentMediaV136{grid-column:1/-1;margin-top:4px;padding:10px 12px;border:1px solid #596d84;border-radius:9px;background:#101d2b}.resolveCurrentMediaV136[hidden]{display:none}.resolveCurrentMediaV136 strong,.resolveCurrentMediaV136 small{display:block}.resolveCurrentMediaV136 strong{color:#e7f8f0;font-size:12px}.resolveCurrentMediaV136 small{margin-top:5px;color:#b9cbd8}.resolveCurrentMediaBarV136{height:7px;margin-top:7px;background:#314352;border-radius:9px;overflow:hidden}.resolveCurrentMediaBarV136 i{display:block;height:100%;width:var(--media-p,0%);background:#72d9b4;transition:width .2s}.resolveCurrentMediaBarV136.indeterminate i{width:35%;animation:resolveMediaPulseV136 1.4s ease-in-out infinite}@keyframes resolveMediaPulseV136{from{transform:translateX(-100%)}to{transform:translateX(300%)}}@media(prefers-reduced-motion:reduce){.resolveCurrentMediaBarV136.indeterminate i{animation:none;width:100%;opacity:.5}}
.resolveDialogV139{background:#151d29;color:#eef7f5;border:1px solid #4d806e;border-radius:14px;padding:22px;max-width:560px;width:min(90vw,560px)}.resolveDialogV139::backdrop{background:#000a}.resolveDialogV139 .row{display:flex;flex-wrap:wrap;gap:8px}.resolveDialogV139 p{line-height:1.5}#stopResolvePrepareV139{margin-top:8px;border-color:#df7880;color:#ffd1d4}#stopResolvePrepareV139[hidden]{display:none}
</style>'''

JS = r'''
const resolveComponentLabelsV71={video:'Video · CUT nativo',source_video:'Video originale caricato + audio · SENZA AUTO-CUT (nuova timeline)',subtitles:'Sottotitoli',highlights:'Parole evidenziate',broll:'B-roll e immagini',social:'Clip social',generic:'Coperture generiche'};
let resolveComponentsV71=null;
async function loadResolveComponentsV71(){
 if(!state.pid)return;
 const pid=state.pid,options=await api(`/projects/${pid}/export-options`);
 if(state.pid!==pid)return;
 const list=$('resolveComponentsV71');
 const available=(key)=>!!(key==='video'?options.video_available:options.component_availability?.[key]!==false);
 const effective=Object.fromEntries(Object.keys(resolveComponentLabelsV71).map(key=>[
   key,!!options.components[key]&&available(key)&&Number(options.counts?.[key]||0)>0
 ]));
 resolveComponentsV71=effective;
 $('resolveOriginalInfoV129').hidden=!effective.source_video;
 list.innerHTML=Object.entries(resolveComponentLabelsV71).map(([key,label])=>{
   const count=Number(options.counts?.[key]||0);
   const usable=available(key)&&count>0;
   return `<label><input type="checkbox" data-component="${key}" ${effective[key]?'checked':''} ${usable?'':'disabled'}><span>${label}</span><small>${count}</small></label>`;
 }).join('');
 $('resolveComponentsReasonV71').textContent=options.video_reason||'';
 for(const input of list.querySelectorAll('input'))input.onchange=async()=>{
   const next=Object.fromEntries([...list.querySelectorAll('input')].map(x=>[x.dataset.component,x.checked]));
   if(input.checked&&input.dataset.component==='source_video')next.video=false;
   if(input.checked&&input.dataset.component==='video')next.source_video=false;
   for(const x of list.querySelectorAll('input'))x.checked=next[x.dataset.component];
   const previous={...resolveComponentsV71};
   resolveComponentsV71=next;
   $('resolveOriginalInfoV129').hidden=!next.source_video;
   try{
     await api(`/projects/${pid}/export-options`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(next)});
     $('resolveComponentsReasonV71').textContent=options.video_reason||'';
   }catch(error){
     resolveComponentsV71=previous;
     for(const x of list.querySelectorAll('input'))x.checked=previous[x.dataset.component];
     $('resolveOriginalInfoV129').hidden=!previous.source_video;
     $('resolveComponentsReasonV71').textContent=error.message||String(error);
   }
 };
}

let resolveHandoffIdV33=null,resolveHandoffPollV33=null,resolvePreparingV37=false,resolveDeliveryStartedV37=0;
let resolvePrepareJobV139=null,resolveCurrentIssueV139=null;
let resolveDeliveryTargetCheckV126=0,resolveDeliveryMismatchV126='';
let genericCoverageV33={items:[],selected:[]};
let ignoredCoverageIdsV123=new Set();
let ignoredCoverageProjectV125=null;

function renderResolveMediaIssuesV48(items=[]){
 const box=$('resolveMediaIssuesV48');
 const remaining=(items||[]).filter(row=>!ignoredCoverageIdsV123.has(String(row.asset_id||'')));
 box.hidden=!remaining.length;
 if(!remaining.length){box.innerHTML='';return}
 box.innerHTML=`<strong>${remaining.length} coperture non disponibili · ignora solo quelle problematiche</strong>${remaining.map(row=>`<article class="resolveMediaIssueV48"><b>${esc(row.beat_id)} · ${esc(row.title||row.provider)}</b><span>${esc(row.message)}</span><div class="row">${row.source_page?`<a href="${esc(row.source_page)}" target="_blank" rel="noopener">${row.reason==='verification_required'?'APRI FONTE E VERIFICA':'APRI FONTE'}</a>`:''}<button type="button" data-ignore-coverage="${esc(String(row.asset_id||''))}">IGNORA QUESTA COPERTURA</button></div></article>`).join('')}<button id="ignoreAllResolveMediaV48" type="button">IGNORA TUTTE LE COPERTURE NON DISPONIBILI</button> <button id="retryResolveMediaV48" type="button">RIPROVA DOWNLOAD</button>`;
 box.querySelector('#retryResolveMediaV48').onclick=()=>prepareResolveHandoffV33();
 box.querySelector('#ignoreAllResolveMediaV48').onclick=async()=>{
   if(resolvePreparingV37)return;
   remaining.forEach(row=>{if(row.asset_id)ignoredCoverageIdsV123.add(String(row.asset_id))});
   $('timelineExportStatusV33').textContent='Ignoro le '+remaining.length+' coperture non disponibili per questo invio.';
   await prepareResolveHandoffV33(true);
 };
 box.querySelectorAll('[data-ignore-coverage]').forEach(button=>button.onclick=async()=>{
   if(resolvePreparingV37)return;
   const id=button.dataset.ignoreCoverage;
   if(!id)return;
   ignoredCoverageIdsV123.add(id);
   button.closest('.resolveMediaIssueV48')?.remove();
   $('timelineExportStatusV33').textContent='Ignorata solo questa copertura ('+ignoredCoverageIdsV123.size+'). Mantengo le altre clip e le selezioni originali.';
   await prepareResolveHandoffV33(true);
 });
}

async function pollResolveBridgeLiveV34(){try{const row=await api('/resolve-bridge/session'),badge=$('resolveBridgeLiveV34');badge.textContent=row.connected?'BRIDGE CONNECTED':'BRIDGE OFFLINE';badge.classList.toggle('off',!row.connected)}catch(_){const badge=$('resolveBridgeLiveV34');badge.textContent='BRIDGE OFFLINE';badge.classList.add('off')}}
function renderGenericCoverageV33(){
 const chosen=new Set(genericCoverageV33.selected||[]),items=genericCoverageV33.items||[];
 const groups=[['genericCoverageCardsV33',r=>(r.coverage_group||'topic')==='topic'],['placeCoverageCardsV138',r=>r.coverage_group==='places'],['customPexelsCardsV138',r=>(r.coverage_group==='custom'||(r.coverage_groups||[]).includes('custom'))&&r.provider==='pexels'],['customEnvatoCardsV138',r=>(r.coverage_group==='custom'||(r.coverage_groups||[]).includes('custom'))&&r.provider==='envato']];
 for(const [id,filter] of groups){
  const container=$(id);container.innerHTML=items.filter(filter).map(row=>`<article class="genericCardV33 ${chosen.has(String(row.provider_id))?'selected':''}" data-generic-id="${esc(String(row.provider_id))}">${row.provider==='envato'?`<img loading="lazy" src="${esc(row.preview_url||'')}" alt="">`:`<video muted loop playsinline preload="none" poster="${esc(row.preview_url||'')}" src="${esc(row.selected_rendition_url||'')}"></video>`}<div><b>${esc(row.title||row.query||'Video')}</b><small>${row.provider==='envato'?'Envato':'Pexels'}${row.duration?' · '+Math.round(row.duration)+'s':''}</small></div></article>`).join('');
  container.querySelectorAll('[data-generic-id]').forEach(card=>{
   card.onclick=async()=>{const id=card.dataset.genericId,set=new Set(genericCoverageV33.selected||[]),wasEmpty=set.size===0;set.has(id)?set.delete(id):set.add(id);genericCoverageV33.selected=[...set];renderGenericCoverageV33();
    try{await api(`/projects/${state.pid}/generic-coverage/selection`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider_ids:genericCoverageV33.selected})});
     if(wasEmpty&&set.size&&resolveComponentsV71&&!resolveComponentsV71.generic){const next={...resolveComponentsV71,generic:true};await api(`/projects/${state.pid}/export-options`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(next)});resolveComponentsV71=next}
     await loadResolveComponentsV71();$('genericCoverageStatusV33').textContent=`${set.size} coperture selezionate · export aggiornato`;
    }catch(e){$('genericCoverageStatusV33').textContent='Salvataggio non riuscito: '+(e.message||String(e));await loadGenericCoverageV33(false)}
   };
   const video=card.querySelector('video');if(video){card.onmouseenter=()=>video.play().catch(()=>{});card.onmouseleave=()=>{video.pause();video.currentTime=0}}
  });
 }
}
async function loadGenericCoverageV33(refresh=false,scope='topic',manualQuery=''){
 const pid=state.pid;if(!pid)return;const buttons=[$('loadGenericCoverageV33'),$('loadPlaceCoverageV35'),...document.querySelectorAll('#customSearchV138 button')];buttons.forEach(b=>b.disabled=true);
 $('genericCoverageStatusV33').textContent=manualQuery?'Cerco su Pexels ed Envato: '+manualQuery+'…':scope==='places'?'Cerco video dei luoghi citati nel testo…':'Cerco video sul tema generale…';
 try{const params=new URLSearchParams({refresh:String(refresh),scope});if(manualQuery)params.set('manual_query',manualQuery);const result=await api(`/projects/${pid}/generic-coverage?${params}`);if(state.pid!==pid)return;genericCoverageV33=result;renderGenericCoverageV33();$('genericCoverageStatusV33').textContent=`${result.items.length} video disponibili · selezionati ${result.selected.length}. ${(result.errors||[]).join(' · ')}`;await loadResolveComponentsV71()}
 catch(error){if(state.pid===pid)$('genericCoverageStatusV33').textContent=error.message||String(error)}finally{buttons.forEach(b=>b.disabled=false)}
}

function syncTimelineExportV33(){const disabled=!state.pid||!!state.run||resolvePreparingV37;for(const id of ['sendResolvePackageV33','exportTimelineXmlV33','exportTimelineDraV33','openTimelineResolveV33'])$(id).disabled=disabled}
function summaryResolveHandoffV33(s={}){return `${s.original_video?'Video originale senza AutoCut · ':''}${s.native_cut?`CUT nativo · ${s.cut_count} tagli · ${s.fps} fps · ${s.width}×${s.height} · `:''}${s.broll_count||0} B-roll · ${s.subtitle_count||0} subs · ${s.title_count||0} frasi${s.generic_broll_count?` · ${s.generic_broll_count} generiche`:''}${s.unavailable_count?` · ${s.unavailable_count} non disponibili`:''}`}
function setResolveDeliveryProgressV33(value){const percent=Math.max(0,Math.min(100,Number(value)||0)),bar=$('resolveDeliveryProgressV33');bar.style.setProperty('--p',`${percent}%`);bar.setAttribute('role','progressbar');bar.setAttribute('aria-valuemin','0');bar.setAttribute('aria-valuemax','100');bar.setAttribute('aria-valuenow',String(percent));$('resolveDeliveryPercentV37').textContent=`${percent}%`}
$('reconnectResolveV145').onclick=async()=>{
 if(!resolveHandoffIdV33)return;
 const button=$('reconnectResolveV145'),message=$('reconnectResolveMessageV145'),id=resolveHandoffIdV33;
 button.disabled=true;message.hidden=false;message.textContent='Controllo bridge, Resolve e pacchetto…';
 try{
  await api(`/resolve-handoffs/${id}/reconnect`,{method:'POST'});
  message.textContent='Bridge contattato. Attendo la ricezione del pacchetto…';
  await new Promise(resolve=>setTimeout(resolve,3000));
  const row=await api(`/resolve-handoffs/${id}/status`);
  message.textContent=row.bridge_received_at?'✓ Pacchetto ricevuto: premi APPLICA nel bridge.':'Bridge collegato, ma non ha ancora confermato. Apri il bridge e controlla Diagnostica Resolve.';
  await pollResolveHandoffV33();
 }catch(error){message.textContent='Collegamento non riuscito: '+(error.message||String(error));$('resolveDebugV39').hidden=false;try{await loadResolveDebugV39()}catch(_){}$('resolveDebugV39').open=true}
 finally{button.disabled=false}
};
async function pollResolveHandoffV33(){
 if(!resolveHandoffIdV33)return;
 try{
  const row=await api(`/resolve-handoffs/${resolveHandoffIdV33}/status`),received=!!row.bridge_received_at,done=row.status==='completed',applying=row.status==='applying',failed=row.status==='failed';
  $('reconnectResolveV145').hidden=row.status!=='pending';
  const box=$('resolveDeliveryV33');box.hidden=false;box.classList.toggle('receivedV33',(received||done)&&!failed);$('resolveDeliveryCheckV33').hidden=!(received||done)||failed;
  $('resolveDeliverySummaryV33').textContent=summaryResolveHandoffV33(row.summary);
  setResolveDeliveryProgressV33((applying||failed)?row.progress?.percent:(received||done?100:90));$('resolveDebugV39').hidden=false;
  $('resolveDeliveryTitleV33').textContent=failed?'OPERAZIONE RESOLVE NON RIUSCITA':done?`TIMELINE CREATA · ${row.result?.timeline_name||''}`:applying?'APPLICAZIONE IN RESOLVE':received?'ESPORTATO SU RESOLVE · RICEVUTO DAL BRIDGE':'PACCHETTO PRONTO · ATTESA RICEZIONE';
  if(failed){$('resolveDeliveryDetailV33').textContent=row.error||'Controlla il bridge';await loadResolveDebugV39();$('resolveDebugV39').open=true;}
  else if(done)$('resolveDeliveryDetailV33').textContent='Operazione completata.';
  else if(applying)$('resolveDeliveryDetailV33').textContent=row.progress?.message||'Applicazione in corso';
  else if(received)$('resolveDeliveryDetailV33').textContent='Premi APPLICA nel bridge quando vuoi creare la timeline.';
  else {
    const live=await api('/resolve-bridge/session'),seconds=Math.floor((Date.now()-resolveDeliveryStartedV37)/1000);
    if(seconds>8 && live.connected && Date.now()-resolveDeliveryTargetCheckV126>8000){
      resolveDeliveryTargetCheckV126=Date.now();
      try{
        const target=await api('/resolve-bridge/status');
        resolveDeliveryMismatchV126=(target.connected&&row.resolve_project&&target.project!==row.resolve_project)
          ?'Il pacchetto si riferisce a un altro progetto Resolve. Premi INVIA A RESOLVE per collegarlo al progetto attivo.':'';
      }catch(_){resolveDeliveryMismatchV126='';}
    }
    const changed=live.bridge_session_id!==row.bridge_session_id;
    $('resolveDeliveryDetailV33').textContent=!live.connected?'Preparazione terminata. Bridge offline: aprilo in Resolve, poi ripeti INVIA.':
      changed?'Il bridge è stato riaperto: ripeti INVIA per la nuova sessione.':
      resolveDeliveryMismatchV126||`Attendo conferma dal bridge da ${seconds}s. ${seconds>15?'Nessuna conferma ricevuta: controlla DIAGNOSTICA RESOLVE e ripeti INVIA.':'Nessuna modifica alla timeline fino ad APPLICA.'}`;
    if(seconds>20)$('resolveDeliveryTitleV33').textContent='CONSEGNA NON CONFERMATA · VERIFICA BRIDGE';
  }
  if(done||failed)clearInterval(resolveHandoffPollV33);
 }catch(error){$('resolveDeliveryDetailV33').textContent='Non riesco a verificare la consegna: '+(error.message||String(error))}
}
function renderCurrentMediaV136(media){
 const box=$('resolveCurrentMediaV136'),bar=$('resolveCurrentMediaBarV136');
 box.hidden=!media;if(!media)return;
 $('resolveCurrentMediaTitleV136').textContent=`${media.provider||'Media'} · ${media.index||1}/${media.count||1} · ${media.title||'File'}`;
 const total=Number(media.total)||0,received=Number(media.received)||0,known=total>0;
 bar.classList.toggle('indeterminate',!known);bar.style.setProperty('--media-p',`${known?Math.max(0,Math.min(100,100*received/total)):0}%`);
 const seconds=Math.max(0,Math.floor(Date.now()/1000-(Number(media.started_at)||Date.now()/1000)));
 const amount=known?`${(received/1048576).toFixed(1)} / ${(total/1048576).toFixed(1)} MB · ${Math.floor(100*received/total)}%`:'Dimensione non disponibile';
 $('resolveCurrentMediaDetailV136').textContent=`${media.phase||'Preparazione'} · ${amount} · ${seconds}s trascorsi`;
}
function showResolveIssueV139(issue){
 resolveCurrentIssueV139=issue;
 const dialog=$('resolveIssueDialogV139');
 $('resolveIssueTitleV139').textContent=(issue.provider||'Video')+' · '+(issue.title||issue.asset_id||'');
 $('resolveIssueDetailV139').textContent=issue.message||'Download non riuscito.';
 $('resolveIssueOpenV139').disabled=!issue.source_page;
 if(!dialog.open&&!$('resolveStopDialogV139').open)dialog.showModal();
}
$('resolveIssueDialogV139').addEventListener('cancel',event=>event.preventDefault());
$('resolveStopDialogV139').addEventListener('cancel',event=>{event.preventDefault();$('resolveStopDialogV139').close()});
$('stopResolvePrepareV139').onclick=()=>{if(resolvePrepareJobV139)$('resolveStopDialogV139').showModal()};
$('resolveIssueStopV139').onclick=()=>{$('resolveIssueDialogV139').close();$('resolveStopDialogV139').showModal()};
$('resolveStopBackV139').onclick=()=>$('resolveStopDialogV139').close();
async function stopResolvePrepareV139(keep){
 if(!resolvePrepareJobV139)return;
 $('resolveStopDialogV139').close();$('stopResolvePrepareV139').disabled=true;
 $('resolveDeliveryDetailV33').textContent='Interruzione in corso…';
 try{await api(`/resolve-preparation/${resolvePrepareJobV139}/cancel?keep_cached=${keep}`,{method:'POST'})}
 catch(e){$('resolveDeliveryDetailV33').textContent='Impossibile interrompere: '+(e.message||e);$('stopResolvePrepareV139').disabled=false}
}
$('resolveStopKeepV139').onclick=()=>stopResolvePrepareV139(true);
$('resolveStopDiscardV139').onclick=()=>stopResolvePrepareV139(false);
async function decideResolveIssueV139(choice){
 if(!resolvePrepareJobV139)return;
 try{await api(`/resolve-preparation/${resolvePrepareJobV139}/decision?choice=${choice}`,{method:'POST'});$('resolveIssueDialogV139').close();$('resolveIssueMessageV139').textContent=''}
 catch(e){$('resolveIssueMessageV139').textContent=e.message||String(e)}
}
$('resolveIssueRetryV139').onclick=()=>decideResolveIssueV139('retry');
$('resolveIssueIgnoreV139').onclick=()=>decideResolveIssueV139('ignore');
$('resolveIssueIgnoreAllV139').onclick=()=>decideResolveIssueV139('ignore_all');
$('resolveIssueOpenV139').onclick=async()=>{
 if(!resolvePrepareJobV139)return;
 if(!['envato','tiktok','youtube','youtube_shorts'].includes(resolveCurrentIssueV139?.provider)){
  try{const url=new URL(resolveCurrentIssueV139?.source_page||'');if(url.protocol!=='https:')throw Error('Pagina non valida');const opened=window.open(url.href,'_blank','noopener');$('resolveIssueMessageV139').textContent='Pagina aperta. Dopo aver risolto, torna qui e premi RIPROVA.'}
  catch(e){$('resolveIssueMessageV139').textContent=e.message||String(e)}return;
 }
 $('resolveIssueMessageV139').textContent='Apro la pagina…';
 try{const r=await api(`/resolve-preparation/${resolvePrepareJobV139}/open-source`,{method:'POST'});if(r.status==='external')window.open(r.url,'_blank','noopener');$('resolveIssueMessageV139').textContent='Pagina aperta. Dopo aver risolto, torna qui e premi RIPROVA.'}
 catch(e){$('resolveIssueMessageV139').textContent=e.message||String(e)}
};
async function prepareResolveHandoffV33(preserveIssues=false){
 if(resolvePreparingV37)return;
 if(ignoredCoverageProjectV125!==state.pid){ignoredCoverageIdsV123.clear();ignoredCoverageProjectV125=state.pid;}
 resolvePreparingV37=true;clearInterval(resolveHandoffPollV33);resolveHandoffIdV33=null;resolveDeliveryTargetCheckV126=0;resolveDeliveryMismatchV126='';
 const panel=$('timelineExportV33'),box=$('resolveDeliveryV33');syncTimelineExportV33();panel.classList.add('busyV33');panel.classList.remove('errorV33');box.hidden=false;box.classList.remove('receivedV33');$('resolveDeliveryCheckV33').hidden=true;if(!preserveIssues)renderResolveMediaIssuesV48([]);
 renderCurrentMediaV136(null);$('resolveDeliveryTitleV33').textContent='PREPARAZIONE PER RESOLVE';$('resolveDeliverySummaryV33').textContent='Controllo le selezioni salvate';setResolveDeliveryProgressV33(0);$('resolveDeliveryDetailV33').textContent='Avvio…';$('timelineExportStatusV33').textContent='';if(!preserveIssues)box.scrollIntoView({block:'nearest',behavior:'smooth'});
 const projectId=state.pid;
 try{
  $('resolveDeliverySummaryV33').textContent='Apro il bridge Resolve…';
  await api('/resolve-bridge/open-window',{method:'POST'});
  let bridge=null;
  for(let attempt=0;attempt<24;attempt++){
   bridge=await api('/resolve-bridge/session');
   if(bridge.connected)break;
   await new Promise(resolve=>setTimeout(resolve,500));
  }
  if(!bridge?.connected)throw Error('Il bridge non si è collegato a questa finestra di RMBL. Aprilo da Resolve e verifica Diagnostica Resolve, poi riprova.');
  $('resolveDeliverySummaryV33').textContent='Bridge collegato · preparo le selezioni';
  const params=new URLSearchParams();
   params.set('interactive','true');
   if(ignoredCoverageIdsV123.size)params.set('ignored',[...ignoredCoverageIdsV123].join(','));
   let job=await api(`/projects/${projectId}/resolve-preparation${params.size?'?'+params:''}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(resolveComponentsV71)});
  resolvePrepareJobV139=job.job_id;$('stopResolvePrepareV139').hidden=false;$('stopResolvePrepareV139').disabled=false;
  while(true){
   if(job.status==='waiting_user'&&job.issue)showResolveIssueV139(job.issue);
   if(job.status==='cancelled'){$('resolveDeliveryTitleV33').textContent='INVIO INTERROTTO';$('resolveDeliveryDetailV33').textContent=job.message;return}
   renderCurrentMediaV136(job.media);setResolveDeliveryProgressV33(job.percent);$('resolveDeliverySummaryV33').textContent=job.message;$('resolveDeliveryDetailV33').textContent=`Tempo trascorso: ${job.elapsed_seconds||0}s · avanzamento aggiornato dal server`;
   if(job.status==='failed')throw Error(job.message||job.error||'Preparazione non riuscita');
   if(job.status==='ready'){resolveHandoffIdV33=job.package.package_id;renderResolveMediaIssuesV48(job.package.media_issues||[]);break;}
   await new Promise(resolve=>setTimeout(resolve,500));job=await api(`/resolve-preparation/${job.job_id}`);
  }
  resolveDeliveryStartedV37=Date.now();resolveHandoffPollV33=setInterval(pollResolveHandoffV33,1000);await pollResolveHandoffV33();
 }catch(error){panel.classList.add('errorV33');$('resolveDeliveryTitleV33').textContent='INVIO NON RIUSCITO';$('resolveDeliveryDetailV33').textContent=error.message||String(error)}
 finally{resolvePrepareJobV139=null;$('stopResolvePrepareV139').hidden=true;if($('resolveIssueDialogV139').open)$('resolveIssueDialogV139').close();if($('resolveStopDialogV139').open)$('resolveStopDialogV139').close();renderCurrentMediaV136(null);resolvePreparingV37=false;panel.classList.remove('busyV33');syncTimelineExportV33()}
}
function showZipIssuesV164(issues){
 return new Promise(resolve=>{
  const dialog=$('zipIssueDialogV164'), list=$('zipIssueListV164');list.replaceChildren();
  for(const issue of issues){const li=document.createElement('li');li.textContent=(issue.title||issue.label||issue.asset_id||'Copertura')+' · '+(issue.message||issue.reason||'Non disponibile');list.append(li)}
  const finish=choice=>{if(dialog.open)dialog.close();resolve(choice)};
  $('zipIssueRetryV164').onclick=()=>finish('retry');$('zipIssueContinueV164').onclick=()=>finish('continue');$('zipIssueCancelV164').onclick=()=>finish('cancel');
  dialog.oncancel=event=>{event.preventDefault();finish('cancel')};dialog.showModal();
 });
}
async function exportMediaPackV125(){
 if(!state.pid||state.run)return;
 const button=$('exportMediaPackV125');button.disabled=true;
 const dra=$('includeOfflineDra').checked;
 $('timelineExportStatusV33').textContent=dra?'Preparo l’archivio DRA e i media selezionati. Resolve non è necessario.':'Controllo i media e preparo lo ZIP. Resolve non è necessario.';
 try{
   let acceptMissing=false,acceptedSignature='',response;
   for(;;){
     response=await fetch('/api/curation/projects/'+encodeURIComponent(state.pid)+'/exports/media-pack.zip?include_dra='+dra+'&accept_missing='+acceptMissing+'&accepted_signature='+encodeURIComponent(acceptedSignature),{
       method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(resolveComponentsV71)
     });
     if(response.status===409){
       const error=await response.json().catch(()=>({})),detail=error.detail||{};
       if(detail.code!=='media_issues')throw Error(typeof detail==='string'?detail:'Media Pack HTTP 409');
       const choice=await showZipIssuesV164(detail.issues||[]);
       if(choice==='cancel'){$('timelineExportStatusV33').textContent='Esportazione annullata. Le selezioni sono conservate.';return}
       acceptMissing=choice==='continue';acceptedSignature=acceptMissing?(detail.signature||''):'';$('timelineExportStatusV33').textContent='Preparo lo ZIP…';continue;
     }
     if(!response.ok){const error=await response.json().catch(()=>({}));throw Error(error.detail||'Media Pack HTTP '+response.status)}
     break;
   }
   const blob=await response.blob(),url=URL.createObjectURL(blob);
   const a=document.createElement('a');a.href=url;a.download=dra?'RMBL_DRA.zip':'RMBL_MediaPack.zip';document.body.append(a);a.click();a.remove();
   setTimeout(()=>URL.revokeObjectURL(url),60000);
   const missing=Number(response.headers.get('X-Rambla-Missing-Count')||0);
   $('timelineExportStatusV33').textContent=missing?`ZIP esportato senza ${missing} coperture. Apri 00_AVVISO_MEDIA_MANCANTI.txt per i dettagli.`:dra?'Archivio pronto. Estrai lo ZIP e in Resolve scegli Restore Project Archive sulla cartella .dra.':'Media Pack esportato. XML e SRT sono in 03_RESOLVE.';
 }catch(e){$('timelineExportStatusV33').textContent='Media Pack non riuscito: '+(e.message||e)}
 finally{button.disabled=false}
}
$('exportMediaPackV125').onclick=exportMediaPackV125;
async function legacyTimelineExportV33(path,download){try{const response=await fetch(`/api/curation/projects/${state.pid}${path}`,{method:path.startsWith('/exports/')?'GET':'POST'});if(!response.ok){const body=await response.json().catch(()=>({}));throw Error(body.detail||`HTTP ${response.status}`)}if(download){const blob=await response.blob(),a=document.createElement('a'),url=URL.createObjectURL(blob);a.href=url;a.download=download;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}else{const result=await response.json();$('timelineExportStatusV33').textContent=`Timeline creata · ${result.timeline_name||''}`}}catch(error){if(typeof showResolveErrorV23==='function')showResolveErrorV23(error,'Timeline');$('timelineExportStatusV33').textContent=error.message||String(error)}}
async function loadResolveDebugV39(){if(!resolveHandoffIdV33)return;const report=await api(`/resolve-handoffs/${resolveHandoffIdV33}/diagnostics`);$('resolveDebugTextV39').value=JSON.stringify(report,null,2)}
$('copyResolveDebugV39').onclick=async()=>{try{await loadResolveDebugV39();await navigator.clipboard.writeText($('resolveDebugTextV39').value);$('copyResolveDebugV39').textContent='DIAGNOSTICA COPIATA'}catch(error){$('resolveDebugTextV39').select();$('copyResolveDebugV39').textContent='SELEZIONATA · PREMI CTRL+C'}};
$('sendResolvePackageV33').onclick=()=>prepareResolveHandoffV33();$('exportTimelineXmlV33').onclick=()=>legacyTimelineExportV33('/exports/broll-timeline.xml','broll-timeline.xml');$('exportTimelineDraV33').onclick=()=>legacyTimelineExportV33('/resolve/broll-timeline.dra','broll-timeline.dra.zip');$('openTimelineResolveV33').onclick=()=>legacyTimelineExportV33('/resolve/broll-timeline',null);
document.querySelector('.genericCoverageV33').ontoggle=e=>{if(e.target.open&&!genericCoverageV33.items.length)loadGenericCoverageV33(false)};
$('customSearchV138').onsubmit=async event=>{event.preventDefault();const query=$('customQueryV138').value.trim();if(query&&state.pid)await loadGenericCoverageV33(true,'custom',query)};
$('loadPlaceCoverageV35').onclick=()=>loadGenericCoverageV33(true,'places');
$('loadGenericCoverageV33').onclick=()=>loadGenericCoverageV33(true);
setInterval(pollResolveBridgeLiveV34,2000);pollResolveBridgeLiveV34();

let resolveRestoreProjectV39=null;
async function restoreResolveDeliveryV39(){if(!state.pid||resolvePreparingV37||resolveRestoreProjectV39===state.pid)return;resolveRestoreProjectV39=state.pid;clearInterval(resolveHandoffPollV33);resolveHandoffIdV33=null;try{const row=await api(`/projects/${state.pid}/resolve-handoffs/latest`);if(!row.package_id||row.status==='discarded')return;resolveHandoffIdV33=row.package_id;resolveDeliveryStartedV37=Date.now();await pollResolveHandoffV33();if(!['failed','completed'].includes(row.status))resolveHandoffPollV33=setInterval(pollResolveHandoffV33,1000)}catch(_){resolveRestoreProjectV39=null}}
const hydrateTimelineBaseV33=hydrate;hydrate=async function(){const value=await hydrateTimelineBaseV33();syncTimelineExportV33();await loadResolveComponentsV71();await restoreResolveDeliveryV39();return value};syncTimelineExportV33();
'''

