const RAMBLA_FOLDER_NAME = 'RAMBLA Review Bridge';
const RAMBLA_SCHEMA = 'rambla-transcript-review-1';
const RAMBLA_SUBMISSION_SCHEMA = 'rambla-transcript-review-submission-1';

function json_(value) {
  return ContentService.createTextOutput(JSON.stringify(value)).setMimeType(ContentService.MimeType.JSON);
}

function folder_() {
  const rows = DriveApp.getFoldersByName(RAMBLA_FOLDER_NAME);
  return rows.hasNext() ? rows.next() : DriveApp.createFolder(RAMBLA_FOLDER_NAME);
}

function record_(reviewId) {
  const fileId = PropertiesService.getScriptProperties().getProperty('review:' + reviewId);
  if (!fileId) throw new Error('Review not found');
  return JSON.parse(DriveApp.getFileById(fileId).getBlob().getDataAsString('UTF-8'));
}

function saveRecord_(record) {
  const props = PropertiesService.getScriptProperties();
  const key = 'review:' + record.review_id;
  const existing = props.getProperty(key);
  const body = JSON.stringify(record);
  if (existing) {
    DriveApp.getFileById(existing).setContent(body);
  } else {
    const file = folder_().createFile('review-' + record.review_id + '.json', body, MimeType.PLAIN_TEXT);
    props.setProperty(key, file.getId());
  }
}

function requireOwner_(body) {
  const expected = PropertiesService.getScriptProperties().getProperty('RAMBLA_OWNER_SECRET') || '';
  if (!expected || body.owner_secret !== expected) throw new Error('Owner authentication failed');
}

function doPost(e) {
  try {
    const body = JSON.parse((e.postData && e.postData.contents) || '{}');
    requireOwner_(body);
    if (body.action === 'publish') {
      if (!body.review_id || !body.reviewer_token || !body.payload || body.payload.schema_version !== RAMBLA_SCHEMA) {
        throw new Error('Invalid review payload');
      }
      const record = {
        review_id: String(body.review_id), reviewer_token: String(body.reviewer_token),
        payload: body.payload, submission: null, submitted_revision: 0,
        created_at: new Date().toISOString()
      };
      saveRecord_(record);
      const base = ScriptApp.getService().getUrl();
      return json_({ok: true, review_url: base + '?review=' + encodeURIComponent(record.review_id) + '&token=' + encodeURIComponent(record.reviewer_token)});
    }
    if (body.action === 'pull') {
      const record = record_(String(body.review_id || ''));
      return json_({ok: true, review_id: record.review_id, submitted_revision: record.submitted_revision || 0, submission: record.submission || null});
    }
    throw new Error('Unsupported action');
  } catch (error) {
    return json_({ok: false, error: String(error && error.message || error)});
  }
}

function loadReview(reviewId, token) {
  const record = record_(String(reviewId || ''));
  if (!token || String(token) !== record.reviewer_token) throw new Error('Link di revisione non valido');
  return record.payload;
}

function submitReview(reviewId, token, transcriptSignature, changes) {
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const record = record_(String(reviewId || ''));
    if (!token || String(token) !== record.reviewer_token) throw new Error('Link di revisione non valido');
    if (transcriptSignature !== record.payload.transcript_signature) throw new Error('La trascrizione \u00e8 cambiata: chiedi un nuovo link');
    const ids = record.payload.chunks.map(function(row) { return String(row.id); });
    if (!changes || Object.keys(changes).length !== ids.length || ids.some(function(id) { return !changes[id]; })) {
      throw new Error('Selezione incompleta');
    }
    record.submitted_revision = Number(record.submitted_revision || 0) + 1;
    record.submission = {
      schema_version: RAMBLA_SUBMISSION_SCHEMA,
      transcript_signature: transcriptSignature,
      changes: changes,
      submitted_at: new Date().toISOString()
    };
    saveRecord_(record);
    return {ok: true, submitted_revision: record.submitted_revision};
  } finally {
    lock.releaseLock();
  }
}

function doGet() {
  return HtmlService.createHtmlOutput(REVIEW_HTML).setTitle('RAMBLA \u00b7 Revisione trascrizione').setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

const REVIEW_HTML = `<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{color-scheme:dark;--bg:#111329;--panel:#222643;--line:#414967;--ink:#f5f6ff;--muted:#abb3d0;--violet:#6558cc;--cyan:#116f78;--gold:#f1b93e}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#2d3158,#111329 55%);color:var(--ink);font:15px/1.55 Inter,system-ui,sans-serif}.wrap{max-width:980px;margin:auto;padding:24px}.panel{background:rgba(34,38,67,.96);border:1px solid var(--line);border-radius:20px;padding:20px;box-shadow:0 24px 70px #07081766}h1{font-size:23px;margin:0 0 5px}p{color:var(--muted)}.tools{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0}button{border:1px solid #596383;border-radius:10px;background:#2d3354;color:var(--ink);padding:10px 13px;font-weight:800;cursor:pointer}button.active.coverage{background:var(--violet)}button.active.animation{background:var(--cyan)}button.active.highlight{background:#c79029;color:#171207}.transcript{max-height:62vh;overflow:auto;background:#171a31;border:1px solid var(--line);border-radius:14px;padding:14px}.chunk{padding:8px 3px;border-bottom:1px solid #343a57}.time{display:block;color:#8791b6;font-size:10px;margin-bottom:5px}.word{display:inline;padding:1px 0;margin:0;border:1px solid transparent;border-radius:3px;cursor:pointer;line-height:1.75}.word:hover{border-color:#9da6ff}.word.coverage{background:var(--violet)}.word.animation{background:var(--cyan)}.word.coverage.animation{background:linear-gradient(135deg,var(--violet) 0 48%,var(--cyan) 52%)}.word.highlight{box-shadow:inset 0 -3px 0 var(--gold)}.word.anchor{outline:2px solid white}.footer{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:16px}.send{background:#d7ff4f;color:#10131c;border-color:#d7ff4f}.status{color:var(--muted)}.ok{color:#8cf0a3}@media(max-width:600px){.wrap{padding:10px}.panel{padding:14px}.tools button{flex:1 1 145px}}
</style></head><body><main class="wrap"><section class="panel"><h1 id="title">RAMBLA &middot; Revisione trascrizione</h1><p>Seleziona Coperture o Animazioni cliccando la prima e l'ultima parola. Per le Parole evidenziate clicca ogni parola singolarmente.</p><div class="tools"><button data-mode="coverage" class="coverage">1 &middot; COPERTURE</button><button data-mode="animation" class="animation">2 &middot; ANIMAZIONI</button><button data-mode="highlight" class="highlight">3 &middot; PAROLE EVIDENZIATE</button><button id="undo">&#8630; UNDO</button><button id="redo">&#8631; REDO</button></div><div id="transcript" class="transcript"></div><div class="footer"><button id="send" class="send">INVIA MODIFICHE</button><span id="status" class="status">Caricamento...</span></div></section></main>
<script>
(function(){
  var review=null,token=null,doc=null,mode=null,anchor=null,history=[],future=[];
  var fields={coverage:'coverage_word_indices',animation:'animation_word_indices',highlight:'highlighted_word_indices'};
  function clone(){return JSON.parse(JSON.stringify(doc.intents))}
  function sync(){document.querySelectorAll('[data-mode]').forEach(function(b){b.classList.toggle('active',b.dataset.mode===mode)});document.getElementById('undo').disabled=!history.length;document.getElementById('redo').disabled=!future.length}
  function tokens(){var out=[];doc.chunks.forEach(function(chunk){chunk.words.forEach(function(word,index){out.push({chunk:chunk,index:index,word:word,global:out.length})})});return out}
  function render(){var root=document.getElementById('transcript');root.textContent='';tokens().forEach(function(item){var existing=root.querySelector('[data-chunk="'+CSS.escape(item.chunk.id)+'"]');if(!existing){existing=document.createElement('section');existing.className='chunk';existing.dataset.chunk=item.chunk.id;var time=document.createElement('small');time.className='time';time.textContent=Number(item.chunk.start).toFixed(1)+'-'+Number(item.chunk.end).toFixed(1)+' s';existing.appendChild(time);root.appendChild(existing)}var span=document.createElement('span');span.className='word';span.textContent=item.word.text;span.dataset.global=item.global;var row=doc.intents[item.chunk.id];Object.keys(fields).forEach(function(kind){if((row[fields[kind]]||[]).indexOf(item.index)>=0)span.classList.add(kind)});if(anchor===item.global)span.classList.add('anchor');span.onclick=function(){choose(item.global)};existing.appendChild(span);existing.appendChild(document.createTextNode(' '))});sync()}
  function choose(global){if(!mode){setStatus('Scegli prima un tipo di selezione.');return}var all=tokens(),item=all[global],field=fields[mode],row=doc.intents[item.chunk.id],before=clone();if(mode==='highlight'){var values=row[field]||[],at=values.indexOf(item.index);if(at>=0)values.splice(at,1);else values.push(item.index);values.sort(function(a,b){return a-b});history.push(before);future=[];render();return}if(anchor===null){anchor=global;setStatus("Ora clicca l'ultima parola.");render();return}var first=Math.min(anchor,global),last=Math.max(anchor,global),selected=all.slice(first,last+1),remove=selected.every(function(x){return (doc.intents[x.chunk.id][field]||[]).indexOf(x.index)>=0});selected.forEach(function(x){var values=doc.intents[x.chunk.id][field]||[],at=values.indexOf(x.index);if(remove&&at>=0)values.splice(at,1);if(!remove&&at<0)values.push(x.index);values.sort(function(a,b){return a-b})});anchor=null;history.push(before);future=[];render()}
  function restore(stack,destination){if(!stack.length)return;destination.push(clone());doc.intents=stack.pop();anchor=null;render()}
  function setStatus(text,ok){var node=document.getElementById('status');node.textContent=text;node.className=ok?'status ok':'status'}
  document.querySelectorAll('[data-mode]').forEach(function(b){b.onclick=function(){mode=mode===b.dataset.mode?null:b.dataset.mode;anchor=null;sync()}});document.getElementById('undo').onclick=function(){restore(history,future)};document.getElementById('redo').onclick=function(){restore(future,history)};
  document.addEventListener('keydown',function(e){if(!(e.ctrlKey||e.metaKey))return;if(e.key.toLowerCase()==='z'){e.preventDefault();restore(e.shiftKey?future:history,e.shiftKey?history:future)}else if(e.key.toLowerCase()==='y'){e.preventDefault();restore(future,history)}});
  document.getElementById('send').onclick=function(){var button=this;button.disabled=true;setStatus('Invio...');google.script.run.withSuccessHandler(function(){button.disabled=false;setStatus('[OK] Modifiche inviate. Puoi chiudere questa pagina.',true)}).withFailureHandler(function(error){button.disabled=false;setStatus(error.message||String(error))}).submitReview(review,token,doc.transcript_signature,doc.intents)};
  function boot(locationData){review=locationData&&locationData.parameter?locationData.parameter.review:null;token=locationData&&locationData.parameter?locationData.parameter.token:null;if(!review||!token){setStatus('Link non valido: usa il collegamento copiato da RAMBLA.');return}google.script.run.withSuccessHandler(function(value){doc=value;document.getElementById('title').textContent='Revisione - '+(doc.project_label||'RAMBLA');render();setStatus('Pronto. Le modifiche saranno inviate soltanto quando premi Invia.')}).withFailureHandler(function(error){setStatus(error.message||String(error))}).loadReview(review,token)}
  google.script.url.getLocation(boot);
})();
</script></body></html>`;
