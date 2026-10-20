from __future__ import annotations

import os
"""Product UI augmentation for project/media lifecycle and social controls.

The established Curation V1 page owns the editor state and media rendering. This
module injects project management, beat research and authenticated social source
controls into the same closure so all additions reuse proven state/hydration.
"""

import re
import base64
from functools import lru_cache
from pathlib import Path

from .curation_ui import render_curation_page
from .social_gallery import CSS as GALLERY_CSS, JS as GALLERY_JS
from .curation_theme import CSS as STUDIO_CSS
from .transcript_intent_ui import CSS as TRANSCRIPT_INTENT_CSS, JS as TRANSCRIPT_INTENT_JS, PANEL as TRANSCRIPT_INTENT_PANEL
from .timeline_export_ui import CSS as TIMELINE_EXPORT_CSS, JS as TIMELINE_EXPORT_JS, PANEL as TIMELINE_EXPORT_PANEL
from .theme_settings_ui import CSS as THEME_SETTINGS_CSS, JS as THEME_SETTINGS_JS, PANEL as THEME_SETTINGS_PANEL
from .release_version import RELEASE_VERSION


@lru_cache(maxsize=2)
def _brand_data_uri(filename: str) -> str:
    path = Path(__file__).resolve().parents[1] / "assets" / "branding" / filename
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


_MANAGEMENT_CSS = r"""
<style id="management-v2-style">
.connectionV6{color:var(--muted);font-size:12px}.connectionV6.ready{color:#86e89f;font-weight:700}#tiktokVideosV2,#instagramVideosV2,#verticalVideos{grid-template-columns:repeat(3,minmax(0,1fr));align-items:start}.portraitSocialV6>img,.portraitSocialV6>video{width:100%;height:auto!important;aspect-ratio:9/16;object-fit:contain;background:#080b10}.portraitSocialV6.noCoverV7>img{display:none}.socialMissingV7{padding:24px 12px;text-align:center;color:var(--muted);background:#151e28;font-size:13px}.portraitSocialV6.noCoverV7{align-self:start}@media(max-width:1000px){#tiktokVideosV2,#instagramVideosV2,#verticalVideos{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){#tiktokVideosV2,#instagramVideosV2,#verticalVideos{grid-template-columns:1fr}}.portraitSocialV6 .copy>b{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:2.7em}.portraitSocialV6 .copy>small{display:none}.portraitSocialV6 .copy>a{display:block;margin-top:8px;font-size:12px}.portraitSocialV6 .badge.vertical{display:none}.managementV2{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:10px 0}.managementV2 button{font-size:12px}.dangerV2{border-color:#75383f!important;color:#ffb4bc!important;background:#28151a!important}.libraryV2{width:min(980px,92vw);max-height:82vh;overflow:auto}.projectRowsV2{display:grid;gap:8px;margin:12px 0}.projectRowV2{display:grid;grid-template-columns:minmax(180px,1.6fr) minmax(120px,.8fr) minmax(100px,.5fr) auto;gap:10px;align-items:center;border:1px solid var(--line);background:#0d131b;border-radius:10px;padding:10px}.projectRowV2 strong,.projectRowV2 small{display:block}.projectRowV2 .actionsV2{display:flex;gap:6px;flex-wrap:wrap}.showMoreV2{margin:8px 0 0}.beatResearchStateV2{color:var(--muted);font-size:12px}.storageV2{font-variant-numeric:tabular-nums}.socialStateV2{display:inline-block;margin-left:4px;padding:2px 6px;border-radius:999px;border:1px solid #596879;font-size:10px;font-weight:800}.socialStateV2.ready{border-color:#86e89f;color:#86e89f}.socialStateV2.preview{border-color:#ffd166;color:#ffd166}.socialStateV2.manual{border-color:#ff9f9f;color:#ff9f9f}.socialLoginStateV2{font-size:11px;color:var(--muted)}.directorV5{display:flex;align-items:center;gap:7px;flex-wrap:wrap;padding-left:8px;border-left:1px solid var(--line)}.directorV5 select{background:#141d27;color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:9px 10px;font:inherit;font-weight:700}.directorStateV5{font-size:11px;color:var(--muted);max-width:420px}.directorStateV5.ready{color:#86e89f}.directorStateV5.busy{color:#ffd166}@media(max-width:850px){.projectRowV2{grid-template-columns:1fr}.projectRowV2 .actionsV2{justify-content:flex-start}}
.workflowV5 h2{margin:0 0 6px}.searchGroupsV5{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.searchGroupsV5>div{display:flex;flex-direction:column;align-items:flex-start;gap:8px;padding:12px;background:var(--p2);border:1px solid var(--line);border-radius:10px}.toolsV5{margin-top:14px;padding-top:10px;border-top:1px solid var(--line)}.toolsV5 summary{cursor:pointer;color:var(--muted);font-weight:650}.toolsV5 .row{margin-top:10px}.socialLoginStateV2{display:block;margin-top:9px;max-width:100%;line-height:1.6}.directorV5{padding:0;border:0;margin:12px 0}.managementV2{padding:10px;background:var(--p2);border:1px solid var(--line);border-radius:8px}@media(max-width:750px){.searchGroupsV5{grid-template-columns:1fr}}
.resolveArrivalV30{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-top:8px;padding:8px 11px;border:1px solid #4d5b78;border-radius:9px;background:#182338;color:#b9c5da;font-size:11px}.resolveArrivalV30.ready{border-color:#527c76;background:#182e31;color:#b9ddd7}.resolveArrivalV30 b{color:#d8ff5b}.resolveArrivalV30[hidden]{display:none}
.stepStatusV12{display:inline-flex;align-items:center;gap:5px;margin-left:9px;padding:3px 8px;border:1px solid var(--line);border-radius:999px;color:var(--muted);font-size:11px;font-weight:750;vertical-align:middle}.stepStatusV12.done{color:#86e89f;border-color:#39784b;background:#13271a}.stepStatusV12.running{color:#ffd166;border-color:#806a2d;background:#2b2513}.stepStatusV12.failed{color:#ff9f9f;border-color:#7a3e45;background:#2a171b}.stepStatusV12.running::before{content:'';width:7px;height:7px;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;animation:stepSpinV12 .8s linear infinite}@keyframes stepSpinV12{to{transform:rotate(360deg)}}
.realProgressV34{display:grid;gap:7px;width:100%;margin-top:6px}.realProgressV34[hidden]{display:none}.realProgressV34 progress{width:100%;height:9px;accent-color:#d8ff5b}.sourceChecksV34{display:flex;gap:6px;flex-wrap:wrap}.sourceChecksV34 span{padding:3px 7px;border:1px solid #50597a;border-radius:999px;color:var(--muted);font-size:10px}.sourceChecksV34 span.done{color:#86e89f;border-color:#39784b;background:#13271a}.directorProgressV34{max-width:620px;margin:8px 0 4px}
#tiktokVideosV2,#instagramVideosV2,#verticalVideos{grid-template-columns:repeat(6,minmax(140px,1fr));overflow-x:auto;max-width:100%;padding-bottom:8px}.portraitSocialV6 .copy{padding:8px}.portraitSocialV6 .copy>b{font-size:12px}.portraitSocialV6>img{object-fit:cover}.portraitSocialV6{min-width:0}.socialMediaStatusV8{font-size:11px;color:var(--muted);display:block;margin-top:6px}.providerLoginV29{margin:14px 0;padding:12px 14px;border:1px solid #58658f;border-radius:12px;background:#1d223e}.providerLoginV29 summary{color:var(--ink)}.envatoDownloadV29{width:100%;margin-top:8px;border-color:#8ca64d!important;background:#2a331d!important}.envatoDownloadStateV29{display:block;margin-top:6px;color:var(--muted);font-size:11px;line-height:1.35}.releaseVersionV35{display:inline-flex;vertical-align:middle;margin-left:8px;padding:3px 8px;border:1px solid #6875ac;border-radius:999px;color:#d8ff5b;background:#242b4b;font-size:11px;font-weight:800;letter-spacing:.04em}
</style>
"""

_WORKFLOW_ACCORDION_CSS = r"""
<style id="workflow-accordion-v42-style">
[data-workflow-step-v42]{position:relative}.workflowHeaderV42{display:flex!important;align-items:center;gap:10px;cursor:pointer;user-select:none}.workflowTitleRowV43{display:flex;align-items:center;gap:10px}.workflowHeaderV42:focus-visible{outline:2px solid #d8ff5b;outline-offset:4px}.workflowChevronV42{display:inline-grid;flex:0 0 32px;place-items:center;width:32px;height:32px;margin:0;padding:0;border:1px solid #7781aa;border-radius:8px;background:#252c4c;color:#f3f5ff;font-size:21px;font-weight:900;line-height:1;box-shadow:0 2px 8px #070a1870;vertical-align:middle;transition:background .15s,border-color .15s,transform .15s}.workflowChevronV42:hover{background:#343d66;border-color:#aab4e4}.workflowChevronV42:active{transform:scale(.94)}.workflowCollapsedV42>.workflowBodyV42{display:none}.workflowBodyV42{display:block}.workflowStepFiveClosedV42+.grid{display:none}.workflowStepFiveOpenV42+.grid{display:grid}
</style>
"""

_WORKFLOW_ACCORDION_JS = r"""
let workflowProjectV42=null,workflowSuggestedV42=0,transcriptConfirmedProjectV42=null;
function workflowStepNodesV42(){return [...document.querySelectorAll('[data-workflow-step-v42]')].sort((a,b)=>Number(a.dataset.workflowStepV42)-Number(b.dataset.workflowStepV42))}
function workflowHeaderV42(node){if(node.matches('h2'))return node;return node.querySelector(':scope > .top')||node.querySelector(':scope > h2')||node.querySelector(':scope > details > summary')}
function setWorkflowOpenV42(node,open){
 const step=Number(node.dataset.workflowStepV42),header=workflowHeaderV42(node),chevron=header?.querySelector('.workflowChevronV42');
 if(step===7){node.classList.toggle('workflowStepFiveClosedV42',!open);node.classList.toggle('workflowStepFiveOpenV42',open)}
 else if(step===3||step===8){const details=node.querySelector(':scope > details');if(details)details.open=!!open}
 else node.classList.toggle('workflowCollapsedV42',!open);
 if(header){header.setAttribute('aria-expanded',String(!!open));if(chevron)chevron.textContent=open?'▼':'▶'}
}
function workflowIsOpenV42(node){const step=Number(node.dataset.workflowStepV42);if(step===7)return node.classList.contains('workflowStepFiveOpenV42');if(step===3||step===8)return !!node.querySelector(':scope > details')?.open;return !node.classList.contains('workflowCollapsedV42')}
function installWorkflowAccordionV42(){
 for(const node of workflowStepNodesV42()){
  if(node.dataset.workflowAccordionV42)continue;node.dataset.workflowAccordionV42='1';const step=Number(node.dataset.workflowStepV42),header=workflowHeaderV42(node);if(!header)continue;
  if(step!==3&&step!==7&&step!==8){const body=document.createElement('div');body.className='workflowBodyV42';for(const child of [...node.children])if(child!==header)body.appendChild(child);node.appendChild(body)}
  header.classList.add('workflowHeaderV42');header.tabIndex=0;header.setAttribute('role','button');const chevron=document.createElement('button');chevron.type='button';chevron.className='workflowChevronV42';chevron.tabIndex=-1;chevron.setAttribute('aria-label',`Apri o chiudi sezione ${step}`);const nestedHeading=header.querySelector(':scope > div > h2');if(nestedHeading){const titleRow=document.createElement('div');titleRow.className='workflowTitleRowV43';nestedHeading.before(titleRow);titleRow.append(chevron,nestedHeading)}else header.prepend(chevron);
  const toggle=event=>{if(event.type==='keydown'&&!['Enter',' '].includes(event.key))return;if(event.target.closest('button')&&event.target!==chevron)return;event.preventDefault();setWorkflowOpenV42(node,!workflowIsOpenV42(node))};header.addEventListener('click',toggle);header.addEventListener('keydown',toggle);setWorkflowOpenV42(node,false);
 }
}
function openOnlyWorkflowStepV42(step,scroll=true){installWorkflowAccordionV42();for(const node of workflowStepNodesV42()){const open=Number(node.dataset.workflowStepV42)===Number(step);setWorkflowOpenV42(node,open);node.classList.toggle('workflowNextV42',open)}const target=document.querySelector(`[data-workflow-step-v42="${step}"]`);if(scroll)target?.scrollIntoView({behavior:'smooth',block:'start'})}
function nextWorkflowStepV42(){
 if(!state.pid)return 0;if(!state.data.analysis_ready)return 2;if(!state.data.editorial_plan_ready)return transcriptConfirmedProjectV42===state.pid?5:4;
 const chunks=state.data.chunks||[],attempts=chunks.flatMap(c=>c.retrieval_diagnostics?.video_attempts||[]);if(!attempts.length)return 4;
 const broll=chunks.filter(c=>c.action==='BROLL'),unresolved=broll.some(c=>{const value=state.sel.get(c.id);return value!=='NO_BROLL'&&value!=='CONTINUE'&&(!Array.isArray(value)||!value.length)});if(unresolved)return 7;
 if(!(genericCoverageV33?.selected||[]).length)return 8;return 9;
}
function syncWorkflowAccordionV42(force=false){installWorkflowAccordionV42();const next=nextWorkflowStepV42();if(!next)return;const projectChanged=workflowProjectV42!==state.pid;if(projectChanged){workflowProjectV42=state.pid;workflowSuggestedV42=next;openOnlyWorkflowStepV42(next,false);return}if(force||next!==workflowSuggestedV42){workflowSuggestedV42=next;openOnlyWorkflowStepV42(next,force)}}
document.addEventListener('click',event=>{if(event.target.closest('#continueWorkflowV15')){transcriptConfirmedProjectV42=state.pid;workflowSuggestedV42=5;setTimeout(()=>openOnlyWorkflowStepV42(5),0)}});
const workflowTerminalBaseV42=window.ramblaRunTerminal;window.ramblaRunTerminal=(run)=>{if(workflowTerminalBaseV42)workflowTerminalBaseV42(run);if(run?.status!=='SUCCEEDED')return;const kind=workflowKindV12(run.stage_type);if(kind==='analyze')openOnlyWorkflowStepV42(3);else if(kind==='director_api')openOnlyWorkflowStepV42(6);else if(['videos','social','images'].includes(kind))openOnlyWorkflowStepV42(7)};
const workflowDrawBaseV42=draw;draw=()=>{workflowDrawBaseV42();syncWorkflowAccordionV42(false)};
installWorkflowAccordionV42();
"""

_PROJECT_DIALOG = r"""
<dialog id="socialConnectDialogV5" class="libraryV2">
<h2>TikTok + Instagram · connection check</h2>
<p>Choose a connected provider and press START SEARCH. If needed, OPEN its browser and sign in. Keep the window open. VERIFY only inspects the current page.</p>
<p class="muted">No test searches or automatic refreshes. If a CAPTCHA appears, resolve it manually in that window; RAMBLA pauses navigation.</p>
<div class="row"><button id="openTikTokCheckV5">OPEN TIKTOK</button><button id="openInstagramCheckV5">OPEN INSTAGRAM</button></div>
<p id="tiktokCheckStateV5" role="status"></p><p id="instagramCheckStateV5" role="status"></p>
<div class="row"><label><input type="checkbox" id="useTiktokV5" disabled> TikTok</label><label><input type="checkbox" id="useInstagramV5" disabled> Instagram</label></div>
<p id="socialNextStepV5" role="status">Verify connections to enable available providers.</p>
<div class="row"><button id="verifyTiktokV8">VERIFY TIKTOK</button><button id="verifyInstagramV8">VERIFY INSTAGRAM</button><button id="verifySocialV5">VERIFY BOTH</button><button id="startSocialV5" class="primary" disabled>START SEARCH</button><button id="cancelSocialV5">CLOSE</button></div>
</dialog>
<dialog id="projectLibraryV2" class="libraryV2">
  <div class="top"><div><h2 style="margin:0">Project Library</h2><div class="muted">Open, rename or remove local RAMBLA projects. Disk usage is calculated from the actual project folder.</div></div><button id="closeProjectsV2">CLOSE</button></div>
  <div class="row" style="margin-top:10px"><b>Disk usage</b><span id="libraryTotalV2" class="muted storageV2"></span><button id="refreshProjectsV2" class="ghost">REFRESH</button></div>
  <div id="projectRowsV2" class="projectRowsV2"><p class="muted">Loading projects…</p></div>
</dialog>
"""

_MANAGEMENT_JS = r"""
let socialSearchScopeV5=null;
let socialOpeningV5=0,socialCheckingV5=false,socialStartingV5=false;
const socialReadyV5={tiktok:false,instagram:false};
async function syncResolveArrivalV30(){const node=$('resolveArrivalV30');if(!node||!state.pid)return;try{const row=await api(`/projects/${state.pid}/resolve-bridge`);node.hidden=!row.received;if(!row.received)return;node.className='resolveArrivalV30 ready';node.innerHTML=`<b>✓ AUDIO RICEVUTO DA RESOLVE</b><span>${esc(row.resolve_project||'')} · ${esc(row.resolve_timeline||'')} · ${Number(row.duration||0).toFixed(1)} s</span><span>${row.detect_videos?`Detect videos: ${Number(row.existing_video_count||0)} intervalli trovati`:'Detect videos non richiesto'}</span>`}catch(_){node.hidden=true}}
const socialCheckboxV5=p=>$(p==='tiktok'?'useTiktokV5':'useInstagramV5');
function selectedSocialV5(){return ['tiktok','instagram'].filter(p=>socialReadyV5[p]&&socialCheckboxV5(p).checked)}
function syncSocialStartV5(){
 const providers=selectedSocialV5(),busy=!!socialOpeningV5||socialCheckingV5||socialStartingV5;
 $('startSocialV5').disabled=busy||!providers.length;
 $('verifySocialV5').disabled=busy;
 $('verifyTiktokV8').disabled=busy;$('verifyInstagramV8').disabled=busy;
 $('socialNextStepV5').textContent=busy?'Connection check / request in progress…':providers.length?'Ready: '+providers.join(' + ')+'. Press START SEARCH. Blocked providers will be skipped.':'Verify connections, then select at least one ready provider.';
}
async function openSocialCheckV5(provider){
 const node=$(provider+'CheckStateV5');socialOpeningV5++;socialReadyV5[provider]=false;
 socialCheckboxV5(provider).checked=false;socialCheckboxV5(provider).disabled=true;syncSocialStartV5();
 node.textContent=provider+': opening browser…';
 try{const opened=await api(`/social/${provider}/login`,{method:'POST'});node.textContent=opened.session==='normal_chrome'?provider+': aperto nel profilo Chrome attivo. Completa l’accesso, poi premi VERIFICA CONNESSIONI.':provider+': sign in and KEEP this window open, then VERIFY CONNECTIONS.'}
 catch(e){node.textContent=provider+': '+(e.message||String(e))}
 finally{socialOpeningV5--;syncSocialStartV5()}
}
async function prepareSocialV5(beatId=null){
 if(state.run)return;socialSearchScopeV5=beatId;
 if(globalThis.RAMBLA_CLOUD_MODE){
  const providers=['tiktok','instagram'];
  if(beatId){
   if(state.active!==beatId)throw Error('Active beat changed; reopen its social search.');
   await researchBeatV2('append',providers);
  }else{
   const result=await api(`/projects/${state.pid}/source/social`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({providers})});
   if(result.status!=='started')throw Error('Search did not start.');
   await watch(result.run_id);
  }
  return;
 }
 $('socialConnectDialogV5').showModal();
 try{const status=await api('/social/status');for(const provider of ['tiktok','instagram']){const ready=!!status.providers?.[provider]?.connection_ready;socialReadyV5[provider]=ready;socialCheckboxV5(provider).disabled=!ready;socialCheckboxV5(provider).checked=ready;if(ready)$(provider+'CheckStateV5').textContent=provider+': CONNECTED · existing session ready, no verification needed.'}}catch(e){}
 syncSocialStartV5();
}
async function checkSocialAndRunV5(providers=['tiktok','instagram']){
 socialCheckingV5=true;syncSocialStartV5();
 try{await Promise.all(providers.map(async provider=>{
  const node=$(provider+'CheckStateV5');node.textContent=provider+': checking the open session without navigation…';
  socialReadyV5[provider]=false;
  try{const result=await api(`/social/${provider}/check`,{method:'POST'});socialReadyV5[provider]=!!result.ready;node.textContent=provider+': '+(result.ready?(result.browser_state==='session_unconfirmed'?'SESSIONE NON CONFERMATA · PUOI CERCARE':'SEARCH READY'):'BLOCKED')+' · '+result.detail+' · login '+(result.login_state==='verified'?'verified':result.login_state==='required'?'required':'unknown')}
  catch(e){node.textContent=provider+': '+(e.message||String(e))}
  socialCheckboxV5(provider).disabled=!socialReadyV5[provider];socialCheckboxV5(provider).checked=socialReadyV5[provider];
 }))}finally{socialCheckingV5=false;syncSocialStartV5();socialStatusV2()}
}
async function startSelectedSocialV5(){
 const providers=selectedSocialV5();if(!providers.length||socialOpeningV5||socialCheckingV5||socialStartingV5||state.run)return;
 socialStartingV5=true;state.currentStageV12='social';if(typeof workflowFailureV12!=='undefined')workflowFailureV12=null;if(typeof syncWorkflowStatusV12==='function')syncWorkflowStatusV12();syncSocialStartV5();
 try{
  if(socialSearchScopeV5){if(state.active!==socialSearchScopeV5)throw Error('Active beat changed; reopen its social search.');await researchBeatV2('append',providers)}
  else{beginSearchV9(providers,'*');const result=await api(`/projects/${state.pid}/source/social`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({providers})});if(result.status!=='started')throw Error('Search did not start.');await watch(result.run_id)}
  $('socialConnectDialogV5').close();$('runStatus').textContent='Searching '+providers.join(' + ')+'…';
 }catch(e){finishSearchV9({status:'FAILED'});$('socialNextStepV5').textContent=e.message||String(e)}finally{socialStartingV5=false;$('startSocialV5').disabled=!selectedSocialV5().length||!!state.run;$('verifySocialV5').disabled=false}
}
$('openTikTokCheckV5').onclick=()=>openSocialCheckV5('tiktok');
$('openInstagramCheckV5').onclick=()=>openSocialCheckV5('instagram');
$('verifySocialV5').onclick=()=>checkSocialAndRunV5();
$('verifyTiktokV8').onclick=()=>checkSocialAndRunV5(['tiktok']);
$('verifyInstagramV8').onclick=()=>checkSocialAndRunV5(['instagram']);
$('startSocialV5').onclick=startSelectedSocialV5;
$('useTiktokV5').onchange=syncSocialStartV5;$('useInstagramV5').onchange=syncSocialStartV5;
$('cancelSocialV5').onclick=()=>$('socialConnectDialogV5').close();

const expandedShelvesV2=new Set();
let directorStatusV5={providers:{},loaded:false};
const shelfLimitsV2={verticalVideos:6,tiktokVideosV2:6,instagramVideosV2:6,webNewsVideosV2:3,envatoVideosV2:3,videos:3,stockVideos:3,images:4};
function formatBytesV2(value){let n=Number(value||0);if(n<1024)return `${n} B`;const units=['KB','MB','GB','TB'];let i=-1;do{n/=1024;i++}while(n>=1024&&i<units.length-1);return `${n.toFixed(n>=100?0:n>=10?1:2)} ${units[i]}`}
function activeChunkV2(){return (state.data.chunks||[]).find(c=>c.id===state.active)||null}
function prepareBrollViewV24(){const beats=(state.data.chunks||[]).filter(c=>c.action==='BROLL');state.filter='broll';if(!beats.some(c=>c.id===state.active))state.active=beats[0]?.id||null;draw();centerActiveBeat();saveWorkspaceSessionV13()}
function syncProjectNameV25(){const input=$('projectNameV25');if(!input)return;input.disabled=!state.pid;input.value=state.project?.name||'New Reel'}
async function saveProjectNameV25(){const input=$('projectNameV25');if(!input||!state.pid)return;const name=input.value.trim()||'New Reel';if(name===(state.project?.name||'New Reel'))return;input.disabled=true;try{const p=await api(`/projects/${state.pid}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});state.project=p;input.value=p.name||name;$('projectStatus').textContent=`Project ${state.pid} · ${input.value} · autosaved locally`}catch(e){input.value=state.project?.name||'New Reel';$('projectStatus').textContent=e.message||String(e)}finally{input.disabled=false}}
function saveWorkspaceSessionV13(){if(!state.pid)return Promise.resolve();return fetch('/api/curation/workspace-session',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_id:state.pid,active_chunk_id:state.active||null}),keepalive:true}).catch(()=>{})}
async function restoreWorkspaceSessionV13(){
 let saved={};try{saved=await api('/workspace-session')}catch(_){saved={}}
 const pid=new URLSearchParams(location.search).get('project')||saved.project_id||localStorage.getItem('rambla-project');if(!pid)return;
 try{state.pid=pid;state.active=saved.project_id===pid?saved.active_chunk_id:null;const p=await api(`/projects/${pid}`);show(p,p.source_video?.path?.split(/[\\/]/).pop()||'Reel',`/api/curation/projects/${pid}/media/source-video/source`);await hydrate();localStorage.setItem('rambla-project',pid);saveWorkspaceSessionV13()}
 catch(e){const missing=/\b404\b|not found/i.test(String(e?.message||e));if(missing){state.pid=null;state.active=null;localStorage.removeItem('rambla-project');$('projectStatus').textContent='Saved project not found. Open a RAMBLA project file or create a new project.'}else{$('projectStatus').textContent='Ripristino progetto momentaneamente non disponibile; ritento…';setTimeout(restoreWorkspaceSessionV13,3000)}}
}
const showBaseV13=show;show=(...args)=>{showBaseV13(...args);syncProjectNameV25();syncResolveArrivalV30();saveWorkspaceSessionV13()};
const projectBaseV25=project;project=async(...args)=>{const result=await projectBaseV25(...args);syncProjectNameV25();return result};
restore=restoreWorkspaceSessionV13;
setInterval(saveWorkspaceSessionV13,15000);
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')saveWorkspaceSessionV13()});
let workflowFailureV12=null;
function setWorkflowStatusV12(id,status,label){const node=$(id);if(!node)return;node.className='stepStatusV12 '+status;node.textContent=(status==='done'?'✓ ':status==='failed'?'! ':'')+label;node.hidden=status==='idle'}
function syncWorkflowStatusV12(){
 const chunks=state.data.chunks||[],videoAttempts=chunks.flatMap(c=>c.retrieval_diagnostics?.video_attempts||[]),imageAttempts=chunks.flatMap(c=>c.retrieval_diagnostics?.image_attempts||[]);
 const socialAttempts=videoAttempts.filter(a=>['tiktok','instagram'].includes(String(a.provider||'').toLowerCase())),brollAttempts=videoAttempts.filter(a=>!['tiktok','instagram'].includes(String(a.provider||'').toLowerCase()));
 const stage=state.currentStageV12||'',busy=!!state.run,status=(complete,kind)=>workflowFailureV12===kind?'failed':busy&&stage===kind?'running':complete?'done':'idle';
 setWorkflowStatusV12('analysisCompleteV12',status(!!state.data.analysis_ready,'analyze'),'Analysis complete');
 const planStatus=status(!!state.data.editorial_plan_ready,'director_api');
 setWorkflowStatusV12('planCompleteV12',planStatus,planStatus==='failed'?'Plan failed':planStatus==='running'?'Creazione piano in corso':'Plan complete');
 setWorkflowStatusV12('videoCompleteV12',status(brollAttempts.length>0,'videos'),brollAttempts.length?'B-roll searched':'B-roll');
 setWorkflowStatusV12('socialCompleteV12',status(socialAttempts.length>0,'social'),socialAttempts.length?'Social searched':'Social');
 setWorkflowStatusV12('imagesCompleteV12',status(imageAttempts.length>0,'images'),imageAttempts.length?'Images searched':'Images');
}
function shelfAssetsV2(chunk,id){if(!chunk)return[];if(id==='verticalVideos')return chunk.assets.filter(a=>a.kind==='video'&&a.provider==='youtube_shorts');if(id==='tiktokVideosV2')return chunk.assets.filter(a=>a.kind==='video'&&a.provider==='tiktok');if(id==='instagramVideosV2')return chunk.assets.filter(a=>a.kind==='video'&&a.provider==='instagram');if(id==='webNewsVideosV2')return chunk.assets.filter(a=>a.kind==='video'&&a.provider==='web_video');if(id==='envatoVideosV2')return chunk.assets.filter(a=>a.kind==='video'&&a.provider==='envato');if(id==='videos')return chunk.assets.filter(a=>a.kind==='video'&&a.provider!=='pexels'&&a.provider!=='envato'&&!VERTICAL.has(a.provider)&&a.provider!=='web_video');if(id==='stockVideos')return chunk.assets.filter(a=>a.kind==='video'&&a.provider==='pexels');return chunk.assets.filter(a=>a.kind==='image')}
function bindCardsV2(chunk){document.querySelectorAll('.card').forEach(node=>{const media=node.querySelector('video,img'),select=node.querySelector('.select'),source=node.querySelector('.copy>a'),a=(chunk.assets||[]).find(x=>x.asset_id===node.dataset.a);if(media)media.onclick=()=>['tiktok','instagram','youtube_shorts'].includes(a?.provider)?showSocialGifV9(a):a?.provider==='envato'?window.open(a.source_page,'_blank','noopener'):inspectMedia(media);if(source){source.textContent='Apri fonte ↗';source.classList.add('sourceButtonV9')}if(select)select.onclick=()=>pick(chunk.id,node.dataset.a)})}
function installShelfExpansionV2(chunk,id){const container=$(id),assets=shelfAssetsV2(chunk,id),limit=shelfLimitsV2[id],key=`${chunk.id}:${id}`;if(!container)return;let button=document.getElementById(`moreV2-${id}`);if(assets.length<=limit){if(button)button.remove();return}if(!button){button=document.createElement('button');button.id=`moreV2-${id}`;button.className='ghost showMoreV2';container.insertAdjacentElement('afterend',button)}const expanded=expandedShelvesV2.has(key);button.textContent=expanded?'SHOW LESS':`SHOW MORE (${assets.length-limit})`;button.onclick=()=>{expanded?expandedShelvesV2.delete(key):expandedShelvesV2.add(key);draw()};if(expanded){container.innerHTML=assets.map(card).join('');bindCardsV2(chunk)}}
async function refreshProjectsV2(){const payload=await api('/projects'),rows=payload.projects||[],box=$('projectRowsV2');$('libraryTotalV2').textContent=`${rows.length} projects · ${formatBytesV2(rows.reduce((n,r)=>n+Number(r.size_bytes||0),0))}`;box.innerHTML=rows.length?rows.map(r=>`<article class="projectRowV2" data-project-v2="${esc(r.project_id)}"><div><strong>${esc(r.name||'Untitled project')}</strong><small>${esc(r.project_id)} · ${esc(r.source_filename||'No source')}</small></div><div><small>${r.has_transcript?'Transcript ready':'No transcript'} · ${r.has_editorial_plan?'Plan ready':'No plan'}</small><small>${esc(r.modified_at||'')}</small></div><div class="storageV2"><b>${formatBytesV2(r.size_bytes)}</b><small>${esc(r.retrieved_media_count||0)} media</small></div><div class="actionsV2"><button data-open-v2="${esc(r.project_id)}">OPEN</button><button data-rename-v2="${esc(r.project_id)}">RENAME</button><button class="dangerV2" data-delete-v2="${esc(r.project_id)}">DELETE</button></div></article>`).join(''):'<p class="muted">No saved projects.</p>';box.querySelectorAll('[data-open-v2]').forEach(b=>b.onclick=()=>openProjectV2(b.dataset.openV2));box.querySelectorAll('[data-rename-v2]').forEach(b=>b.onclick=()=>renameProjectV2(b.dataset.renameV2));box.querySelectorAll('[data-delete-v2]').forEach(b=>b.onclick=()=>deleteProjectV2(b.dataset.deleteV2))}
async function openProjectV2(pid){const p=await api(`/projects/${pid}`);state.pid=pid;localStorage.setItem('rambla-project',pid);await showProjectWithOriginalSource(p);await hydrate();$('projectLibraryV2').close()}
async function renameProjectV2(pid){const row=(await api('/projects')).projects.find(x=>x.project_id===pid),name=prompt('Rename project',row?.name||'');if(name==null)return;const p=await api(`/projects/${pid}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});if(state.pid===pid){state.project=p;$('projectStatus').textContent=`Project ${pid} · ${p.name} · autosaved locally`}await refreshProjectsV2()}
async function deleteProjectV2(pid){const listing=await api('/projects'),row=listing.projects.find(x=>x.project_id===pid);if(!confirm(`This will permanently delete “${row?.name||pid}” and free about ${formatBytesV2(row?.size_bytes||0)}. Continue?`))return;await api(`/projects/${pid}`,{method:'DELETE'});if(state.pid===pid){localStorage.removeItem('rambla-project');state.pid=null;state.project=null;resetProjectView();$('projectStatus').textContent='Project deleted. Choose or create another project.'}await refreshProjectsV2()}
async function cleanBeatMediaV2(beatId){if(state.run||!state.pid)return;if(!confirm('Cancellare risultati e selezioni solo di questa frase? Potrai rilanciare la ricerca.'))return;await api(`/projects/${state.pid}/beats/${encodeURIComponent(beatId)}/media/clean`,{method:'POST'});const prefix=state.pid+':'+beatId+':';for(const map of [galleryV9,searchesV9])for(const key of map.keys())if(key.startsWith(prefix))map.delete(key);for(const key of Object.keys(localStorage))if(key.startsWith('round:'+prefix))localStorage.removeItem(key);await hydrate();$('beatResearchStateV2').textContent='Media della frase rimossi. Avvia una nuova ricerca.'}
async function cleanMediaV2(){if(!state.pid)return;if(!confirm('Delete downloaded/search B-roll, images and previews for this project? Transcript and editorial plan stay safe.'))return;$('cleanMediaV2').disabled=true;try{const result=await api(`/projects/${state.pid}/media/clean`,{method:'POST'});expandedShelvesV2.clear();galleryV9.clear();for(const key of Object.keys(localStorage))if(key.startsWith('round:'+state.pid+':'))localStorage.removeItem(key);await hydrate();const c=result.cleanup||{};$('runStatus').textContent=`Media cleaned · ${c.deleted_files||0} files · ${formatBytesV2(c.deleted_bytes||0)} freed`}finally{$('cleanMediaV2').disabled=false}}
async function researchBeatV2(mode,providers=[],options={}){const chunk=activeChunkV2();if(!chunk||chunk.action!=='BROLL'||state.run)return;const replace=mode==='replace';if(replace&&!confirm('Replace the current B-roll and image results for this beat with a new search? Existing selections for this beat will be cleared.'))return;const buttons=$('beatActionsV2').querySelectorAll('button');buttons.forEach(b=>b.disabled=true);const socialOnly=providers.length>0;$('beatResearchStateV2').textContent=replace?'Starting new search…':socialOnly?'Searching TikTok + Instagram only…':'Searching for additional unique results…';const payload={mode,providers,visual_verify:!!document.getElementById("socialQwenV2")?.checked,...options};beginSearchV9(providers.length?providers:['youtube_shorts'],chunk.id,{...options,visual_verify:payload.visual_verify});try{const r=await api(`/projects/${state.pid}/beats/${encodeURIComponent(chunk.id)}/research`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if(r.status==='started')await watch(r.run_id);else await hydrate()}catch(e){finishSearchV9({status:'FAILED'});buttons.forEach(b=>b.disabled=false);$('beatResearchStateV2').textContent=e.message||String(e);throw e}}
function syncDirectorControlsV5(){const select=$('directorProviderV5'),button=$('generateDirectorV5'),status=$('directorStateV5');if(!select||!button||!status)return;const selected=select.value,row=directorStatusV5.providers?.[selected]||{},analysisReady=!!state.data.analysis_ready,configured=selected==='manual'||!!row.configured,busy=!!state.run;button.disabled=selected==='manual'||!analysisReady||!configured||busy;if(busy&&state.currentStageV12==='director_api'){status.className='directorStateV5 busy';status.textContent='Director running · progress is shown in Analysis Details';return}if(workflowFailureV12==='director_api'){status.className='directorStateV5';status.textContent='Piano non riuscito \u00b7 vedi Analysis Details';return}if(state.data.editorial_error&&analysisReady&&!state.data.editorial_plan_ready){status.className='directorStateV5';status.textContent=`Piano generato ma non utilizzabile · ${state.data.editorial_error}`;return}if(state.data.editorial_plan_ready){status.className='directorStateV5 ready';status.textContent='\u2713 Piano completato';return}if(selected==='manual'){status.className='directorStateV5';status.textContent='Manual plan import';return}if(!configured){status.className='directorStateV5';status.textContent=selected==='groq'?'Groq API key not configured':selected==='gemini'?'Gemini API key not configured':'No cloud Director API configured';return}status.className='directorStateV5 ready';const reasoning=String(row.thinking_level||'high').toUpperCase();if(selected==='auto'){status.textContent=`AUTO · ${(row.chain||[]).join(' → ')} · ${reasoning} reasoning · transcript only`}else{status.textContent=`${selected==='groq'?'Groq':'Gemini'} API · ${row.model||'default'} · ${reasoning} reasoning · transcript only`}}
async function aiDirectorStatusV5(){try{directorStatusV5=await api('/ai/status');directorStatusV5.loaded=true}catch(e){directorStatusV5={providers:{},loaded:true,error:e.message||String(e)}}const select=$('directorProviderV5');if(select){const saved=localStorage.getItem('rambla-director-provider'),allowed=new Set(['manual','auto','gemini','groq']);if(allowed.has(saved))select.value=saved;else if(directorStatusV5.providers?.auto?.configured)select.value='auto';else if(directorStatusV5.providers?.gemini?.configured)select.value='gemini';else if(directorStatusV5.providers?.groq?.configured)select.value='groq'}syncDirectorControlsV5()}
async function runDirectorV5(){if(!state.pid||state.run)return;state.currentStageV12='director_api';workflowFailureV12=null;syncWorkflowStatusV12();const provider=$('directorProviderV5').value;if(provider==='manual')return;$('directorStateV5').className='directorStateV5 busy';$('directorStateV5').textContent=`Starting ${provider.toUpperCase()} Director…`;$('analysisDetails').open=true;try{const r=await api(`/projects/${state.pid}/director`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider})});if(r.status==='started')await watch(r.run_id);else await hydrate()}catch(e){$('directorStateV5').className='directorStateV5';$('directorStateV5').textContent=e.message||String(e);throw e}finally{syncDirectorControlsV5()}}
const brollProviderLabelsV34={youtube:'YouTube',youtube_shorts:'Shorts',pexels:'Pexels',envato:'Envato',web_video:'Web'};
function searchedBrollProvidersV34(){const found=new Set();for(const c of state.data.chunks||[])for(const a of c.retrieval_diagnostics?.video_attempts||[]){const p=String(a.provider||'').toLowerCase();if(p in brollProviderLabelsV34)found.add(p)}return found}
function renderBrollProgressV34(r){const wrap=$('brollProgressV34');if(!wrap)return;const active=r?.stage_type==='videos'&&r.status==='RUNNING',terminal=r?.stage_type==='videos'&&['SUCCEEDED','FAILED','CANCELLED'].includes(r.status);if(!active&&!terminal)return;wrap.hidden=false;$('brollProgressBarV34').value=Number(r.total_progress||0);$('brollProgressLabelV34').textContent=active?`${Math.round(r.total_progress||0)}% · ${r.last_message||'Ricerca in corso'}`:r.status==='SUCCEEDED'?'Ricerca B-roll completata':r.last_message||r.status;const done=searchedBrollProvidersV34();$('brollSourceChecksV34').innerHTML=Object.entries(brollProviderLabelsV34).map(([key,label])=>`<span class="${done.has(key)?'done':''}">${done.has(key)?'✓':'○'} ${label}</span>`).join('')}
function renderDirectorProgressV34(r){const wrap=$('directorProgressV34');if(!wrap||r?.stage_type!=='director_api')return;wrap.hidden=false;const value=Number(r.total_progress||0);$('directorProgressBarV34').value=value;$('directorProgressLabelV34').textContent=r.status==='RUNNING'?`${Math.round(value)}% · ${r.last_message||'Creazione piano in corso'}`:r.status==='SUCCEEDED'?'✓ Piano completato':r.last_message||r.status}
function socialBackendLabelV2(value){return value==='playwright'?'Playwright':value==='chromium_dom'?'Edge/Chrome headless':'unavailable'}
function socialProviderStateV2(name,row){const profile=row?.profile_ready?'PROFILE SAVED':'NO PROFILE',ready=row?.search_ready?`search ready via ${socialBackendLabelV2(row.search_backend)}`:'search unavailable';return `${name}: ${profile} · ${ready}`}
async function socialStatusV2(){try{const s=await api('/social/status'),p=s.providers||{};const badges=$('socialBadgesV6');if(badges)badges.innerHTML=['tiktok','instagram'].map(k=>`<span class="connectionV6 ${p[k]?.connection_ready?'ready':''}">${p[k]?.connection_ready?'✓':'○'} ${k==='tiktok'?'TikTok':'Instagram'} · ${p[k]?.connection_ready?'Connected':'Not verified'}</span>`).join('');$('tiktokLoginV2').textContent=`TIKTOK LOGIN${p.tiktok?.profile_ready?' · PROFILE SAVED':''}`;$('instagramLoginV2').textContent=`INSTAGRAM LOGIN${p.instagram?.profile_ready?' · PROFILE SAVED':''}`;$('envatoLoginV2').textContent='ENVATO · APRI ACCESSO';$('socialLoginStateV2').textContent=`${socialProviderStateV2('TikTok',p.tiktok)} · ${socialProviderStateV2('Instagram',p.instagram)} · Envato: login e download ufficiale nel Chrome personale · PROFILE SAVED means the local RAMBLA browser profile exists; it does not verify login.`}catch(e){$('socialLoginStateV2').textContent=e.message||String(e)}}
async function socialLoginV2(provider){const buttons={tiktok:$('tiktokLoginV2'),instagram:$('instagramLoginV2'),envato:$('envatoLoginV2')},button=buttons[provider];button.disabled=true;try{const opened=await api(`/social/${provider}/login`,{method:'POST'});$('socialLoginStateV2').textContent=opened.session==='normal_chrome'?`${provider} aperto in una nuova finestra del profilo Chrome attivo.`:`${provider} browser aperto.`;setTimeout(()=>socialStatusV2(),1800)}catch(e){$('socialLoginStateV2').textContent=e.message||String(e)}finally{button.disabled=false}}
function latestSocialAttemptV2(chunk,provider){const rows=(chunk?.retrieval_diagnostics?.video_attempts||[]).filter(a=>String(a.provider||'').toLowerCase()===provider);return rows.length?rows[rows.length-1]:null}
function socialEmptyMessageV2(chunk,provider){const a=latestSocialAttemptV2(chunk,provider);const label=provider==='youtube_shorts'?'YouTube Shorts':provider==='web_video'?'Web / News':provider[0].toUpperCase()+provider.slice(1);if(!a){const busy=typeof searchesV9!=='undefined'&&(searchesV9.get(galleryKeyV9(provider))||searchesV9.get(galleryKeyV9(provider,'*')))?.busy;return busy?`${label} · ricerca in corso; in attesa della risposta del provider.`:`No ${label} search attempt recorded for this beat yet.`;}const hits=a.hits==null?'unknown':Number(a.hits),query=a.query?` · query: ${a.query}`:'',state=a.browser_state?` · ${a.browser_state}`:'',detail=a.browser_error_detail?`: ${a.browser_error_detail}`:'';if(a.browser_error)return `${label} authenticated search failed: ${a.browser_error}${detail}${a.fallback_used?' · public fallback: '+(a.fallback_attempt?.error_detail||a.fallback_attempt?.error||'completed'):''} · ${hits} results${state}${query}`;if(a.error)return `${label} search failed: ${a.error} · ${hits} results${query}`;const rejected=(chunk.retrieval_diagnostics?.video_rejections||[]).filter(r=>(r.source||r.provider)===provider),count=new Set(rejected.map(r=>r.id||r.source_url)).size;const reasons=[...new Set(rejected.flatMap(r=>r.quality_reasons||[]))];if(Number(hits)>0)return `${label} · ${hits} risultati grezzi nell'ultima query · 0 card disponibili. ${count?`${count} candidati scartati nelle ricerche registrate: ${reasons.slice(0,3).join('; ')}.`:'Risultati non ancora disponibili come card; consulta la diagnostica di elaborazione.'}${query}`;return `${label} searched · ${hits} results${a.fallback_used?' · public fallback used':''}${state}${query}`}
function socialStateV2(a){if(a.preview_status==='manual'||(!a.preview_url&&a.selectable===false))return 'MANUAL';if(a.preview_status==='ready'&&a.selectable!==false)return 'CLIP READY';return 'PREVIEW'}
function installSocialMediaV8(node,a){
 if(node.dataset.mediaV8)return;node.dataset.mediaV8='1';
 const copy=node.querySelector('.copy'),status=document.createElement('span');status.className='socialMediaStatusV8';
 status.textContent=(a.shot_id?'Shot '+a.shot_id.split('_').pop()+' · ':'')+(a.selectable?'Clip verificata':'Fonte da verificare');copy.appendChild(status);
 const button=document.createElement('button');button.textContent='Video completo';copy.appendChild(button);
 const pid=state.pid, asset=encodeURIComponent(a.asset_id),base=`/projects/${pid}/social-media/${asset}`;
 button.onclick=async e=>{e.stopPropagation();button.disabled=true;status.textContent='Preparazione download…';try{const r=await api(base+'/full',{method:'POST'});let link=copy.querySelector('.fullDownloadV8');if(!link){link=document.createElement('a');link.className='fullDownloadV8';link.textContent='DOWNLOAD VIDEO';link.setAttribute('download','');copy.appendChild(link)}link.href=r.url;link.click();status.textContent='Video disponibile'}catch(e){status.textContent=e.message||'Download non disponibile'}finally{button.disabled=false}};
 const oldVideo=node.querySelector('video');if(oldVideo){const img=document.createElement('img');img.src=a.poster_url;oldVideo.pause();oldVideo.removeAttribute('src');oldVideo.load();oldVideo.replaceWith(img)}
 let timer,inside=false,loading=false,attempted=false,gifUrl=null;
 const poster=node.querySelector(':scope>img')?.src;
 node.addEventListener('mouseenter',()=>{inside=true;timer=setTimeout(async()=>{
  const current=node.querySelector(':scope>img');if(gifUrl){if(current)current.src=gifUrl;return}if(loading||attempted)return;loading=true;attempted=true;status.textContent='Preparazione GIF panoramica…';
  try{const r=await api(base+'/hover',{method:'POST'});if(!node.isConnected)return;gifUrl=r.url;let img=node.querySelector(':scope>img');if(!img){img=document.createElement('img');node.insertBefore(img,copy)}if(inside)img.src=gifUrl;node.querySelector('.socialMissingV7')?.remove();node.classList.remove('noCoverV7');status.textContent='6 momenti del video · rilevanza da verificare'}catch(e){status.textContent=e.message||'GIF non disponibile'}finally{loading=false}
 },400)});
 node.addEventListener('mouseleave',()=>{inside=false;clearTimeout(timer);const img=node.querySelector(':scope>img');if(img&&poster)img.src=poster});
}
function decorateSocialCardsV2(chunk){for(const id of ['verticalVideos','tiktokVideosV2','instagramVideosV2','webNewsVideosV2','envatoVideosV2']){const container=$(id);if(!container)continue;container.querySelectorAll('.card').forEach(node=>{const a=(chunk.assets||[]).find(x=>x.asset_id===node.dataset.a);if(!a)return;if(a.provider==='envato')installEnvatoDownloadV29(node,a);const stateLabel=socialStateV2(a),copy=node.querySelector('.copy'),badge=document.createElement('span');if(['tiktok','instagram','youtube_shorts'].includes(a.provider)){node.classList.add('portraitSocialV6');installSocialMediaV8(node,a);const title=copy?.querySelector('b');if(title){let text=(a.title||a.provider).split(/\s+#| creato da | created by /i)[0].trim();title.textContent=text.length>100?text.slice(0,97)+'…':text;}if(a.download_url&&!copy.querySelector('.downloadV6')){const download=document.createElement('a');download.className='downloadV6';download.href=a.download_url;download.textContent='Clip selezionata'+(a.source_end_seconds!=null&&a.source_start_seconds!=null?' · '+(a.source_end_seconds-a.source_start_seconds).toFixed(1)+' s':'');download.setAttribute('download','');copy.appendChild(download)}}badge.className=`socialStateV2 ${stateLabel==='CLIP READY'?'ready':stateLabel==='MANUAL'?'manual':'preview'}`;badge.textContent=stateLabel;const head=copy?.querySelector('div');if(head&&!head.querySelector('.socialStateV2'))head.appendChild(badge);const link=copy?.querySelector('a');if(link){link.textContent='Apri fonte ↗';link.classList.add('sourceButtonV9')};if(stateLabel==='MANUAL'&&node.classList.contains('portraitSocialV6')){node.classList.add('noCoverV7');if(!node.querySelector('.socialMissingV7')){const missing=document.createElement('div');missing.className='socialMissingV7';missing.textContent='Anteprima non disponibile';node.insertBefore(missing,copy)}}else if(stateLabel==='MANUAL'){const img=node.querySelector('img');if(img)img.src='data:image/svg+xml;charset=utf-8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22640%22 height=%22360%22%3E%3Crect width=%22100%25%22 height=%22100%25%22 fill=%22%23202b37%22/%3E%3Ctext x=%2250%25%22 y=%2250%25%22 fill=%22%2394a3b8%22 font-size=%2226%22 text-anchor=%22middle%22 dominant-baseline=%22middle%22%3EOPEN SOURCE%3C/text%3E%3C/svg%3E'}})}}
function installEnvatoDownloadV29(node,a){if(node.dataset.envatoDownloadV29)return;node.dataset.envatoDownloadV29='1';const copy=node.querySelector('.copy'),status=document.createElement('span');status.className='envatoDownloadStateV29';const button=document.createElement('button');button.className='envatoDownloadV29';button.textContent=a.clip_verified?'PRONTA ✓':'SCARICA DA ENVATO';button.disabled=!!a.clip_verified;copy.appendChild(button);copy.appendChild(status);button.onclick=async event=>{event.stopPropagation();button.disabled=true;status.textContent='Apro Envato nel tuo profilo Chrome…';try{const started=await api(`/projects/${state.pid}/envato/download/start`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({asset_id:a.asset_id})});if(!started.opened_in_chrome)throw Error('Chrome non ha confermato l’apertura di Envato');let attempts=0;const poll=async()=>{attempts++;try{const result=await api(`/projects/${state.pid}/envato/download/${started.token}`);if(result.status==='ready'){button.textContent='PRONTA ✓';button.disabled=true;node.classList.add('selectedMediaV27');status.textContent='Download associato · pronto per XML, DRA e Resolve';return}if(attempts>=300){button.disabled=false;status.textContent='Download non rilevato. Premi di nuovo per riprovare.';return}status.textContent='In attesa del download Envato dalla finestra Chrome…';setTimeout(poll,2000)}catch(error){button.disabled=false;status.textContent=error.message||String(error)}};setTimeout(poll,1200)}catch(error){button.disabled=false;status.textContent=error.message||String(error)}}}
function installProviderGalleriesV26(chunk){const providers={videos:'youtube',verticalVideos:'youtube_shorts',stockVideos:'pexels',envatoVideosV2:'envato',webNewsVideosV2:'web_video',tiktokVideosV2:'tiktok',instagramVideosV2:'instagram',images:'images'};for(const [id,provider] of Object.entries(providers))installGalleryV9(chunk,id,provider)}
function installSocialShelvesV2(){const chunk=activeChunkV2();if(!chunk)return;installProviderGalleriesV26(chunk);bindCardsV2(chunk);decorateSocialCardsV2(chunk)}
function envatoEmptyV5(chunk){const attempts=(chunk.retrieval_diagnostics?.video_attempts||[]).filter(a=>a.provider==='envato');if(!attempts.length)return 'Not searched yet for this beat.';return attempts.map(a=>`Envato ${a.error?'request failed':'searched'} · ${a.hits??'unknown'} results · query: ${a.query} · engine: ${a.engine||'unrecorded'} · parser: ${a.parser||'unrecorded'}${a.error?' · '+a.error:''}${a.cache_hit?' · cached':''}`).join(' | ')}
function installManagementV2(){syncWorkflowStatusV12();const chunk=activeChunkV2();for(const id of ['findVideos','findImages'])$(id).disabled=!state.data.editorial_plan_ready||!!state.run;$('cleanMediaV2').disabled=!state.pid||!state.data.editorial_plan_ready||!!state.run;$('findSocial').disabled=!state.data.editorial_plan_ready||!!state.run;syncDirectorControlsV5();const actions=$('beatActionsV2');if(chunk?.action==='BROLL'){actions.innerHTML=`<small>THIS BEAT</small><button id="newSearchV2" ${state.run?'disabled':''}>NEW SEARCH</button><button id="addResultsV2" ${state.run?'disabled':''}>ADD TIKTOK + IG</button><button id="cleanBeatV2" ${state.run?'disabled':''}>CLEAN MEDIA · QUESTA FRASE</button><label><input type="checkbox" id="socialQwenV2" ${localStorage.getItem('socialQwenV2')==='true'?'checked':''}> Verifica social con Qwen (GPU)</label><span id="beatResearchStateV2" class="beatResearchStateV2"></span>`;$('cleanBeatV2').onclick=()=>cleanBeatMediaV2(chunk.id);$('socialQwenV2').onchange=e=>localStorage.setItem('socialQwenV2',e.target.checked);$('newSearchV2').onclick=()=>researchBeatV2('replace');$('addResultsV2').onclick=()=>prepareSocialV5(chunk.id);installShelfExpansionV2(chunk,'images')}else{actions.innerHTML='';for(const id of Object.keys(shelfLimitsV2)){const b=document.getElementById(`moreV2-${id}`);if(b)b.remove()}}installSocialShelvesV2();if(chunk)bindCardsV2(chunk)}
function workflowKindV12(stage){const value=String(stage||'');if(value==='director_api')return 'director_api';if(value==='analyze')return 'analyze';if(value.includes('social'))return 'social';if(value.includes('image'))return 'images';if(value.includes('video')||value.includes('research'))return 'videos';return value}
const startStageBaseV12=startStage;startStage=async(stage)=>{state.currentStageV12=workflowKindV12(stage);workflowFailureV12=null;syncWorkflowStatusV12();return await startStageBaseV12(stage)};
const watchBaseV5=watch;watch=async(id)=>{await watchBaseV5(id);installManagementV2()};
const drawBaseV2=draw;draw=()=>{drawBaseV2();installManagementV2();document.querySelectorAll('[data-c]').forEach(b=>{const original=b.onclick;b.onclick=()=>{original();saveWorkspaceSessionV13()}})};
const projectNameInputV25=$('projectNameV25');projectNameInputV25.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();projectNameInputV25.blur()}else if(e.key==='Escape'){projectNameInputV25.value=state.project?.name||'New Reel';projectNameInputV25.blur()}};projectNameInputV25.onblur=saveProjectNameV25;syncProjectNameV25();
const ramblaRunProgressBaseV34=window.ramblaRunProgress;window.ramblaRunProgress=(r)=>{if(ramblaRunProgressBaseV34)ramblaRunProgressBaseV34(r);renderBrollProgressV34(r);renderDirectorProgressV34(r);syncWorkflowStatusV12()};
window.ramblaRunTerminal=(r)=>{const kind=workflowKindV12(r?.stage_type);workflowFailureV12=r?.status==='FAILED'?kind:null;state.currentStageV12='';syncDirectorControlsV5();finishSearchV9(r);installManagementV2();renderBrollProgressV34(r);renderDirectorProgressV34(r);socialStatusV2();syncDirectorControlsV5();if(r?.stage_type==='director_api'&&r.status!=='SUCCEEDED'){const s=$('directorStateV5');if(s){s.className='directorStateV5';s.textContent=`Director ${String(r.status||'FAILED').toLowerCase()} · ${r.last_message||'see Analysis Details'}`}}};const findVideosBaseV24=$('findVideos').onclick;$('findVideos').onclick=()=>{prepareBrollViewV24();$('brollProgressV34').hidden=false;$('brollProgressBarV34').value=0;$('brollProgressLabelV34').textContent='Avvio ricerca B-roll…';return findVideosBaseV24()};$('findSocial').onclick=()=>prepareSocialV5();$('generateDirectorV5').onclick=runDirectorV5;$('directorProviderV5').onchange=()=>{localStorage.setItem('rambla-director-provider',$('directorProviderV5').value);syncDirectorControlsV5()};$('projectsV2').onclick=async()=>{$('projectLibraryV2').showModal();await refreshProjectsV2()};$('closeProjectsV2').onclick=()=>$('projectLibraryV2').close();$('refreshProjectsV2').onclick=refreshProjectsV2;$('cleanMediaV2').onclick=cleanMediaV2;$('tiktokLoginV2').onclick=()=>socialLoginV2('tiktok');$('instagramLoginV2').onclick=()=>socialLoginV2('instagram');$('envatoLoginV2').onclick=()=>socialLoginV2('envato');socialStatusV2();aiDirectorStatusV5();
"""



def _organize_workflow(html: str) -> str:
    """Move existing controls, preserving IDs and event bindings."""
    def take(element_id: str, tag: str = "button") -> str:
        nonlocal html
        pattern = rf'<{tag}\b[^>]*\bid="{element_id}"[^>]*>.*?</{tag}>'
        found = re.search(pattern, html, re.S)
        if found is None:
            raise RuntimeError(f"Missing workflow control: {element_id}")
        html = html[:found.start()] + html[found.end():]
        return found.group()

    analyze = take("analyze")
    video, social, images = (take(key) for key in ("findVideos", "findSocial", "findImages"))
    logins = ''.join(take(key) for key in ("tiktokLoginV2", "instagramLoginV2", "envatoLoginV2"))
    login_status = take("socialLoginStateV2", "span")
    maintenance = take("cleanMediaV2")
    panel = (
        '<section class="panel workflowV5" id="mediaWorkflowV5" data-workflow-step-v42="6"><h2>6 · Find media</h2>'
        '<p class="muted">These searches cover all B-roll beats. Use the controls inside a beat to search only that beat.</p>'
        '<details class="toolsV5 providerLoginV29" id="socialConnectionsV5"><summary>LOGIN PROVIDER ESTERNI</summary>'
        f'<p class="muted">TikTok, Instagram ed Envato si aprono in una nuova finestra del profilo Chrome attivo. I download ufficiali Envato vengono associati automaticamente.</p><div class="row">{logins}</div>{login_status}</details>'
        '<div class="searchGroupsV5">'
        f'<div><b>Video sources</b><span id="videoCompleteV12" class="stepStatusV12" hidden></span>{video}<small>YouTube, Shorts, Pexels, Envato and web</small><div id="brollProgressV34" class="realProgressV34" hidden><progress id="brollProgressBarV34" max="100" value="0"></progress><span id="brollProgressLabelV34">Pronto</span><div id="brollSourceChecksV34" class="sourceChecksV34"></div></div></div>'
        f'<div><b>Social sources</b><span id="socialCompleteV12" class="stepStatusV12" hidden></span><div id="socialBadgesV6" class="row" aria-live="polite"></div>{social}<small>TikTok + Instagram only · adds results</small></div>'
        f'<div><b>Still images</b><span id="imagesCompleteV12" class="stepStatusV12" hidden></span>{images}<small>Photos matched to each shot</small></div></div>'
        f'<details class="toolsV5"><summary>Media maintenance</summary><div class="row">{maintenance}<small>Remove retrieved media while keeping the transcript and plan.</small></div></details></section>'
    )
    html = html.replace('<div class="grid"><aside class="rail">', panel + '<section class="panel workflowSceneHeaderV44" data-workflow-step-v42="7"><h2 id="sceneWorkspaceHeading">7 · Visual beats · testo e B-roll</h2></section><div class="grid"><aside class="rail">', 1)
    html = html.replace('<h2>Source</h2>', '<h2>1 · Source <span id="analysisCompleteV12" class="stepStatusV12" hidden></span></h2>', 1)
    html = html.replace('<details id="analysisDetails">', f'</section><section class="panel" data-workflow-step-v42="2"><h2>2 · Analysis</h2><div class="row">{analyze}</div><details id="analysisDetails">', 1)
    html = html.replace('<h2>Editorial Plan</h2>', '<h2>5 · Editorial plan <span id="planCompleteV12" class="stepStatusV12" hidden></span></h2>', 1)
    html = re.sub(r'(<section class="panel")(?=>\s*<h2>1 ·)', r'\1 data-workflow-step-v42="1"', html, count=1)
    html = re.sub(r'(<section class="panel")(?=>\s*<h2>5 ·)', r'\1 data-workflow-step-v42="5"', html, count=1)
    # Primary Director controls precede the optional manual import/export tools.
    pattern = r'<span class="directorV5">.*?<span id="directorStateV5".*?</span></span>'
    director = re.search(pattern, html, re.S)
    if director:
        controls = director.group()
        html = html.replace(controls, '', 1)
        html = html.replace('<div class="row"><button id="copyEditorial"', controls + '<details class="toolsV5"><summary>Manual plan · export / import</summary><div class="row"><button id="copyEditorial"', 1)
        html = html.replace('<span id="editorialStatus" class="muted">Analyze a reel first.</span></div></section>', '</div></details><span id="editorialStatus" class="muted">Analyze a reel first.</span></section>', 1)
        html = html.replace(controls, controls + '<div id="directorProgressV34" class="realProgressV34 directorProgressV34" hidden><progress id="directorProgressBarV34" max="100" value="0"></progress><span id="directorProgressLabelV34">Preparazione piano…</span></div>', 1)
    return html

def render_curation_page_v2(build_token: str | None = None) -> str:
    html = render_curation_page(build_token)
    wordmark = _brand_data_uri("rmbl_wordmark_white.png")
    mark = _brand_data_uri("rmbl_mark_white.png")
    html = re.sub(
        r'<h1>.*?</h1>',
        f'<h1 class="brandHeaderV41"><img class="brandWordmarkV41" src="{wordmark}" alt="RMBL"><span class="brandTextV41"><span class="brandProductV41">RMBL B ROLL</span><span class="releaseVersionV35">{RELEASE_VERSION}</span></span></h1><button id="searchSoftwareUpdate" class="ghost" type="button">SEARCH UPDATE</button>',
        html,
        count=1,
    )
    html = html + """<script>
    document.getElementById('searchSoftwareUpdate')?.addEventListener('click',async()=>{
      const b=document.getElementById('searchSoftwareUpdate');
      if(typeof state!=='undefined'&&state.run){alert('Attendi la fine della lavorazione prima di aggiornare.');return}
      b.disabled=true;try{
        const r=await fetch('/api/curation/software-update',{method:'POST',headers:{'X-RMBL-Update':'1'}});
        const j=await r.json();if(!r.ok)throw Error(j.detail||'Aggiornamento non disponibile');
        alert(j.message);
      }catch(e){alert(e.message)}finally{b.disabled=false}
    });
    </script>"""
    html = html.replace('<meta name="rambla-build"', f'<link rel="icon" type="image/png" href="{mark}"><meta name="rambla-build"', 1)
    html = html.replace('CURATION V1 · build', 'CURATION · build', 1)
    html = html.replace(
        '<h2 style="margin:0">Project</h2>',
        '<label class="projectTitleV25"><span>PROGETTO</span><input id="projectNameV25" class="projectNameV25" value="New Reel" maxlength="120" aria-label="Nome progetto" disabled></label>',
        1,
    )
    html = html.replace(
        '<button id="saveProject" class="ghost" disabled>SAVE PROJECT FILE</button>',
        '<button id="saveProject" class="ghost" disabled>SAVE PROJECT FILE</button><button id="projectsV2" class="ghost">PROJECTS</button>',
        1,
    )
    html = html.replace(
        '<button id="findVideos" disabled>FIND B-ROLL</button>',
        '<button id="findVideos" disabled>FIND B-ROLL</button><button id="findSocial" disabled>FIND SOCIAL</button>',
        1,
    )
    html = html.replace(
        '<button data-filter="all">All</button>',
        '<button data-filter="all">All</button><button data-filter="broll">B-ROLL SCENES</button>',
        1,
    )
    html = html.replace(
        "state.filter==='all'||(state.filter==='none'?status(c)==='NO BROLL':state.filter==='selected'?status(c)==='Selected':state.filter==='errors'?status(c)==='Error':status(c)==='Needs Choice')",
        "state.filter==='all'||(state.filter==='broll'?c.action==='BROLL':state.filter==='none'?status(c)==='NO BROLL':state.filter==='selected'?status(c)==='Selected':state.filter==='errors'?status(c)==='Error':status(c)==='Needs Choice')",
        1,
    )
    html = html.replace(
        '<button id="findImages" disabled>FIND IMAGES</button>',
        '<button id="findImages" disabled>FIND IMAGES</button><button id="cleanMediaV2" class="ghost" disabled>CLEAN MEDIA</button><button id="tiktokLoginV2" class="ghost">TIKTOK LOGIN</button><button id="instagramLoginV2" class="ghost">INSTAGRAM LOGIN</button><button id="envatoLoginV2" class="ghost">ENVATO LOGIN</button><span id="socialLoginStateV2" class="socialLoginStateV2"></span>',
        1,
    )
    html = html.replace(
        '<span id="guideStatus" class="muted">No source selected.</span>',
        '<span id="guideStatus" class="muted">No source selected.</span><span id="resolveArrivalV30" class="resolveArrivalV30" hidden></span>',
        1,
    )
    html = html.replace(
        '<section class="panel"><h2>Editorial Plan</h2><p class="muted">Export the transcript, plan with any external tool or manually, then import the JSON.</p>',
        TRANSCRIPT_INTENT_PANEL + '<section class="panel"><h2>Editorial Plan</h2><p class="muted">Choose the editorial engine. AUTO routes around provider limits; cloud Directors receive the full transcript only, never the source video.</p>',
        1,
    )
    html = html.replace(
        '<button id="importEditorial" disabled>IMPORT EDITORIAL PLAN</button><span id="editorialStatus" class="muted">Analyze a reel first.</span>',
        '<button id="importEditorial" disabled>IMPORT EDITORIAL PLAN</button><span id="editorialStatus" class="muted">Analyze a reel first.</span><span class="directorV5"><select id="directorProviderV5" aria-label="Editorial Director"><option value="manual">MANUAL / IMPORT</option><option value="auto">AUTO</option><option value="gemini">GEMINI API</option><option value="groq">GROQ API</option></select><button id="generateDirectorV5" class="ghost" disabled>GENERATE PLAN</button><button id="refreshPlanV18" class="ghost" hidden>REFRESH PLAN</button><span id="directorStateV5" class="directorStateV5">Checking API…</span></span>',
        1,
    )
    html = html.replace(
        '<section class="stage"><div id="active" class="muted">No project artifacts loaded.</div>',
        '<section class="stage"><div id="active" class="muted">No project artifacts loaded.</div><div id="beatActionsV2" class="managementV2"></div>',
        1,
    )
    html = html.replace('<h3>SOCIAL / SHORTS / REELS</h3>', '<h3>YOUTUBE SHORTS</h3>', 1)
    html = html.replace(
        '<div id="stockVideos" class="cards"></div><p id="providerWarnings" class="muted"></p>',
        '<div id="stockVideos" class="cards"></div><div class="shelfHead"><h3>ENVATO ELEMENTS</h3><small>Automatic public Envato catalog search. Use SCARICA DA ENVATO, complete the official Envato download in Chrome, then RAMBLA attaches the licensed file automatically.</small></div><div id="envatoVideosV2" class="cards"></div><p id="providerWarnings" class="muted"></p>',
        1,
    )
    html = html.replace(
        '<div id="verticalVideos" class="cards"></div>',
        '<div id="verticalVideos" class="cards"></div><div class="shelfHead"><h3>TIKTOK</h3><small>Authenticated TikTok search first; automatic clip when possible, otherwise preview/link.</small></div><div id="tiktokVideosV2" class="cards"></div><div class="shelfHead"><h3>INSTAGRAM REELS</h3><small>Authenticated Reels discovery with public-web fallback.</small></div><div id="instagramVideosV2" class="cards"></div><div class="shelfHead"><h3>WEB / NEWS VIDEO</h3><small>Current-event video sources can remain clickable even when automatic download is unavailable.</small></div><div id="webNewsVideosV2" class="cards"></div>',
        1,
    )
    html = _organize_workflow(html)
    from .cut_pass_ui import PANEL as CUT_PANEL, CSS as CUT_CSS, JS as CUT_JS
    from .magic_ui import PANEL as MAGIC_PANEL, CSS as MAGIC_CSS, JS as MAGIC_JS
    html = html.replace('<section class="panel transcriptWorkspaceV14"', MAGIC_PANEL + CUT_PANEL + '<section class="panel transcriptWorkspaceV14"', 1)
    html = html.replace('</style>', '</style>' + CUT_CSS + MAGIC_CSS, 1)
    html = html.replace('</style>', '</style>' + _MANAGEMENT_CSS + _WORKFLOW_ACCORDION_CSS + GALLERY_CSS + STUDIO_CSS + TRANSCRIPT_INTENT_CSS + TIMELINE_EXPORT_CSS + THEME_SETTINGS_CSS, 1)
    html = html.replace('</main><dialog id="lightbox">', TIMELINE_EXPORT_PANEL + THEME_SETTINGS_PANEL + '</main><dialog id="lightbox">', 1)
    html = html.replace('</main><dialog id="lightbox">', _PROJECT_DIALOG + '</main><dialog id="lightbox">', 1)
    needle = 'draw();restore()})();</script></html>'
    if needle not in html:
        raise RuntimeError('curation V1 bootstrap marker changed; management UI injection aborted')
    desktop_target_js = r"""
let desktopTargetRevision=0,desktopProjectSwitchBusy=false;
setInterval(async()=>{try{const target=await api('/desktop-target');if(!target.project_id)return;if(!target.revision||target.revision===desktopTargetRevision||desktopProjectSwitchBusy)return;const next=new URL(target.url||('/curation?project='+encodeURIComponent(target.project_id)),location.href);if(next.hostname!=='127.0.0.1')return;const versionChanged=next.searchParams.get('build')&&next.searchParams.get('build')!==new URL(location.href).searchParams.get('build');if(!(target.project_id!==state.pid||next.origin!==location.origin||versionChanged)){desktopTargetRevision=target.revision;return}await api(`/projects/${target.project_id}`);desktopTargetRevision=target.revision;desktopProjectSwitchBusy=true;if(state.pid){await saveWorkspaceSessionV13();await api(`/projects/${state.pid}/workspace-backup`,{method:'POST'})}location.replace(next.href)}catch(_){desktopProjectSwitchBusy=false}},900);
"""
    html = html.replace(needle, GALLERY_JS + _MANAGEMENT_JS + TRANSCRIPT_INTENT_JS + TIMELINE_EXPORT_JS + THEME_SETTINGS_JS + desktop_target_js + needle, 1)
    from .runtime_mode import current_mode
    runtime_mode = current_mode()
    if runtime_mode == "cloud":
        html = html.replace("let socialSearchScopeV5=null;", "window.RAMBLA_CLOUD_MODE=true;let socialSearchScopeV5=null;", 1)
        html = html.replace('<button id="path">Open Local Path</button>', '<button id="path" hidden>Open Local Path</button>', 1)
        html = html.replace('id="socialConnectionsV5"', 'id="socialConnectionsV5" hidden', 1)
        html = html.replace('id="socialQwenV2"', 'id="socialQwenV2" disabled', 1)
        html = html.replace('Verifica social con Qwen (GPU)', 'Cloud mode · local GPU disabled', 1)
        html = html.replace(
            'const payload={mode,providers,visual_verify:!!document.getElementById("socialQwenV2")?.checked,...options};',
            'const payload={mode,providers,visual_verify:false,...options};',
            1,
        )
        html = html.replace(
            '<button id="analyze" class="primary" disabled>ANALYZE</button>',
            '<button id="analyze" class="primary" disabled>ANALYZE</button><span class="badge">CLOUD · GPU FREE</span>',
            1,
        )
    elif runtime_mode == "desktop_api":
        html = html.replace('id="socialQwenV2"', 'id="socialQwenV2" disabled', 1)
        html = html.replace('Verifica social con Qwen (GPU)', 'Desktop API · local GPU disabled', 1)
        html = html.replace(
            'const payload={mode,providers,visual_verify:!!document.getElementById("socialQwenV2")?.checked,...options};',
            'const payload={mode,providers,visual_verify:false,...options};',
            1,
        )
        html = html.replace(
            '<button id="analyze" class="primary" disabled>ANALYZE</button>',
            '<button id="analyze" class="primary" disabled>ANALYZE</button><span class="badge">DESKTOP · GPU FREE</span>',
            1,
        )
    from .scene_workspace_ui import CSS as SCENE_CSS, JS as SCENE_JS
    html = html.replace('</main>', SCENE_CSS + '</main>', 1)
    html = html.replace(needle, SCENE_JS + _WORKFLOW_ACCORDION_JS + CUT_JS + MAGIC_JS + needle, 1)
    html = html.replace("filter:'all'", "filter:'broll'")
    html = html.replace('RAMBLA · B-ROLL', 'RMBL B ROLL').replace('RAMBLA - B-ROLL', 'RMBL B ROLL')
    html = re.sub(r'\bRAMBLA\b', 'RMBL B ROLL', html)
    from .diagnostics_ui import HTML as SUPPORT_HTML
    html += SUPPORT_HTML
    return html
