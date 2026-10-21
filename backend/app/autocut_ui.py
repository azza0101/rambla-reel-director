"""A focused host of the existing Auto-Cut review component."""
from .cut_pass_ui import PANEL, CSS, JS
from .curation_theme import CSS as THEME
from .curation_reference_theme import CSS as REFERENCE
from .release_version import RELEASE_VERSION
from .diagnostics_ui import HTML as SUPPORT_HTML

BOOT = r'''const $=id=>document.getElementById(id);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state={pid:null,project:null,run:null};let integrationContext=null,integrationApplying=false;
function reportError(error){$('integrationStatus').textContent=error.message||String(error)}
async function api(path,options={}){const response=await fetch('/api/curation'+path,options);const data=await response.json();if(!response.ok)throw Error(data.detail||'Operazione non riuscita');return data}
async function integrationRequest(path,options={}){const response=await fetch('/autocut'+path,options);const data=await response.json();if(!response.ok)throw Error(data.detail||'Operazione non riuscita');return data}
function draw(){}
async function hydrate(){if(state.pid){state.project=await api('/projects/'+state.pid);draw()}}
'''
AFTER = r'''
const integrationDrawBase=drawCut;drawCut=function(){integrationDrawBase();$('cutConfirm').textContent='APPLICA CUT IN RESOLVE';$('cutConfirm').disabled=integrationApplying||cutBusy||!cutData?.plan||cutData?.job?.status==='running';$('cutEditStatus').textContent=cutEditMode?'Modifica attiva · le scelte si salvano automaticamente':'Revisione in lettura · attiva Modifica per cambiare i tagli'};
$('cutPassFold').open=true;
$('integrationImport').onclick=async()=>{
 try{
  if(!window.rmblAutoCut)throw Error('Apri questo pannello da Resolve → Workspace → Workflow Integrations → RMBL Auto-Cut');
  if(cutBusy||cutData?.job?.status==='running'||integrationApplying)throw Error('Attendi la fine dell’operazione in corso');
  $('integrationImport').disabled=true;$('integrationStatus').textContent='Leggo la timeline attiva…';
  const context=await window.rmblAutoCut.snapshot();
  const project=await integrationRequest('/source',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(context)});
  integrationContext=context;state.pid=project.project_id;state.project=project;
  $('integrationSource').textContent=context.project_name+' · '+context.timeline_name;
  $('integrationStatus').textContent='Sorgente collegata · premi AVVIA AUTO-CUT. La trascrizione usa il motore configurato.';
  draw();
 }catch(error){reportError(error)}finally{$('integrationImport').disabled=false}
};
$('cutConfirm').onclick=async()=>{
 if(!state.pid||!cutData?.plan||integrationApplying)return;
 try{
  if(cutRangeStart!==null)throw Error('Premi FINE SELEZIONE per salvare l’ultimo intervallo prima di applicare');
  const current=await window.rmblAutoCut.snapshot();
  if(!integrationContext||current.timeline_id!==integrationContext.timeline_id||current.project_name!==integrationContext.project_name||current.path!==integrationContext.path)throw Error('La timeline è cambiata: torna alla sorgente originale prima di applicare');
  if(!confirm('Creare una nuova timeline CUT con le scelte attuali? La timeline originale resta intatta.'))return;
  integrationApplying=true;$('cutPassPanel').inert=true;$('integrationImport').disabled=true;
  let job=await integrationRequest('/projects/'+state.pid+'/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:cutData.plan.revision})});
  while(job.status==='running'){
   $('integrationStatus').textContent=(job.progress||0)+'% · '+job.message;
   await new Promise(resolve=>setTimeout(resolve,700));job=await integrationRequest('/projects/'+state.pid+'/apply');
  }
  if(job.status!=='succeeded')throw Error(job.message);
  $('integrationStatus').textContent='✓ '+job.message+' · '+job.result.timeline_name;
 }catch(error){reportError(error)}finally{integrationApplying=false;$('cutPassPanel').inert=false;$('integrationImport').disabled=false;drawCut()}
};
$('integrationUpdate').onclick=async()=>{
 try{
  if(!window.rmblAutoCut?.update)throw Error('Riapri la finestra Auto-Cut per caricare il controllo aggiornamenti');
  if(cutBusy||cutData?.job?.status==='running'||integrationApplying||cutRangeStart!==null)throw Error('Termina l’operazione o FINE SELEZIONE prima di aggiornare');
  $('integrationUpdate').disabled=true;$('cutPassPanel').inert=true;$('integrationStatus').textContent='Controllo e ricarica aggiornamenti… Resolve resta aperto.';
  await window.rmblAutoCut.update();
 }catch(error){reportError(error);$('integrationUpdate').disabled=false;$('cutPassPanel').inert=false}
};
draw();
(async()=>{try{const saved=await integrationRequest('/session');if(saved.update)$('integrationStatus').textContent=(saved.update.status==='failed'?'Aggiornamento non riuscito · ':'')+saved.update.message;if(saved.project){state.pid=saved.project.project_id;state.project=saved.project;integrationContext=saved.context;$('integrationSource').textContent=saved.context.project_name+' · '+saved.context.timeline_name;if(!saved.update)$('integrationStatus').textContent='Sessione Auto-Cut ripristinata · scelte salvate conservate';draw()}}catch(error){reportError(error)}})();
'''


def render_autocut():
    panel=PANEL.replace('3 · Auto-cut','Revisione Auto-Cut')
    # The shared component references editorial-only controls; keep inert placeholders,
    # never the actual editorial UI or its scripts/routes.
    placeholders='<div hidden>'+''.join('<div id="'+key+'"></div>' for key in ['cutAutoCoverage','magicAutoCoverageBox','magicAutoCoverageStatus','magicAutoCoverageProgress','magicAutoCoverageDetail'])+'</div>'
    return ('<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;self&#39;; script-src &#39;self&#39; &#39;unsafe-inline&#39;; style-src &#39;self&#39; &#39;unsafe-inline&#39;; img-src &#39;self&#39; data:; media-src &#39;self&#39; blob:; connect-src &#39;self&#39;; object-src &#39;none&#39;; base-uri &#39;none&#39;">'
        '<title>RMBL Auto-Cut</title>'+THEME+CSS+REFERENCE+
        '<style>*{box-sizing:border-box}body{margin:0}main{max-width:1100px;padding:22px}header{display:flex;align-items:center;justify-content:space-between;gap:16px}h1{font-size:24px;margin:0}.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}button{color:var(--ink);border:1px solid var(--line);cursor:pointer}.muted,small{color:var(--muted)}#integrationStatus{line-height:1.6;overflow-wrap:anywhere}#cutConfirm{min-width:200px}#cutRevisionReport{display:none}#cutTakeDialog{max-width:calc(100vw - 32px)}[hidden]{display:none!important}</style>'
        '</head><body><main><header><div><small>RAMBLA · RESOLVE WORKFLOW</small><h1>Auto-Cut</h1></div><div class="row"><small>Auto-Cut 0.1.3 · motore '+RELEASE_VERSION+'</small><button id="integrationUpdate">AGGIORNA</button></div></header>'
        '<section class="panel"><div class="row"><button id="integrationImport" class="primary">USA VIDEO DELLA TIMELINE</button><b id="integrationSource">Nessuna sorgente collegata</b></div><p id="integrationStatus" role="status">Apri la timeline con il video completo. Nessun taglio viene applicato automaticamente.</p><small>Prima versione: una sola clip video integrale. Trascrizione e revisione usano le API già configurate.</small></section>'
        +panel+placeholders+'</main><script>'+BOOT+JS+AFTER+'</script>'+SUPPORT_HTML+'</body></html>')
