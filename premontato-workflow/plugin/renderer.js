'use strict';
const $ = id => document.getElementById(id);
let scriptReady = false, mediaReady = false;
 if(/^\d+\.\d+\.\d+$/.test(window.premontato.version || ''))$('version').textContent = `v${window.premontato.version}`;
function updateButton() { $('analyze').disabled = !(scriptReady && mediaReady); $('transcribe').disabled = !mediaReady; $('intellisearch').disabled = !mediaReady; }
function message(text) { $('message').textContent = text; }
function showError(error) { message(error.message || String(error)); if(lastProgressEvent && !['complete','error','transcript-complete','awaiting-scene'].includes(lastProgressEvent.phase))showProgress({...lastProgressEvent,phase:'error',label:error.message || String(error)}); }
const phaseNames=['Copione','Scena','Inquadrature','Controllo visivo facoltativo','Confini take','Audio','Battute e parlante','Ritmo e reazioni'];
const phaseBounds=[0,12,24,62,68,81,89,95,100];
const phaseState=[]; let progressStarted=0,lastProgressEvent=null;
[...$('progress-steps').children].forEach((row,index)=>{
 row.innerHTML='<strong>'+phaseNames[index]+'</strong><small data-phase-detail>In attesa</small><progress max="100" value="0" aria-label="'+phaseNames[index]+'"></progress>';
});
function phaseClock(seconds){return Math.floor(seconds/60)+'m '+String(seconds%60).padStart(2,'0')+'s';}
function showProgress(event){
 if((event.phase==='preflight' || event.phase==='script' || event.phase==='transcript') && event.percent===0){phaseState.length=0;progressStarted=Date.now();}
 lastProgressEvent={...event,receivedAt:Date.now()};
 $('analysis-progress').hidden=false;$('progress-label').textContent=event.label;
 $('progress-percent').textContent=event.percent+'%';$('progress-bar').value=event.percent;
 $('progress-bar').setAttribute('aria-valuenow',event.percent);
 [...$('progress-steps').children].forEach((row,index)=>{
   const complete=event.phase==='complete' || index<event.phaseIndex || event.phase==='awaiting-scene' && phaseState[index]?.done;
   const active=index===event.phaseIndex && !['complete','error','awaiting-scene'].includes(event.phase);
   const failed=index===event.phaseIndex && event.phase==='error';
   row.classList.toggle('done',complete);row.classList.toggle('active',active);row.classList.toggle('error',failed);
   const detail=row.querySelector('[data-phase-detail]'),bar=row.querySelector('progress');
   if(complete){if(!phaseState[index]?.done)phaseState[index]={...(phaseState[index] || {}),done:true};detail.textContent=phaseState[index]?.skipped?'Facoltativa · su richiesta':'Completata'+(phaseState[index]?.label?' · '+phaseState[index].label:'');bar.value=phaseState[index]?.skipped?0:100;}
   else if(active){phaseState[index]={label:event.label,skipped:Boolean(event.skipped),startedAt:phaseState[index]?.startedAt || Date.now()};detail.textContent=event.label; if(event.total)bar.value=100*(event.current || 0)/event.total;else bar.removeAttribute('value');}
   else if(failed){detail.textContent=event.label;bar.value=0;}
   else{detail.textContent=event.phase==='awaiting-scene' && index===1?'Scegli le scene del copione':'In attesa';bar.value=0;}
 });
}
window.premontato.onProgress(showProgress);
setInterval(()=>{if(!lastProgressEvent || ['complete','error','transcript-complete','awaiting-scene'].includes(lastProgressEvent.phase))return;
 const now=Date.now(),elapsed=Math.round((now-progressStarted)/1000);$('progress-percent').textContent=lastProgressEvent.percent+'% · '+phaseClock(elapsed);
 const index=lastProgressEvent.phaseIndex,row=$('progress-steps').children[index];
 if(row && phaseState[index])row.querySelector('[data-phase-detail]').textContent=phaseState[index].label+' · '+phaseClock(Math.round((now-phaseState[index].startedAt)/1000));
},1000);

$('script').addEventListener('click', async () => { try { const result = await window.premontato.selectScript(); if (!result) return; scriptReady = true;renderScriptPages({scriptIsPdf:result.isPdf,scriptPages:null}); $('script-status').textContent = `Copione: ${result.name}`;  $('review').hidden = true; $('make-timeline').disabled = true; updateButton(); } catch (e) { showError(e); } });
const updateSteps=['Credenziale locale','Ricerca release Premontato','Manifest del pacchetto','Download','Verifica integrità','Salvataggio progetti','Installazione','Riapertura pannello'];
const updateStepIndexes={credential:0,check:1,manifest:2,download:3,verify:4,save:5,validate:6,extract:6,install:6,rollback:6,restart:7};
let updateStartedAt=0,updatePhaseStartedAt=0,updateLastAt=0,updateActiveIndex=0,updateRunning=false,updateDetail='',updateCompleted=new Set();
function updateClock(){
 if(!updateStartedAt)return;const now=Date.now();
 $('update-progress-clock').textContent='Tempo trascorso '+phaseClock(Math.floor((now-updateStartedAt)/1000))+(updateRunning?' · fase '+phaseClock(Math.floor((now-updatePhaseStartedAt)/1000)):'');
 $('update-progress-detail').textContent=updateDetail+(updateRunning && now-updateLastAt>=15000?' · Operazione ancora in corso, in attesa di risposta.':'');
}
function showUpdateProgress(event,reset=false){
 const now=Date.now(),index=updateStepIndexes[event.phase],terminal=['current','unpublished','error','restart-error'].includes(event.phase);
 if(reset || !updateStartedAt){updateStartedAt=now;updatePhaseStartedAt=now;updateCompleted=new Set();updateActiveIndex=0;}
 if(index!==undefined && index!==updateActiveIndex){updateCompleted.add(updateActiveIndex);updateActiveIndex=index;updatePhaseStartedAt=now;}
 updateRunning=!terminal;updateLastAt=now;
 const labels={credential:'Leggo la credenziale locale protetta',check:'Cerco le release Premontato su GitHub',manifest:'Leggo il manifest della nuova versione',download:'Scarico l’aggiornamento',verify:'Verifico l’integrità del pacchetto',save:'Salvo sessione Premontato e progetto Resolve',validate:'Controllo i file da installare',extract:'Estraggo i file',install:'Installazione · conferma Windows se richiesta',rollback:'Ripristino l’installazione precedente',restart:'Aggiornamento completato · riapro il pannello',current:'Premontato è già aggiornato',unpublished:'Nessun aggiornamento pubblicato',error:'Aggiornamento interrotto','restart-error':'Aggiornato, riapertura non riuscita'};
 $('update-progress').hidden=false;$('update-progress-label').textContent=labels[event.phase] || event.phase;
 if(Number.isFinite(event.percent)){$('update-progress-bar').value=event.percent;$('update-progress-percent').textContent=event.percent+'% della fase';}else{$('update-progress-bar').removeAttribute('value');$('update-progress-percent').textContent=terminal?'Terminato':'In corso';}
 updateDetail=event.error || event.detail || (event.received!==undefined?(event.received/1048576).toFixed(1)+(event.total>0?' / '+(event.total/1048576).toFixed(1):'')+' MB ricevuti':event.current!==undefined?event.current+' / '+event.total+' file':'');
 const list=$('update-progress-steps');list.replaceChildren();
 for(let i=0;i<updateSteps.length;i++){const row=document.createElement('li');let status=updateCompleted.has(i)?'Completata':i===updateActiveIndex?'In corso':'In attesa';if(terminal){if(i===updateActiveIndex)status=['error','restart-error'].includes(event.phase)?'Errore':'Completata';else if(!updateCompleted.has(i))status=['current','unpublished'].includes(event.phase)?'Non necessaria':'Non eseguita';}row.textContent=updateSteps[i]+' · '+status;row.dataset.state=status;list.append(row);}
 if(['error','restart-error'].includes(event.phase)){$('update').disabled=false;$('update-progress-percent').textContent='Errore';}
 updateClock();
}
setInterval(()=>{if(updateRunning)updateClock();},1000);
$('update').addEventListener('click',async()=>{
 const button=$('update');button.disabled=true;$('update-status').textContent='Controllo gli aggiornamenti…';
 showUpdateProgress({phase:'credential',percent:null,detail:'Preparo la ricerca degli aggiornamenti.'},true);$('update-progress').scrollIntoView({behavior:'smooth',block:'center'});
 let restarting=false;
 try{const result=await window.premontato.update({draft:capturePremontatoDraft()});restarting=Boolean(result.restarting);$('update-status').textContent=result.status==='updated'?(restarting?'Versione '+result.version+' installata. Riapertura automatica del pannello…':'Versione '+result.version+' installata: riapri il pannello.') : result.status==='current'?'Premontato è aggiornato ('+result.version+').':'Nessun aggiornamento pubblicato.';if(result.status!=='updated')showUpdateProgress({phase:result.status==='current'?'current':'unpublished',percent:100,detail:$('update-status').textContent});}
 catch(error){$('update-status').textContent=error.message || String(error);showUpdateProgress({phase:'error',percent:null,error:error.message || String(error)});}
 finally{button.disabled=restarting;}
});
window.premontato.onUpdateProgress?.(event=>showUpdateProgress(event));
let supportPreview = null;
$('debug').addEventListener('click', async () => { const button = $('debug'), status = $('support-status'); button.disabled = true; supportPreview = null; $('support-preview').textContent = ''; $('support-confirm').checked = false; $('support-send').disabled = true; status.textContent = 'Preparo una diagnostica filtrata…'; try { supportPreview = await window.premontato.prepareSupportReport(); $('support-preview').textContent = supportPreview.body; status.textContent = 'Anteprima pronta. Rileggila e conferma prima dell’invio.'; $('support-dialog').showModal(); } catch (error) { status.textContent = error.message || String(error); $('support-dialog').showModal(); } finally { button.disabled = false; } });
$('support-confirm').addEventListener('change', () => { $('support-send').disabled = !supportPreview || !$('support-confirm').checked; });
$('support-close').addEventListener('click', () => $('support-dialog').close());
$('support-dialog').addEventListener('click', event => { if (event.target === $('support-dialog')) $('support-dialog').close(); });
$('support-send').addEventListener('click', async () => { if (!supportPreview || !$('support-confirm').checked) return; const button = $('support-send'); button.disabled = true; $('support-status').textContent = 'Invio a GitHub…'; try { const result = await window.premontato.submitSupportReport({ reportId: supportPreview.reportId, confirmed: true }); $('support-status').textContent = 'Segnalazione inviata.'; const link = document.createElement('a'); link.href = result.url; link.target = '_blank'; link.rel = 'noreferrer'; link.textContent = result.url; $('support-status').append(document.createTextNode(' '), link); supportPreview = null; } catch (error) { $('support-status').textContent = error.message || String(error); button.disabled = false; } });
$('media').addEventListener('click', async () => { try { const items = await window.premontato.selectMedia(); mediaReady = items.length > 0;  $('review').hidden = true; $('make-timeline').disabled = true; $('media-list').innerHTML = items.map(item => `<div>${escapeHtml(item.name)} <span class="pill">${item.duration_frames} frame</span>${item.people?.length ? `<small>Volti IntelliSearch nel clip: ${escapeHtml(item.people.join(', '))}</small>` : ''}</div>`).join('') || 'Nessuna clip selezionata in Resolve'; updateButton(); await refreshConnection(); } catch (e) { showError(e); } });
$('transcribe').addEventListener('click', async () => { $('transcribe').disabled = true; message('Controllo trascrizioni Resolve…'); try { const result = await window.premontato.transcribeSelected(); message(`Trascrizione pronta: ${result.count} segmenti; ${result.results.filter(item => item.reused).length} clip riusate dalla cache Resolve.`); } catch (e) { showError(e); } finally { updateButton(); } });
$('intellisearch').addEventListener('click', async () => { $('intellisearch').disabled = true; message('Resolve sta analizzando le clip selezionate con IntelliSearch…'); try { const result = await window.premontato.analyzeIntellisearch(); message(`Richiesta IntelliSearch inviata a ${result.filter(item => item.ok).length}/${result.length} clip. I risultati restano nel catalogo Resolve.`); } catch (e) { showError(e); } finally { updateButton(); } });
$('analyze').addEventListener('click', async () => { $('analyze').disabled = true; $('cancel').hidden = false; $('analysis-progress').hidden = false; $('progress-bar').value = 0; visualNames={}; visualDirty=false; visualOverrides.clear(); showProgress({phase:'preflight',phaseIndex:-1,percent:0,label:'Verifico il progetto Resolve e preparo l’analisi…'}); message('Analisi locale del copione…'); try { const state = await window.premontato.analyze(); render(state); $('review').hidden = false; message(state.analysis?.selectedScene?'Analisi completata. Controlla i beat prima della timeline.':'Scegli le scene del copione per preparare il montaggio.'); } catch (e) { showError(e); } finally { $('cancel').hidden = true; updateButton(); } });
$('cancel').addEventListener('click', async () => { await window.premontato.cancelAnalysis(); $('cancel').hidden = true; message('Analisi annullata.'); });
$('make-timeline').addEventListener('click', async () => {
 const status=$('timeline-result');$('make-timeline').disabled=true;status.textContent='Creazione timeline in corso…';message(status.textContent);
 try { const result=await window.premontato.createReviewTimeline({confirmed:true});const omitted=result.omitted?'; '+result.omitted+' dialoghi non abbinati omessi':'';status.textContent='Creata '+result.timelineName+' con '+result.included+' battute abbinate'+omitted+'. Verifica i tagli e l’audio in Resolve.';message(status.textContent); }
 catch(error){status.textContent=error.message || String(error);showError(error);}
 finally{updateTimelineButton();}
});
$('confirm-takes').addEventListener('click', async () => { try { const fields = [...$('takes').querySelectorAll('[data-take]')]; const segments = fields.map(row => ({ ...JSON.parse(row.dataset.take), start_frame: Number(row.querySelector('[data-start]').value), end_frame: Number(row.querySelector('[data-end]').value) })); const state = await window.premontato.confirmTakes(segments); render(state); message('Confini confermati e montaggio ricalcolato.'); } catch (e) { showError(e); } });
function render(state){
 const previous=window.__lastReviewState;
 const pending=previous && directionsChanged(previous) ? captureDirections() : null;
 renderBase(state);
 if(pending){
   const ids=new Set((state.analysis?.parsedBeats || []).map(b=>b.beat_id));pending.markers=Object.fromEntries(Object.entries(pending.markers).filter(([id])=>ids.has(id)));
   renderDirections({...state,directions:pending});
   clearTimeout(draftTimer);draftTimer=setTimeout(async()=>{try{await window.premontato.saveDraft(capturePremontatoDraft());}catch(error){showError(error);}},0);
 }
 updateTimelineButton(state);
}
function renderBase(state) { renderScriptPages(state);renderSceneScope(state); window.__lastReviewState = state; renderGroq(state.groq); $('load-visual-review').disabled=!state.analysis;  window.__lastReviewState = state; renderPacing(state); renderDirections(state); renderVisualReview(state); const takes = state.analysis?.takes || []; const needsConfirm = takes.some(group => !group.confirmed); $('confirm-takes').hidden = !needsConfirm; $('takes').innerHTML = takes.map(group => `<h3>${escapeHtml(group.media_name)}</h3>${group.segments.map(segment => `<div class="take-row" data-take='${escapeHtml(JSON.stringify(segment))}'><span>Take ${escapeHtml(segment.take_index)}${segment.boundary_source === 'suggested' ? ' · suggerita' : ''}</span><label>In <input data-start type="number" min="0" max="${escapeHtml(group.duration_frames)}" value="${escapeHtml(segment.start_frame)}"></label><label>Out <input data-end type="number" min="1" max="${escapeHtml(group.duration_frames)}" value="${escapeHtml(segment.end_frame)}"></label><small>${segment.confirmed ? 'confermata' : 'da verificare'}</small></div>`).join('')}`).join(''); const selectedScene = state.analysis?.selectedScene; const beats = state.analysis?.plan?.review_beats || selectedScene?.beats || []; const decisions = new Map((state.analysis?.plan?.decisions || []).map(item => [item.decision_id || item.beat_id, item])); $('beats').innerHTML = selectedScene ? `<div class="notice">Scena individuata dal parlato: ${escapeHtml(selectedScene.heading)} · confidenza ${state.analysis.sceneSelection?.manual?'scelta manuale':Math.round((state.analysis.sceneSelection?.confidence || 0) * 100)+'%'}</div>` : ''; $('beats').innerHTML += beats.map((beat, i) => { const edit = decisions.get(beat.beat_id); const framing = edit ? ` · ${escapeHtml(edit.shot_size)} (${Math.round((edit.shot_confidence || 0) * 100)}%)` : ''; const status = edit ? `Visibilità parlante: ${edit.speaker_coverage === 'visible' ? (edit.speaker_coverage_source === 'audio_visual' ? 'stimata da audio/video' : 'confermata nelle still') : edit.speaker_coverage === 'absent' ? 'fuori campo: verifica' : 'da verificare'} · Take ${escapeHtml(edit.take_id)}${framing} · ${["semantic_context","groq_context"].includes(edit.match_method) ? `significato · indice ${(edit.semantic_score ?? edit.semantic ?? 0).toFixed(2)}` : `copertura parole ${Math.round((edit.coverage ?? 1) * 100)}%`} · ${edit.alternatives.length} alternative${edit.warnings?.length ? ` · ${escapeHtml(edit.warnings.join("; "))}` : ""}` : beat.kind === 'dialogue' ? 'Nessuna battuta trovata nella trascrizione' : 'Indicazione di scena, non richiede corrispondenza audio'; return `<div class="beat"><span class="num">${String(i + 1).padStart(2, '0')}</span><span class="character">${escapeHtml(beat.character || beat.kind.toUpperCase())}</span><span>${escapeHtml(beat.text)}<small>${status}</small></span></div>`; }).join(''); const plan = state.analysis?.plan; const matched = plan?.decisions.length || 0, omitted = plan?.unmatched_beats.length || 0; $('make-timeline').disabled = !plan || !matched || visualDirty || plan.visual_review_required; if (plan) { const summary = document.createElement('div'); summary.className = 'notice'; summary.textContent = `${matched} ${plan?.engine === "groq_staged_v1" ? "momenti dialogati" : "battute abbinate"} · ${omitted} dialoghi senza corrispondenza · ${state.analysis.shots.length} segmenti video analizzati`; $('beats').append(summary); } renderEditors(state, beats, decisions); updateTimelineButton(state); for (const warning of state.analysis?.warnings || []) { const notice = document.createElement('div'); notice.className = 'notice'; notice.textContent = warning; $('beats').append(notice); } }
function escapeHtml(value) { return String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]); }


function renderEditors(state, beats, decisions) {
  [...$('beats').querySelectorAll('.beat')].forEach((row, index) => {
    const edit=decisions.get(beats[index].beat_id); if(!edit) return;
    const panel=document.createElement('div'); panel.className='edit-controls';panel.dataset.beatId=edit.decision_id || edit.beat_id;
    const labels={wide:'Larga / master',medium:'Media',close:'Stretta',detail:'Dettaglio',unknown:'Non determinata'};
    panel.innerHTML='<small>Parlato trovato: '+escapeHtml(edit.matched_text || '')+'</small><div class="actions">'+
      '<label>In <input data-in type="number" min="0" value="'+escapeHtml(edit.start_frame)+'"></label>'+
      '<label>Out <input data-out type="number" min="1" value="'+escapeHtml(edit.end_frame)+'"></label>'+
      '<label>Campo <select data-scale>'+Object.entries(labels).map(([key,label])=>'<option value="'+key+'" '+(key===edit.shot_size?'selected':'')+'>'+label+'</option>').join('')+'</select></label>'+
      '<button data-save>Applica correzioni</button></div>';
    panel.querySelector('[data-save]').addEventListener('click',async()=>{try {
      const next=await window.premontato.updateDecision({beat_id:edit.beat_id,decision_id:edit.decision_id,start_frame:Number(panel.querySelector('[data-in]').value),end_frame:Number(panel.querySelector('[data-out]').value),shot_size:panel.querySelector('[data-scale]').value});
      render(next);message('Correzione salvata nel piano.');
    }catch(error){showError(error);}});
    if(edit.alternatives?.length){
      const select=document.createElement('select'); const placeholder=document.createElement('option');placeholder.textContent='Scegli una ripresa alternativa…';placeholder.value='';select.append(placeholder);
      edit.alternatives.forEach((alt,i)=>{const option=document.createElement('option');option.value=String(i);option.textContent=(state.media.find(m=>m.media_id===alt.media_id)?.name || alt.take_id)+' · '+alt.start_frame+'–'+alt.end_frame+' · '+Math.round((alt.coverage??alt.score)*100)+'%';select.append(option);});
      select.addEventListener('change',async()=>{if(select.value==='')return;try{const next=await window.premontato.updateDecision({beat_id:edit.beat_id,decision_id:edit.decision_id,alternative_index:Number(select.value)});render(next);}catch(error){showError(error);}});panel.append(select);
    }
    const pauseLabel=document.createElement('label');pauseLabel.className='review-confirm';
    const pauseCheck=document.createElement('input');pauseCheck.type='checkbox';pauseCheck.checked=Boolean(edit.preserve_pause || edit.pacing?.protected_pause);
    pauseLabel.append(pauseCheck,document.createTextNode(' Conserva le pause di questa battuta'));
    pauseCheck.addEventListener('change',async()=>{try{const next=await window.premontato.updateDecision({beat_id:edit.beat_id,decision_id:edit.decision_id,preserve_pause:pauseCheck.checked});render(next);}catch(error){showError(error);}});
    panel.append(pauseLabel);
    if(edit.opening_checked){const checked=document.createElement('small');checked.textContent='Attacco della battuta verificato nel contesto del copione';panel.append(checked);}
    if(edit.reaction_status){
      const reaction=edit.reaction_before || state.analysis.plan.decisions[state.analysis.plan.decisions.findIndex(d=>d.beat_id===edit.beat_id)-1]?.reaction_overlay,box=document.createElement('div');box.className='reaction-review';
      if(edit.reaction_status==='unavailable'){const note=document.createElement('small');note.textContent='Reazione non inserita: manca una copertura in ascolto verificata, oppure la battuta è stata modificata manualmente.';box.append(note);}
      else {
        const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.dataset.reaction='';check.checked=Boolean(reaction);label.className='review-confirm';
        label.append(check,document.createTextNode((reaction?.basis==='verified_listener'?' Reazione in ascolto prima della larga · audio della battuta precedente conservato':' Inserisci la reazione silenziosa prima della risposta')+(reaction?' · '+((reaction.end_frame-reaction.start_frame)/(state.analysis.plan.fps || 25)).toFixed(2)+' s':'')));box.append(label);
        if(reaction?.still){const figure=document.createElement('figure'),image=document.createElement('img'),caption=document.createElement('figcaption');image.src=safeStill(reaction.still.image);image.alt='Anteprima della stretta silenziosa di '+reaction.character;caption.textContent=reaction.character+' · frame '+reaction.still.frame+' · pausa audio verificata, senza parole trascritte';figure.append(image,caption);box.append(figure);}
        check.addEventListener('change',async()=>{try{const next=await window.premontato.updateDecision({beat_id:edit.beat_id,decision_id:edit.decision_id,reaction_enabled:check.checked});render(next);message('Scelta della reazione salvata nel piano.');}catch(error){showError(error);}});
      }panel.append(box);
    }
    if(edit.narrative_role && edit.narrative_role!=='free'){const narrative=document.createElement('small');narrative.textContent='Regia: '+(edit.narrative_role==='tension'?'tensione · stretta':'risoluzione · larga')+(edit.style_satisfied?' · copertura trovata':' · copertura richiesta non disponibile');panel.append(narrative);}
    if(edit.pacing){const info=document.createElement('small');info.textContent=(edit.pacing.duration_frames/(state.analysis?.plan?.fps || 25)).toFixed(2)+' s · '+(edit.source_ranges?.length || 1)+' intervalli'+(edit.pacing.short_exception?' · Inquadratura breve: eccezione da verificare':'')+(edit.pacing.protected_pause?' · Pausa protetta':'');panel.append(info);}
    row.lastElementChild.append(panel);
  });
}

function renderPacing(state) {
 const options=state.pacingSettings || {}; if(options.enabled!==undefined)$('pacing-enabled').checked=options.enabled;
 if(options.max_pause_seconds!==undefined)$('pacing-gap').value=options.max_pause_seconds;
 if(options.minimum_shot_seconds!==undefined)$('pacing-minimum').value=options.minimum_shot_seconds;
 if(options.respect_script_pauses!==undefined)$('pacing-script').checked=options.respect_script_pauses;
 const summary=state.analysis?.plan?.pacing_summary;
 if(summary)$('pacing-status').textContent=options.enabled===false ? 'Regolazione silenzi disattivata.' : 'Audio misurato: '+summary.measured_media+' clip · '+summary.removed_seconds+' s rimossi · '+summary.protected_beats+' pause protette · '+(summary.reaction_count || 0)+' reazioni · '+(summary.action_count || 0)+' raccordi d’azione · '+summary.short_shot_exceptions+' inquadrature brevi da verificare'+(summary.unavailable_media.length?' · Audio non disponibile per '+summary.unavailable_media.length+' clip: pause conservate.':'');
}
$('pacing-apply').addEventListener('click',async()=>{
 const button=$('pacing-apply');button.disabled=true;
 try {const state=await window.premontato.setPacing({enabled:$('pacing-enabled').checked,max_pause_seconds:Number($('pacing-gap').value),minimum_shot_seconds:Number($('pacing-minimum').value),respect_script_pauses:$('pacing-script').checked});render(state);message(state.analysis?.plan?'Ritmo ricalcolato. Controlla gli intervalli e le eccezioni.':'Impostazioni pronte per la prossima analisi.');}
 catch(error){showError(error);}finally{button.disabled=false;}
});

let visualReviewOpen=false;
let visualNames={},visualDirty=false;const visualOverrides=new Map();
function safeStill(value){return typeof value==='string' && value.length<500000 && /^data:image\/jpeg;base64,[A-Za-z0-9+/=]+$/.test(value) ? value : '';}
function previewImage(image,caption){
 const button=document.createElement('button');button.type='button';button.className='preview-image';button.setAttribute('aria-label','Ingrandisci: '+image.alt);button.append(image);
 button.addEventListener('click',()=>{$('still-image').src=image.src;$('still-image').alt=image.alt;$('still-caption').textContent=typeof caption==='function'?caption():caption;$('still-dialog').showModal();});return button;
}
$('still-close').addEventListener('click',()=>$('still-dialog').close());
$('still-dialog').addEventListener('click',event=>{if(event.target===$('still-dialog'))$('still-dialog').close();});
$('still-dialog').addEventListener('close',()=>{$('still-image').removeAttribute('src');});
function renderVisualReview(state){
 const review=state.analysis?.visualReview; syncVisualVisibility(state);
 if(!review)return;
 visualNames={...(review.personNames || {}),...visualNames};
 const cast=[...new Set((state.analysis.parsedBeats || []).filter(b=>b.kind==='dialogue').map(b=>b.character).filter(Boolean))];
 const people=new Map();for(const face of review.faces || [])if(face.person_id){if(!people.has(face.person_id))people.set(face.person_id,[]);people.get(face.person_id).push(face);}
 $('visual-people').replaceChildren();
 for(const [id,faces] of [...people.entries()].sort((a,b)=>b[1].length-a[1].length)){
  const card=document.createElement('div');card.className='person-card';
  const label=document.createElement('strong');label.textContent='Gruppo volti '+id.replace('person-','');card.append(label);
  const strip=document.createElement('div');strip.className='face-strip';
  for(const face of faces.slice(0,3)){const img=document.createElement('img');img.src=safeStill(face.thumbnail);img.alt='Volto suggerito nello stesso gruppo';strip.append(previewImage(img,()=> 'Gruppo volti '+id.replace('person-','')+' · '+(visualNames[id] || 'Personaggio da assegnare')+' · Più gruppi possono appartenere alla stessa persona.'));}card.append(strip);
  const select=document.createElement('select');select.dataset.person=id;
  for(const name of ['',...cast]){const option=document.createElement('option');option.value=name;option.textContent=name || 'Personaggio da assegnare';select.append(option);}select.value=visualNames[id] || '';
  select.addEventListener('change',()=>{captureVisualOverrides(review.confirmed);visualDirty=true;visualNames[id]=select.value;review.confirmed=false;if(state.analysis.plan)state.analysis.plan.visual_review_required=true;renderVisualIntervals(state,cast);$('visual-confirm').checked=false;$('visual-save').disabled=true;$('make-timeline').disabled=true;});card.append(select);$('visual-people').append(card);
 }
 $('visual-confirm').checked=false;$('visual-save').disabled=true;
 const unknown=(review.faces || []).filter(f=>!f.person_id).length;
 $('visual-status').textContent='La stessa persona può comparire in più gruppi. '+(review.confirmed?'Revisione confermata.':'Controllo facoltativo: '+review.intervals.length+' intervalli.')+' '+people.size+' gruppi proposti'+(unknown?' · '+unknown+' volti incerti o troppo piccoli':'')+(review.cache_hits?' · still riusate dalla cache per '+review.cache_hits+' clip':'')+(review.warnings?.length?' · '+review.warnings.join('; '):'');
 renderVisualIntervals(state,cast);
}
function captureVisualOverrides(force=false){
 for(const card of $('visual-intervals').querySelectorAll('[data-visual-segment]'))if(force || card.dataset.changed==='true')visualOverrides.set(card.dataset.visualSegment,{shot_size:card.querySelector('[data-visual-scale]').value,visible_subjects:[...card.querySelectorAll('[data-subject]:checked')].map(x=>x.value)});
}
function renderVisualIntervals(state,cast){
 const review=state.analysis.visualReview,byFace=new Map((review.faces || []).map(f=>[f.observation_id,f]));$('visual-intervals').replaceChildren();
 const clips=new Map();
 for(const interval of review.intervals){
  if(!clips.has(interval.media_id)){const detail=document.createElement('details');detail.open=true;const title=document.createElement('summary');title.textContent=state.media.find(m=>m.media_id===interval.media_id)?.name || interval.media_id;detail.append(title);$('visual-intervals').append(detail);clips.set(interval.media_id,detail);}
  const card=document.createElement('article');card.className='visual-card';card.dataset.visualSegment=interval.segment_id;
  const override=visualOverrides.get(interval.segment_id);if(override)card.dataset.changed='true';
  const title=document.createElement('h3');title.textContent='Frame '+interval.start_frame+'–'+interval.end_frame;card.append(title);
  const strip=document.createElement('div');strip.className='still-strip';const suggested=new Set();
  for(const still of interval.stills || []){
    const figure=document.createElement('figure'),img=document.createElement('img'),caption=document.createElement('figcaption');img.src=safeStill(still.image);img.alt='Inquadratura al frame '+still.frame;caption.textContent='Frame '+still.frame;
    const faces=(still.face_ids || []).map(id=>byFace.get(id)).filter(Boolean);
    for(const face of faces){const name=visualNames[face.person_id];if(name)suggested.add(name);caption.textContent+=' · Volto '+face.face_number+': '+(name || (face.person_id ? 'Gruppo '+face.person_id.replace('person-','') : 'incerto'));}
    figure.append(previewImage(img,()=>caption.textContent+' · Campo: '+(visualOverrides.get(interval.segment_id)?.shot_size || interval.shot_size)+' · Campione dell’intervallo, non dell’intera ripresa.'),caption);strip.append(figure);
  }card.append(strip);
  const select=document.createElement('select');select.dataset.visualScale='';select.setAttribute('aria-label','Scala inquadratura');
  for(const [value,label] of Object.entries({wide:'Larga / master',medium:'Media',close:'Stretta / primo piano',detail:'Dettaglio',unknown:'Non determinata'})){const option=document.createElement('option');option.value=value;option.textContent=label;select.append(option);}select.value=override?.shot_size || interval.shot_size;card.append(select);
  const subjects=override?.visible_subjects || (review.confirmed?interval.visible_subjects:[...suggested]);
  const checks=document.createElement('div');checks.className='subject-checks';
  for(const name of cast){const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.value=name;input.dataset.subject='';input.checked=subjects.includes(name);label.append(input,document.createTextNode(name));checks.append(label);}card.append(checks);
  const note=document.createElement('small');note.textContent='Personaggi visibili per tutto l’intervallo. Nessuna selezione = non determinato. Correggi i suggerimenti se il volto cambia o il gruppo è errato.';card.append(note);
  card.addEventListener('change',()=>{card.dataset.changed='true';visualDirty=true;captureVisualOverrides();$('visual-confirm').checked=false;$('visual-save').disabled=true;$('make-timeline').disabled=true;if(state.analysis.plan)state.analysis.plan.visual_review_required=true;});clips.get(interval.media_id).append(card);
 }
}
function syncVisualVisibility(state=window.__lastReviewState || {}){
 const open=Boolean(visualReviewOpen && state.analysis?.visualReview);
 $('visual-review').hidden=!open;
 const button=$('load-visual-review');button.textContent=open?'Chiudi controllo visivo facoltativo':'Apri controllo visivo facoltativo';button.setAttribute('aria-expanded',String(open));
 for(const [buttonId,panelId,label] of [['visual-faces-toggle','visual-people-panel','volti'],['visual-debug-toggle','visual-intervals','inquadrature']]){
  const expanded=!$(panelId).hidden;$(buttonId).textContent=(expanded?'Chiudi':'Apri')+' controllo '+label;$(buttonId).setAttribute('aria-expanded',String(expanded));
 }
}
async function toggleVisualReview(){
 if(visualReviewOpen){visualReviewOpen=false;syncVisualVisibility();return;}
 if(window.__lastReviewState?.analysis?.visualReview){visualReviewOpen=true;syncVisualVisibility();return;}
 const button=$('load-visual-review');button.disabled=true;
 try{const state=await window.premontato.loadVisualReview();visualReviewOpen=true;render(state);$('visual-controls').open=true;message('Controllo visivo pronto. Non serve assegnare nomi per creare il premontato.');}
 catch(error){showError(error);}finally{button.disabled=false;}
}
$('load-visual-review').addEventListener('click',toggleVisualReview);
$('visual-faces-toggle').addEventListener('click',()=>{const panel=$('visual-people-panel'),button=$('visual-faces-toggle');panel.hidden=!panel.hidden;button.setAttribute('aria-expanded',String(!panel.hidden));button.textContent=panel.hidden?'Apri controllo volti':'Chiudi controllo volti';});
$('visual-debug-toggle').addEventListener('click',()=>{const panel=$('visual-intervals'),button=$('visual-debug-toggle');panel.hidden=!panel.hidden;button.setAttribute('aria-expanded',String(!panel.hidden));button.textContent=panel.hidden?'Apri controllo inquadrature':'Chiudi controllo inquadrature';});
$('visual-confirm').addEventListener('change',()=>{$('visual-save').disabled=!$('visual-confirm').checked || !window.__lastReviewState?.analysis?.visualReview?.intervals?.length;});
$('visual-save').addEventListener('click',async()=>{
 const button=$('visual-save');button.disabled=true;$('visual-status').textContent='Ricalcolo usando le correzioni…';
 try{const intervals=[...$('visual-intervals').querySelectorAll('[data-visual-segment]')].map(card=>({segment_id:card.dataset.visualSegment,shot_size:card.querySelector('[data-visual-scale]').value,visible_subjects:[...card.querySelectorAll('[data-subject]:checked')].map(x=>x.value)}));
 const next=await window.premontato.confirmVisualReview({confirmed:$('visual-confirm').checked,intervals,person_names:visualNames});visualOverrides.clear();visualDirty=false;render(next);message('Inquadrature confermate. Controlla gli abbinamenti ricalcolati prima della timeline.');
 }catch(error){showError(error);$('visual-status').textContent=error.message || String(error);button.disabled=false;}
});

function hasPendingFormEdits(state=window.__lastReviewState || {},includeDirections=true){
 if(includeDirections && directionsChanged(state))return true;
 const decisions=new Map((state.analysis?.plan?.decisions || []).map(item=>[item.decision_id || item.beat_id,item]));
 for(const row of $('beats').querySelectorAll('[data-beat-id]')){const edit=decisions.get(row.dataset.beatId);if(edit && (Number(row.querySelector('[data-in]').value)!==edit.start_frame || Number(row.querySelector('[data-out]').value)!==edit.end_frame || row.querySelector('[data-scale]').value!==edit.shot_size))return true;}
 for(const row of $('takes').querySelectorAll('[data-take]')){const item=JSON.parse(row.dataset.take);if(Number(row.querySelector('[data-start]').value)!==item.start_frame || Number(row.querySelector('[data-end]').value)!==item.end_frame)return true;}
 const pacing=state.pacingSettings;if(pacing && (pacing.enabled!==$('pacing-enabled').checked || pacing.max_pause_seconds!==Number($('pacing-gap').value) || pacing.minimum_shot_seconds!==Number($('pacing-minimum').value) || pacing.respect_script_pauses!==$('pacing-script').checked))return true;
 return false;
}
function timelineBlockers({matched,visualPending,dirty,pending}){
 const result=[];
 if(!matched)result.push({message:'Nessun piano pronto: scegli le scene del copione oppure verifica gli abbinamenti.',target:'scene-scope'});
 if(visualPending || dirty)result.push({message:'Conferma campi e personaggi: controlla le still, spunta il controllo visivo e premi «Conferma e ricalcola il montaggio».',target:'visual-review'});
 if(pending)result.push({message:'Ci sono correzioni in bozza: applica le modifiche a take, battute, ritmo o direzioni.',target:'review'});
 return result;
}
function updateTimelineButton(state=window.__lastReviewState || {}){
 const plan=state.analysis?.plan,blockers=timelineBlockers({matched:plan?.decisions?.length,visualPending:Boolean(plan?.visual_review_required),dirty:visualDirty,pending:hasPendingFormEdits(state)});
 $('beat-review-title').textContent='Battute e scelte di montaggio'+(plan?' · '+(plan.decisions?.length || 0)+' abbinate · '+(plan.unmatched_beats?.length || 0)+' da verificare':'');
 $('make-timeline').disabled=blockers.length>0;
 const box=$('timeline-readiness');box.replaceChildren();
 if(!blockers.length){box.textContent='Pronto: puoi creare la nuova timeline di revisione.';return;}
 const heading=document.createElement('strong');heading.textContent='Prima di creare la timeline:';box.append(heading);
 for(const item of blockers){const row=document.createElement('div'),button=document.createElement('button');button.type='button';button.className='quiet';button.textContent=item.message;button.addEventListener('click',()=>{const target=$(item.target);if(item.target==='visual-review'){visualReviewOpen=true;syncVisualVisibility(state);$('visual-controls').open=true;}if(item.target==='beats')$('beat-review').open=true;if(item.target==='scene-scope')$('scene-scope-options').open=true;target.scrollIntoView({behavior:'smooth',block:'center'});const focus=target.matches('input,button')?target:target.querySelector('input,select,button');focus?.focus({preventScroll:true});});row.append(button);box.append(row);}
}
let draftTimer=null,restoringDraft=false;
function capturePremontatoDraft(){
 return {directions:captureDirections(),visual:{dirty:visualDirty,person_names:{...visualNames},intervals:[...$('visual-intervals').querySelectorAll('[data-visual-segment]')].map(card=>({segment_id:card.dataset.visualSegment,shot_size:card.querySelector('[data-visual-scale]').value,visible_subjects:[...card.querySelectorAll('[data-subject]:checked')].map(input=>input.value)}))},
 takes:[...$('takes').querySelectorAll('[data-take]')].map(row=>({take_id:JSON.parse(row.dataset.take).take_id,start_frame:row.querySelector('[data-start]').value,end_frame:row.querySelector('[data-end]').value})),
 beats:[...$('beats').querySelectorAll('[data-beat-id]')].map(row=>({beat_id:row.dataset.beatId,start:row.querySelector('[data-in]').value,end:row.querySelector('[data-out]').value,scale:row.querySelector('[data-scale]').value})),
 pacing:{enabled:$('pacing-enabled').checked,gap:$('pacing-gap').value,minimum:$('pacing-minimum').value,script:$('pacing-script').checked}};
}
window.capturePremontatoDraft=capturePremontatoDraft;
function showProjectStatus(value){
 if(!value)return;const time=value.lastAutosaveAt || value.lastSavedAt;
 $('project-status').textContent=value.name+(time?' · Salvato alle '+new Date(time).toLocaleTimeString('it-IT'):'')+(value.warning?' · '+value.warning:'')+(value.error?' · '+value.error:'');
 if(value.resolve)$('resolve-save-status').textContent=value.resolve.error?'Salvataggio Resolve: '+value.resolve.error:'Resolve salvato: '+value.resolve.name+' · '+new Date(value.resolve.savedAt).toLocaleTimeString('it-IT');
}
window.premontato.onProjectStatus?.(showProjectStatus);
function hydrateProject(state){
 scriptReady=Boolean(state.scriptName);mediaReady=Boolean(state.media?.length);$('script-status').textContent=state.scriptName?'Copione: '+state.scriptName:'Nessun copione scelto';
 $('media-list').innerHTML=(state.media || []).map(item=>'<div>'+escapeHtml(item.name)+' <span class="pill">'+item.duration_frames+' frame</span></div>').join('') || 'Nessuna clip selezionata';
 visualNames={};visualOverrides.clear();visualDirty=false;
 window.__lastReviewState=null;render(state);$('review').hidden=!state.analysis;updateButton();showProjectStatus(state.projectStatus);
 const draft=state.uiDraft;if(!draft)return;
 restoringDraft=true;
 try{
  if(draft.visual){visualNames={...draft.visual.person_names};visualDirty=Boolean(draft.visual.dirty);for(const item of draft.visual.intervals || [])visualOverrides.set(item.segment_id,item);if(state.analysis?.visualReview)renderVisualReview(state);if(visualDirty)$('make-timeline').disabled=true;}
  for(const row of $('takes').querySelectorAll('[data-take]')){const item=draft.takes?.find(x=>x.take_id===JSON.parse(row.dataset.take).take_id);if(item){row.querySelector('[data-start]').value=item.start_frame;row.querySelector('[data-end]').value=item.end_frame;}}
  for(const row of $('beats').querySelectorAll('[data-beat-id]')){const item=draft.beats?.find(x=>x.beat_id===row.dataset.beatId);if(item){row.querySelector('[data-in]').value=item.start;row.querySelector('[data-out]').value=item.end;row.querySelector('[data-scale]').value=item.scale;}}
  if(draft.directions)renderDirections({...state,directions:draft.directions});
  if(draft.pacing){$('pacing-enabled').checked=draft.pacing.enabled;$('pacing-gap').value=draft.pacing.gap;$('pacing-minimum').value=draft.pacing.minimum;$('pacing-script').checked=draft.pacing.script;}
 }finally{restoringDraft=false;updateTimelineButton(state);}
}
document.addEventListener('input',event=>{
 if(restoringDraft || !window.premontato.saveDraft || !event.target.matches('input,select,textarea') || event.target.closest('#support-dialog') || event.target.closest('#groq-settings') || ['visual-confirm'].includes(event.target.id))return;
 updateTimelineButton();
 clearTimeout(draftTimer);draftTimer=setTimeout(async()=>{try{await window.premontato.saveDraft(capturePremontatoDraft());}catch(error){if(!/Operazione già in corso/.test(error.message))$('project-status').textContent='Salvataggio bozza: '+error.message;}},900);
});
for(const [id,saveAs] of [['project-save',false],['project-save-as',true]])$(id).addEventListener('click',async()=>{const button=$(id);button.disabled=true;clearTimeout(draftTimer);try{const state=await window.premontato.saveProject({saveAs,draft:capturePremontatoDraft()});if(state){hydrateProject(state);message('Progetto Premontato salvato.');}}catch(error){showError(error);}finally{button.disabled=false;}});
$('project-open').addEventListener('click',async()=>{const button=$('project-open');button.disabled=true;clearTimeout(draftTimer);try{const state=await window.premontato.openProject({draft:capturePremontatoDraft()});if(state){hydrateProject(state);message('Progetto Premontato aperto. Le riprese restano nei percorsi originali.');}}catch(error){showError(error);}finally{button.disabled=false;}});

function captureDirections(){
 const markers={};for(const input of $('directions-beats').querySelectorAll('[data-direction-beat]'))if(input.value)markers[input.dataset.directionBeat]=input.value;
 return {profile:$('directions-profile').value,notes:$('directions-notes').value,markers};
}
function directionsChanged(state){
 const current=captureDirections(),saved=state.directions || {profile:'VIDEO COLICHE',notes:'',markers:{}};
 return current.profile!==saved.profile || current.notes!==saved.notes || JSON.stringify(Object.entries(current.markers).sort())!==JSON.stringify(Object.entries(saved.markers || {}).sort());
}
function renderDirections(state){
 const value=state.directions || {profile:'VIDEO COLICHE',notes:'',markers:{}};
 $('directions-profile').value=value.profile;$('directions-notes').value=value.notes;$('directions-beats').replaceChildren();
 for(const beat of state.analysis?.parsedBeats || [])if(beat.kind==='dialogue'){
   const row=document.createElement('label');row.className='direction-row';const text=document.createElement('span');text.textContent=(beat.character || '')+': '+beat.text;
   const select=document.createElement('select');select.dataset.directionBeat=beat.beat_id;select.setAttribute('aria-label','Direzione di '+beat.text);
   for(const [key,label] of Object.entries({'':'Prosegui','tension':'Inizio tensione','resolution':'Risoluzione → larga','free':'Libero'})){const option=document.createElement('option');option.value=key;option.textContent=label;select.append(option);}select.value=value.markers?.[beat.beat_id] || '';row.append(text,select);$('directions-beats').append(row);
 }
 $('directions-status').textContent=Object.keys(value.markers || {}).length+' indicazioni sulle battute · note conservate localmente';
}
$('directions-file').addEventListener('change',async()=>{try{
 const file=$('directions-file').files[0];if(!file)return;
 if(file.size>80000 || !/\.(txt|md)$/i.test(file.name))throw new Error('Carica un file .txt o .md fino a 80 KB');
 const text=await file.text();if(text.length>20000)throw new Error('Note troppo lunghe: massimo 20.000 caratteri');
 $('directions-notes').value=text;$('directions-notes').dispatchEvent(new Event('input',{bubbles:true}));$('directions-status').textContent='Note caricate in bozza: salva le direzioni per conservarle nel progetto.';
 }catch(error){showError(error);}finally{$('directions-file').value='';}});
$('directions-apply').addEventListener('click',async()=>{const button=$('directions-apply');button.disabled=true;try{
 if(visualDirty || hasPendingFormEdits(window.__lastReviewState || {},false))throw new Error('Applica prima le correzioni in bozza a take, clip, ritmo e revisione visiva. Le direzioni restano in bozza.');
 const state=await window.premontato.setDirections(captureDirections());render(state);message('Direzioni salvate. Controlla copertura, tensione e risoluzione nelle scelte ricalcolate.');
 }catch(error){showError(error);}finally{button.disabled=false;}});

async function refreshConnection(){
 const previous=$('host').textContent;$('host').textContent='Connessione Resolve…';
 try{
  const snapshot=await window.premontato.resolveSnapshot();
  $('host').textContent='Resolve '+snapshot.project+' · '+snapshot.fps+' fps';$('connection-status').textContent='';
  return snapshot;
 }catch(error){
  $('host').textContent=/Operazione già in corso/.test(error.message || '')?previous:'Resolve non collegato · Riprova';
  $('connection-status').textContent=error.message || String(error);throw error;
 }
}
$('host').addEventListener('click',async()=>{try{await refreshConnection();message('Collegamento Resolve ripristinato. Puoi usare le clip selezionate.');}catch(error){showError(error);}});

(async()=>{
 try{const state=await window.premontato.getReviewState();if(state)hydrateProject(state);}
 catch(error){showError(error);}
 try{await refreshConnection();}catch(error){showError(error);}
})();

function renderGroq(status=window.__lastReviewState?.groq){
 if(!status)return;const summary=window.__lastReviewState?.analysis?.plan?.planning_summary?.classification;
 $('groq-enabled').checked=status.enabled;
 $('groq-status').textContent=status.enabled && status.configured?'Groq attivo · '+status.model+(summary?' · '+summary.calls+' chiamate · '+summary.cache_hits+'/'+summary.clips+' clip da cache':''):status.configured?'Groq disattivato · motore locale':'Groq non configurato · motore locale';
}
$('groq-save').addEventListener('click',async()=>{
 const key=$('groq-key').value.trim(),button=$('groq-save');button.disabled=true;
 try{const state=await window.premontato.configureGroq({...(key?{key}:{}),enabled:$('groq-enabled').checked});$('groq-key').value='';hydrateProject(state);message('Impostazioni salvate. Rilancia l’analisi per applicare il motore scelto.');}
 catch(error){showError(error);}finally{$('groq-key').value='';button.disabled=false;}
});

function renderScriptPages(state){
 $('script-pages').hidden=!state.scriptIsPdf;
 $('script-page-start').value=state.scriptPages?.start || '';
 $('script-page-end').value=state.scriptPages?.end || '';
 $('script-pages-status').textContent=state.scriptPages?'Intervallo attivo: pagine '+state.scriptPages.start+'–'+state.scriptPages.end:'Riconoscimento automatico su tutto il copione';
}
$('script-pages-apply').addEventListener('click',async()=>{
 const start=$('script-page-start').value.trim(),end=$('script-page-end').value.trim(),button=$('script-pages-apply');button.disabled=true;
 try{const state=await window.premontato.setScriptPages({start:start===''?null:Number(start),end:end===''?null:Number(end)});hydrateProject(state);message('Intervallo del copione salvato. Premi Analizza: le analisi in cache saranno riutilizzate.');}
 catch(error){showError(error);}finally{button.disabled=false;}
});
function renderSceneScope(state){
 const analysis=state.analysis,scenes=analysis?.script?.scenes || [];
 $('scene-scope').hidden=!scenes.length;
 if(!scenes.length)return;
 const selected=analysis.selectedScene,ids=selected?.source_scene_ids || (selected?[selected.scene_id]:[]);
 $('scene-scope-status').textContent=selected?'Ambito individuato: '+selected.heading:'Il parlato corrisponde a più scene: seleziona una o più scene per proseguire.';
 $('scene-scope-options').open=!selected;
 $('scene-scope-list').replaceChildren();
 for(const [index,scene] of scenes.entries()){
  const row=document.createElement('label');row.className='direction-row';
  const check=document.createElement('input');check.type='checkbox';check.dataset.scopeScene=scene.scene_id;check.checked=ids.includes(scene.scene_id);
  const text=document.createElement('span'),preview=scene.beats.filter(beat=>beat.kind==='dialogue').slice(0,2).map(beat=>(beat.character || '')+': '+beat.text).join(' / ');
  text.textContent=(index+1)+'. '+scene.heading+' · '+(preview.slice(0,240) || 'Indicazioni di scena');
  row.append(check,text);$('scene-scope-list').append(row);
 }
}
$('scene-scope-apply').addEventListener('click',async()=>{
 const button=$('scene-scope-apply');button.disabled=true;
 try{const scene_ids=[...$('scene-scope-list').querySelectorAll('[data-scope-scene]:checked')].map(input=>input.dataset.scopeScene);
 if(!scene_ids.length)throw new Error('Seleziona almeno una scena del copione');
 const state=await window.premontato.selectScenes({scene_ids});visualReviewOpen=false;visualDirty=false;visualOverrides.clear();hydrateProject(state);message('Montaggio pronto sulle scene selezionate. Puoi creare la timeline.');}
 catch(error){showError(error);}finally{button.disabled=false;}
});
