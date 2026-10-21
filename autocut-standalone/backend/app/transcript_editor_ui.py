"""Inline transcript editor, using canonical semantic segments within each beat."""
JS = r'''
let phraseEditTarget=null;
async function openPhraseEditor(){
 const c=activeChunkV2();if(!c||state.run)return;
 const data=await api(`/projects/${state.pid}/beats/${encodeURIComponent(c.id)}/transcript`);
 phraseEditTarget={project:state.pid,beat:c.id,expected:data.text};
 let dialog=document.getElementById('phraseEditDialog');if(!dialog){dialog=document.createElement('dialog');dialog.id='phraseEditDialog';dialog.style.cssText='width:min(720px,90vw);max-height:85vh;overflow:auto';document.body.appendChild(dialog)}
 dialog.innerHTML=`<h2>Modifica trascrizione</h2><p>Correggi il parlato. I tempi restano invariati. Il testo corretto verrà usato nelle esportazioni e nel prossimo piano editoriale.</p><p class="muted">Dopo il salvataggio, rigenera o importa il piano prima di nuove ricerche. I media già trovati restano disponibili.</p>${data.chunks.map(c=>`<label style="display:block;margin:16px 0">${esc(c.id)} · ${c.start}–${c.end} s<textarea data-transcript-id="${esc(c.id)}" style="display:block;width:100%;min-height:95px;margin-top:6px">${esc(c.text)}</textarea></label>`).join('')}<p id="phraseEditError" role="alert"></p><div class="row"><button id="phraseEditSave">SALVA CORREZIONI</button><button id="phraseEditCancel">ANNULLA</button></div>`;
 $('phraseEditCancel').onclick=()=>dialog.close();$('phraseEditSave').onclick=async()=>{const target=phraseEditTarget;if(target.project!==state.pid){dialog.close();return}const chunks=Object.fromEntries([...dialog.querySelectorAll('[data-transcript-id]')].map(e=>[e.dataset.transcriptId,e.value]));$('phraseEditSave').disabled=true;try{await api(`/projects/${target.project}/beats/${encodeURIComponent(target.beat)}/transcript`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({chunks,expected_text:target.expected})});await hydrate();const transcript=await api(`/projects/${state.pid}/transcript`);$('transcript').textContent=(transcript.segments||[]).map(s=>s.text).join(' ');dialog.close()}catch(e){$('phraseEditError').textContent=e.message||String(e)}finally{$('phraseEditSave').disabled=false}};dialog.showModal();
}
function installPhraseEditor(){
 if(activeChunkV2()){
  const button=document.createElement('button');button.textContent='MODIFICA TRASCRIZIONE';button.disabled=!!state.run;button.onclick=openPhraseEditor;$('active').prepend(button);
 }
 if(state.data.transcript_needs_plan){
  const notice=document.createElement('p');notice.setAttribute('role','status');notice.textContent='Trascrizione corretta. Rigenera o importa il piano editoriale prima di nuove ricerche.';notice.style.cssText='color:#ffe4a0;padding:12px;border:1px solid #b48b41;border-radius:10px';$('active').prepend(notice);
  for(const id of ['findVideos','findImages','findSocial','newSearchV2','addResultsV2']){const b=$(id);if(b)b.disabled=true}
 }
}
const drawBeforePhraseEditor=draw;draw=()=>{drawBeforePhraseEditor();installPhraseEditor()};
'''
