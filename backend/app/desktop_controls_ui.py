"""Settings UI and live worker monitoring for the installed desktop build."""
PANEL = """<dialog id="rmblSettings" style="background:#151d29;color:white;padding:24px;border:1px solid #526579;border-radius:12px;max-width:560px;width:90vw"><h2>IMPOSTAZIONI API</h2><p>Le credenziali rimangono sul PC. Groq viene verificata prima di salvarla.</p><div id="rmblProviderRows"></div><p id="rmblSettingsStatus" role="status"></p><button id="rmblCloseSettings">CHIUDI</button></dialog><div id="rmblSystemBar" style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;background:#101923;padding:10px;border-radius:8px;margin-top:10px"><span id="rmblSystemText">Stato del sistema…</span><button id="rmblStopAnalysis" type="button" style="background:#822a32;color:white" hidden>■ STOP ANALISI</button></div>"""
JS = r"""<script>
(function(){
const el=id=>document.getElementById(id);
const names={groq:'Groq · trascrizione',pexels:'Pexels · video stock',gemini:'Gemini · AI',google:'Google · immagini'};
let providers={},active=null,stopping=false,busy=false,allowAnalyzing=false;
function show(){if(!el('rmblSettings').open)el('rmblSettings').showModal()}
function status(msg){el('rmblSettingsStatus').textContent=msg}
async function api(url,options){
 const r=await fetch(url,options);let d={};try{d=await r.json()}catch(_){}
 if(!r.ok)throw Error(d.detail||('HTTP '+r.status));return d;
}
function draw(){
 for(const id of Object.keys(names)){const e=el('rmblProviderStatus-'+id);if(e)e.textContent=providers[id]?.configured?' · configurata':' · mancante'}
}
function rows(){
 el('rmblProviderRows').innerHTML=Object.entries(names).map(([id,name])=>
 '<div style="margin:12px 0;padding:8px;border:1px solid #304055;border-radius:8px"><b>'+name+'</b><span id="rmblProviderStatus-'+id+'"></span><div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px"><input id="rmblKey-'+id+'" type="password" autocomplete="new-password" placeholder="Chiave API" style="flex:1;min-width:130px"><button data-set="'+id+'">VERIFICA E SALVA</button><button data-del="'+id+'">RIMUOVI</button></div></div>').join('');
 el('rmblProviderRows').querySelectorAll('[data-set]').forEach(b=>b.onclick=async()=>{
 const id=b.dataset.set,key=el('rmblKey-'+id).value.trim();if(!key){status('Inserisci la chiave');return}
 b.disabled=true;status(id==='groq'?'Verifica della chiave Groq…':'Salvataggio…');
 try{await api('/api/curation/desktop-settings/'+id,{method:'PUT',headers:{'Content-Type':'application/json','X-RMBL-Settings':'1'},body:JSON.stringify({key})});
 el('rmblKey-'+id).value='';providers[id]={configured:true};draw();status(id==='groq'?'Groq verificato e salvato':'Chiave salvata (non verificata online)')}
 catch(e){status(String(e.message||e))}finally{b.disabled=false}
 });
 el('rmblProviderRows').querySelectorAll('[data-del]').forEach(b=>b.onclick=async()=>{
 const id=b.dataset.del;if(!confirm('Rimuovere la chiave '+id+'?'))return;
 try{await api('/api/curation/desktop-settings/'+id,{method:'DELETE',headers:{'X-RMBL-Settings':'1'}});
 providers[id]={configured:false};draw();status('Chiave rimossa')}
 catch(e){status(String(e.message||e))}
 });
}
async function refresh(){
 if(busy)return;busy=true;
 try{
 const pid=new URLSearchParams(location.search).get('project')||localStorage.getItem('rambla-project')||'';
 const d=await api('/api/curation/desktop-controls?project_id='+encodeURIComponent(pid));
 providers=d.providers||{};draw();active=(d.running||[])[0]||null;
 const m=d.resources||{},machine=m.available?'CPU '+m.cpu_percent+'% · RAM '+m.ram_percent+'% ('+m.ram_used_gb+'/'+m.ram_total_gb+' GB)':'CPU/RAM non disponibili';
 el('rmblSystemText').textContent=(active?active.stage_type+' '+active.total_progress+'% · '+active.last_message:'Nessuna analisi attiva')+' · '+machine;
 el('rmblStopAnalysis').hidden=!active;el('rmblStopAnalysis').disabled=stopping;
 }catch(e){el('rmblSystemText').textContent='Monitor non disponibile: '+e.message}
 finally{busy=false}
}
function init(){
 const update=el('searchSoftwareUpdate');
 if(update)update.insertAdjacentHTML('afterend','<button id="rmblOpenSettings" type="button">⚙ IMPOSTAZIONI</button>');
 el('rmblOpenSettings')?.addEventListener('click',show);
 el('rmblCloseSettings')?.addEventListener('click',()=>el('rmblSettings').close());
 el('rmblStopAnalysis')?.addEventListener('click',async()=>{
 if(!active||stopping)return;if(!confirm('Interrompere analisi e processi figli?'))return;
 stopping=true;el('rmblSystemText').textContent='Arresto in corso…';
 try{await api('/v1/debug/runs/'+encodeURIComponent(active.run_id)+'/cancel',{method:'POST'})}catch(e){el('rmblSystemText').textContent=e.message}
 finally{stopping=false;await refresh()}
 });
 el('analyze')?.addEventListener('click',async event=>{
 if(allowAnalyzing)return;
 event.preventDefault();event.stopImmediatePropagation();
 const button=el('analyze');button.disabled=true;
 try{
   await api('/api/curation/desktop-settings/groq/verify',{method:'POST',headers:{'X-RMBL-Settings':'1'}});
   allowAnalyzing=true;button.disabled=false;button.click();allowAnalyzing=false;
 }catch(e){
   allowAnalyzing=false;button.disabled=false;show();
   status('Impossibile avviare ANALIZZA: '+e.message+'. Inserisci una chiave valida.');
 }
 },true);
 rows();refresh();setInterval(refresh,2000);
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
</script>"""
