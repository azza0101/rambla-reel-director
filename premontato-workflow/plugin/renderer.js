'use strict';
const $ = id => document.getElementById(id);
let scriptReady = false, mediaReady = false;
 $('version').textContent = `v${window.premontato.version}`;
function updateButton() { $('analyze').disabled = !(scriptReady && mediaReady); $('transcribe').disabled = !mediaReady; $('intellisearch').disabled = !mediaReady; }
function message(text) { $('message').textContent = text; }
function showError(error) { message(error.message || String(error)); }
window.premontato.onProgress(event => {
  $('analysis-progress').hidden = false;
  $('progress-label').textContent = event.label;
  $('progress-percent').textContent = `${event.percent}%`;
  $('progress-bar').value = event.percent;
  $('progress-bar').setAttribute('aria-valuenow', event.percent);
  [...$('progress-steps').children].forEach((item, index) => {
    item.classList.toggle('active', event.phaseIndex === index && !['complete', 'error'].includes(event.phase));
    item.classList.toggle('done', event.phase === 'complete' || index < event.phaseIndex);
    item.classList.toggle('error', event.phase === 'error' && index === event.phaseIndex);
  });
});

$('script').addEventListener('click', async () => { try { const result = await window.premontato.selectScript(); if (!result) return; scriptReady = true; $('script-status').textContent = `Copione: ${result.name}`; $('reviewed').checked = false; $('review').hidden = true; $('make-timeline').disabled = true; updateButton(); } catch (e) { showError(e); } });
$('update').addEventListener('click', async () => { const button = $('update'), status = $('update-status'); button.disabled = true; status.textContent = 'Controllo gli aggiornamenti su GitHub…'; try { const result = await window.premontato.update(); status.textContent = result.status === 'updated' ? `Premontato ${result.version} installato. Chiudi e riapri il pannello per caricare la nuova versione.` : result.status === 'current' ? `Premontato è aggiornato (${result.version}).` : 'Nessun aggiornamento pubblicato.'; } catch (error) { status.textContent = error.message || String(error); } finally { button.disabled = false; } });
let supportPreview = null;
$('debug').addEventListener('click', async () => { const button = $('debug'), status = $('support-status'); button.disabled = true; supportPreview = null; $('support-preview').textContent = ''; $('support-confirm').checked = false; $('support-send').disabled = true; status.textContent = 'Preparo una diagnostica filtrata…'; try { supportPreview = await window.premontato.prepareSupportReport(); $('support-preview').textContent = supportPreview.body; status.textContent = 'Anteprima pronta. Rileggila e conferma prima dell’invio.'; $('support-dialog').showModal(); } catch (error) { status.textContent = error.message || String(error); $('support-dialog').showModal(); } finally { button.disabled = false; } });
$('support-confirm').addEventListener('change', () => { $('support-send').disabled = !supportPreview || !$('support-confirm').checked; });
$('support-close').addEventListener('click', () => $('support-dialog').close());
$('support-dialog').addEventListener('click', event => { if (event.target === $('support-dialog')) $('support-dialog').close(); });
$('support-send').addEventListener('click', async () => { if (!supportPreview || !$('support-confirm').checked) return; const button = $('support-send'); button.disabled = true; $('support-status').textContent = 'Invio a GitHub…'; try { const result = await window.premontato.submitSupportReport({ reportId: supportPreview.reportId, confirmed: true }); $('support-status').textContent = 'Segnalazione inviata.'; const link = document.createElement('a'); link.href = result.url; link.target = '_blank'; link.rel = 'noreferrer'; link.textContent = result.url; $('support-status').append(document.createTextNode(' '), link); supportPreview = null; } catch (error) { $('support-status').textContent = error.message || String(error); button.disabled = false; } });
$('media').addEventListener('click', async () => { try { const items = await window.premontato.selectMedia(); mediaReady = items.length > 0; $('reviewed').checked = false; $('review').hidden = true; $('make-timeline').disabled = true; $('media-list').innerHTML = items.map(item => `<div>${escapeHtml(item.name)} <span class="pill">${item.duration_frames} frame</span>${item.people?.length ? `<small style="display:block;color:#91a0ad">Volti IntelliSearch nel clip: ${escapeHtml(item.people.join(', '))}</small>` : ''}</div>`).join('') || 'Nessuna clip selezionata in Resolve'; updateButton(); } catch (e) { showError(e); } });
$('transcribe').addEventListener('click', async () => { $('transcribe').disabled = true; message('Controllo trascrizioni Resolve…'); try { const result = await window.premontato.transcribeSelected(); message(`Trascrizione pronta: ${result.count} segmenti; ${result.results.filter(item => item.reused).length} clip riusate dalla cache Resolve.`); } catch (e) { showError(e); } finally { updateButton(); } });
$('intellisearch').addEventListener('click', async () => { $('intellisearch').disabled = true; message('Resolve sta analizzando le clip selezionate con IntelliSearch…'); try { const result = await window.premontato.analyzeIntellisearch(); message(`Richiesta IntelliSearch inviata a ${result.filter(item => item.ok).length}/${result.length} clip. I risultati restano nel catalogo Resolve.`); } catch (e) { showError(e); } finally { updateButton(); } });
$('analyze').addEventListener('click', async () => { $('analyze').disabled = true; $('cancel').hidden = false; $('analysis-progress').hidden = false; $('progress-bar').value = 0; $('progress-label').textContent = 'Avvio analisi…'; $('progress-percent').textContent = '0%'; message('Analisi locale del copione…'); try { const state = await window.premontato.analyze(); render(state); $('review').hidden = false; message('Analisi completata. Controlla i beat prima della timeline.'); } catch (e) { showError(e); } finally { $('cancel').hidden = true; updateButton(); } });
$('cancel').addEventListener('click', async () => { await window.premontato.cancelAnalysis(); $('cancel').hidden = true; message('Analisi annullata.'); });
$('make-timeline').addEventListener('click', async () => { try { const result = await window.premontato.createReviewTimeline({ confirmed: $('reviewed').checked }); const omitted = result.omitted ? `; ${result.omitted} dialoghi non abbinati omessi` : ''; message(`Creata ${result.timelineName} con ${result.included} battute abbinate${omitted}. Verifica i tagli e l'audio in Resolve.`); } catch (e) { showError(e); } });
 $('reviewed').addEventListener('change', () => render(window.__lastReviewState || {}));
$('confirm-takes').addEventListener('click', async () => { try { const fields = [...$('takes').querySelectorAll('[data-take]')]; const segments = fields.map(row => ({ ...JSON.parse(row.dataset.take), start_frame: Number(row.querySelector('[data-start]').value), end_frame: Number(row.querySelector('[data-end]').value) })); const state = await window.premontato.confirmTakes(segments); render(state); message('Confini confermati e montaggio ricalcolato.'); } catch (e) { showError(e); } });
function render(state) { window.__lastReviewState = state; renderPacing(state); const takes = state.analysis?.takes || []; const needsConfirm = takes.some(group => !group.confirmed); $('confirm-takes').hidden = !needsConfirm; $('takes').innerHTML = takes.map(group => `<h3>${escapeHtml(group.media_name)}</h3>${group.segments.map(segment => `<div class="take-row" data-take='${escapeHtml(JSON.stringify(segment))}'><span>Take ${segment.take_index}${segment.boundary_source === 'suggested' ? ' · suggerita' : ''}</span><label>In <input data-start type="number" min="0" max="${group.duration_frames}" value="${segment.start_frame}"></label><label>Out <input data-end type="number" min="1" max="${group.duration_frames}" value="${segment.end_frame}"></label><small>${segment.confirmed ? 'confermata' : 'da verificare'}</small></div>`).join('')}`).join(''); const selectedScene = state.analysis?.selectedScene; const beats = selectedScene?.beats || []; const decisions = new Map((state.analysis?.plan?.decisions || []).map(item => [item.beat_id, item])); $('beats').innerHTML = selectedScene ? `<div class="notice">Scena individuata dal parlato: ${escapeHtml(selectedScene.heading)} · confidenza ${Math.round((state.analysis.sceneSelection?.confidence || 0) * 100)}%</div>` : ''; $('beats').innerHTML += beats.map((beat, i) => { const edit = decisions.get(beat.beat_id); const framing = edit ? ` · ${escapeHtml(edit.shot_size)} (${Math.round((edit.shot_confidence || 0) * 100)}%)` : ''; const status = edit ? `Take ${edit.take_id}${framing} · ${edit.match_method === "semantic_context" ? `significato · indice ${(edit.semantic_score ?? 0).toFixed(2)}` : `copertura parole ${Math.round((edit.coverage ?? 1) * 100)}%`} · ${edit.alternatives.length} alternative${edit.warnings?.length ? ` · ${escapeHtml(edit.warnings.join("; "))}` : ""}` : beat.kind === 'dialogue' ? 'Nessuna battuta trovata nella trascrizione' : 'Indicazione di scena, non richiede corrispondenza audio'; return `<div class="beat"><span class="num">${String(i + 1).padStart(2, '0')}</span><span class="character">${escapeHtml(beat.character || beat.kind.toUpperCase())}</span><span>${escapeHtml(beat.text)}<small style="display:block;color:#91a0ad">${status}</small></span></div>`; }).join(''); const plan = state.analysis?.plan; const matched = plan?.decisions.length || 0, omitted = plan?.unmatched_beats.length || 0; $('make-timeline').disabled = !plan || !matched || !$('reviewed').checked; $('reviewed-copy').textContent = omitted ? `Ho controllato: crea una timeline di prova con ${matched} battute abbinate e ometti ${omitted} dialoghi senza corrispondenza.` : 'Ho controllato gli abbinamenti e voglio creare una timeline di prova.'; if (plan) { const summary = document.createElement('div'); summary.className = 'notice'; summary.textContent = `${matched} battute abbinate · ${omitted} dialoghi senza corrispondenza · ${state.analysis.shots.length} segmenti video analizzati`; $('beats').append(summary); } renderEditors(state, beats, decisions); for (const warning of state.analysis?.warnings || []) { const notice = document.createElement('div'); notice.className = 'notice'; notice.textContent = warning; $('beats').append(notice); } }
function escapeHtml(value) { return String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]); }
window.premontato.resolveSnapshot().then(snapshot => { $('host').textContent = `Resolve ${escapeHtml(snapshot.project)} · ${snapshot.fps} fps`; }).catch(error => { $('host').textContent = 'Resolve non collegato'; showError(error); });

function renderEditors(state, beats, decisions) {
  [...$('beats').querySelectorAll('.beat')].forEach((row, index) => {
    const edit=decisions.get(beats[index].beat_id); if(!edit) return;
    const panel=document.createElement('div'); panel.className='edit-controls';
    const labels={wide:'Larga / master',medium:'Media',close:'Stretta',detail:'Dettaglio',unknown:'Non determinata'};
    panel.innerHTML='<small>Parlato trovato: '+escapeHtml(edit.matched_text || '')+'</small><div class="actions">'+
      '<label>In <input data-in type="number" min="0" value="'+edit.start_frame+'"></label>'+
      '<label>Out <input data-out type="number" min="1" value="'+edit.end_frame+'"></label>'+
      '<label>Campo <select data-scale>'+Object.entries(labels).map(([key,label])=>'<option value="'+key+'" '+(key===edit.shot_size?'selected':'')+'>'+label+'</option>').join('')+'</select></label>'+
      '<button data-save>Applica correzioni</button></div>';
    panel.querySelector('[data-save]').addEventListener('click',async()=>{try {
      const next=await window.premontato.updateDecision({beat_id:edit.beat_id,start_frame:Number(panel.querySelector('[data-in]').value),end_frame:Number(panel.querySelector('[data-out]').value),shot_size:panel.querySelector('[data-scale]').value});
      $('reviewed').checked=false;render(next);message('Correzione salvata nel piano.');
    }catch(error){showError(error);}});
    if(edit.alternatives?.length){
      const select=document.createElement('select'); const placeholder=document.createElement('option');placeholder.textContent='Scegli una ripresa alternativa…';placeholder.value='';select.append(placeholder);
      edit.alternatives.forEach((alt,i)=>{const option=document.createElement('option');option.value=String(i);option.textContent=(state.media.find(m=>m.media_id===alt.media_id)?.name || alt.take_id)+' · '+alt.start_frame+'–'+alt.end_frame+' · '+Math.round((alt.coverage??alt.score)*100)+'%';select.append(option);});
      select.addEventListener('change',async()=>{if(select.value==='')return;try{const next=await window.premontato.updateDecision({beat_id:edit.beat_id,alternative_index:Number(select.value)});$('reviewed').checked=false;render(next);}catch(error){showError(error);}});panel.append(select);
    }
    const pauseLabel=document.createElement('label');pauseLabel.className='review-confirm';
    const pauseCheck=document.createElement('input');pauseCheck.type='checkbox';pauseCheck.checked=Boolean(edit.preserve_pause || edit.pacing?.protected_pause);
    pauseLabel.append(pauseCheck,document.createTextNode(' Conserva le pause di questa battuta'));
    pauseCheck.addEventListener('change',async()=>{try{const next=await window.premontato.updateDecision({beat_id:edit.beat_id,preserve_pause:pauseCheck.checked});$('reviewed').checked=false;render(next);}catch(error){showError(error);}});
    panel.append(pauseLabel);
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
 if(summary)$('pacing-status').textContent=options.enabled===false ? 'Regolazione silenzi disattivata.' : 'Audio misurato: '+summary.measured_media+' clip · '+summary.removed_seconds+' s rimossi · '+summary.protected_beats+' pause protette · '+summary.short_shot_exceptions+' inquadrature brevi da verificare'+(summary.unavailable_media.length?' · Audio non disponibile per '+summary.unavailable_media.length+' clip: pause conservate.':'');
}
$('pacing-apply').addEventListener('click',async()=>{
 const button=$('pacing-apply');button.disabled=true;
 try {const state=await window.premontato.setPacing({enabled:$('pacing-enabled').checked,max_pause_seconds:Number($('pacing-gap').value),minimum_shot_seconds:Number($('pacing-minimum').value),respect_script_pauses:$('pacing-script').checked});$('reviewed').checked=false;render(state);message(state.analysis?.plan?'Ritmo ricalcolato. Controlla gli intervalli e le eccezioni.':'Impostazioni pronte per la prossima analisi.');}
 catch(error){showError(error);}finally{button.disabled=false;}
});
