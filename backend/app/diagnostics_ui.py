"""Small support dialog shared with the existing product header."""
HTML = r"""
<style>
#rmblSupport{width:min(680px,calc(100vw - 48px));color:#eef2ff;background:#181d39;border:1px solid #626d9c;border-radius:18px;padding:22px;box-shadow:0 24px 90px #0009}
#rmblSupport::backdrop{background:#050916b8}#rmblSupport h2{margin:0 0 10px}#rmblSupport p{font-size:13px;line-height:1.5;color:#c7cde5}
#rmblSupport label{display:flex;align-items:center;gap:10px;margin:16px 0}#rmblSupport input{width:auto}#rmblSupport pre{max-height:220px;overflow:auto;background:#0f1428;padding:12px;border-radius:10px;white-space:pre-wrap;font-size:11px}#rmblSupport .supportActions{display:flex;gap:8px;flex-wrap:wrap}#rmblSupport a{color:#d8ff5b}
</style>
<dialog id="rmblSupport" aria-labelledby="rmblSupportTitle">
<h2 id="rmblSupportTitle">Assistenza e diagnostica</h2>
<p>I report arrivano nel repository GitHub privato. Contengono versione, categoria di errore e riferimenti al codice. Non inviamo video, audio, trascrizioni, nomi dei progetti, percorsi personali o chiavi API.</p>
<label><input type="checkbox" id="rmblDiagnosticsAuto">Invia automaticamente i report tecnici, anche quelli locali in attesa</label>
<p id="rmblDiagnosticsStatus" role="status"></p><a id="rmblDiagnosticsIssue" target="_blank" rel="noopener" hidden>Apri segnalazione GitHub ↗</a>
<details><summary>Anteprima del report che verra inviato</summary><pre id="rmblDiagnosticsPreview">Nessun errore registrato.</pre></details>
<p>Serve un account GitHub autorizzato. Se l'invio fallisce, il report rimane sul PC. Le segnalazioni non avviano automaticamente una correzione.</p>
<div class="supportActions"><button id="rmblDiagnosticsSend">INVIA DIAGNOSTICA</button><button id="rmblDiagnosticsCopy" class="ghost">COPIA DEBUG</button><button id="rmblDiagnosticsLogin" class="ghost">COLLEGA GITHUB</button><button id="rmblDiagnosticsClose" class="ghost">CHIUDI</button></div>
</dialog>
<script>
(()=>{
 const button=document.createElement('button');button.type='button';button.className='ghost';button.id='rmblSupportOpen';button.textContent='ASSISTENZA';
 const update=document.getElementById('searchSoftwareUpdate');if(update)update.after(button);else document.querySelector('h1')?.after(button);
 const dialog=document.getElementById('rmblSupport'),auto=document.getElementById('rmblDiagnosticsAuto'),status=document.getElementById('rmblDiagnosticsStatus'),preview=document.getElementById('rmblDiagnosticsPreview'),link=document.getElementById('rmblDiagnosticsIssue');let row=null,timer=null;
 const labels={idle:'Nessun invio in corso.',sending:'Invio diagnostica a GitHub…',sent:'✓ Segnalazione ricevuta da GitHub.',github_unavailable:'Invio non riuscito: report conservato. Collega GitHub e riprova.',private_repo_required:'Invio bloccato: il repository deve essere privato.',daily_limit:'Limite giornaliero raggiunto: report conservati.',invalid_local_report:'Report locale non valido: invio bloccato.',local_storage_error:'Impossibile leggere o salvare la diagnostica locale.'};
 async function request(path,body){const r=await fetch('/api/curation/diagnostics'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-RMBL-Diagnostics':'1'},body:JSON.stringify(body)});const j=await r.json();if(!r.ok)throw Error(j.detail||'Diagnostica non disponibile');return j}
 function draw(j){row=j;auto.checked=j.settings.automatic;status.textContent=(labels[j.delivery_state]||'Report registrato sul PC.')+` · ${j.pending_count} in attesa`;preview.textContent=j.last_report?JSON.stringify(j.last_report,null,2):'Nessun errore registrato: INVIA DIAGNOSTICA inviera soltanto versione e informazioni tecniche di base.';link.hidden=!j.last_url;if(j.last_url)link.href=j.last_url}
 async function refresh(){try{draw(await request(''))}catch(e){status.textContent=e.message}}
 async function open(){await refresh();if(!dialog.open)dialog.showModal();clearInterval(timer);timer=setInterval(refresh,1500)}
 button.onclick=open;dialog.addEventListener('close',()=>{clearInterval(timer);timer=null});
 auto.onchange=async()=>{try{draw(await request('/settings',{automatic:auto.checked}))}catch(e){status.textContent=e.message}};
 document.getElementById('rmblDiagnosticsSend').onclick=async()=>{try{draw(await request('/send',{}))}catch(e){status.textContent=e.message}};
 document.getElementById('rmblDiagnosticsCopy').onclick=async()=>{try{await navigator.clipboard.writeText(JSON.stringify(row?.last_report||{status:'Nessun errore registrato'},null,2));status.textContent='✓ Report tecnico copiato.'}catch(e){status.textContent='Seleziona e copia il testo nell’anteprima.'}};
 document.getElementById('rmblDiagnosticsLogin').onclick=async()=>{try{const r=await request('/login',{});status.textContent=r.status==='configured'?'GitHub e gia preconfigurato. Premi INVIA DIAGNOSTICA.':'Completa l’accesso nella finestra GitHub, poi premi INVIA DIAGNOSTICA.'}catch(e){status.textContent=e.message}};
 document.getElementById('rmblDiagnosticsClose').onclick=async()=>{try{if(row&&!row.settings.choice_made)await request('/settings',{automatic:false})}catch(e){}dialog.close()};
 request('').then(j=>{draw(j);if(!j.settings.choice_made)open()}).catch(()=>{});
})();
</script>
"""
