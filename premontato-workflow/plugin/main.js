'use strict';
const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { assertTrusted, validateMediaRecords } = require('./ipc_security');
const { Session, prepareReviewTimeline } = require('./session');
const adapter = require('./resolve_adapter');
const updateManager = require('./updater');
const ID = 'com.rambla.premontato';
app.setPath('userData', path.join(app.getPath('appData'), 'RAMBLA', 'Premontato'));
let win, sdk, session, diagnostics, activeSupportReport, busy = false, shuttingDown=false, closing=false, updateRestartPending=false;
const page = pathToFileURL(path.join(__dirname, 'index.html')).href;

async function getSdk() {
  if (sdk) return sdk;
  try { sdk = require('./WorkflowIntegration.node'); if (!await sdk.InitializePromise(ID)) throw new Error('InitializePromise rifiutata'); return sdk; }
  catch (error) { throw new Error(`Bridge Workflow Integration non disponibile: ${error.message}`); }
}
function handle(name, fn) {
  ipcMain.handle(`premontato:${name}`, async (event, ...args) => {
    assertTrusted(event, win, page);
    if (updateRestartPending) throw new Error('Riavvio del pannello in corso');
    if (busy && name !== 'cancelAnalysis') throw new Error('Operazione già in corso');
    if (name !== 'cancelAnalysis') busy = true;
    try {
      let result=await fn(...args);
      if(['analyze','updateDecision','confirmVisualReview','setPacing','setDirections','confirmTakes','selectMedia','selectScript','transcribeSelected'].includes(name)){const pending=session.state.uiDraft?.directions;session.state.uiDraft=['updateDecision','confirmVisualReview','setPacing','confirmTakes'].includes(name) && pending ? {directions:pending} : null;}
      if(['selectScript','selectMedia','transcribeSelected','analyze','updateDecision','confirmVisualReview','setPacing','setDirections','confirmTakes','createReviewTimeline','saveDraft'].includes(name)){
        try{await session.saveAutosave();}catch(error){session.saveError='Salvataggio automatico non riuscito: '+error.message;}
        publishProjectStatus();if(result?.stage)result=session.getReviewState();
      }
      return result;
    }
    catch (error) {
      try { await diagnostics?.record('operation_failed', { operation: name, error }); } catch {}
      throw error;
    } finally { if (name !== 'cancelAnalysis') busy = false; }
  });
}
let resolveSaveStatus=null,lastUpdateEvent=null;
function publishProjectStatus(){win?.webContents.send('premontato:projectStatus',{...session.projectStatus(),resolve:resolveSaveStatus});}
function updateProgress(event){
 const now=Date.now();if(event.phase==='download' && lastUpdateEvent?.phase===event.phase && event.percent!==100 && now-lastUpdateEvent.at<150)return;
 lastUpdateEvent={...event,at:now};win?.webContents.send('premontato:updateProgress',event);
}
async function saveResolve(expectedProjectId){
 try{const saved=await adapter.saveCurrentProject(await getSdk(),expectedProjectId);resolveSaveStatus={...saved,error:null};publishProjectStatus();return saved;}
 catch(error){resolveSaveStatus={error:error.message};publishProjectStatus();throw error;}
}
async function start() {
  const root = app.getPath('userData');
  diagnostics = updateManager.createDiagnostics({ logPath: path.join(root, 'logs', 'premontato-diagnostics.jsonl'),
    appVersion: require('./package.json').version, platform: process.platform, release: require('node:os').release() });
  await diagnostics.record('application_started');
  const workerPath = path.join(__dirname, 'worker', 'protocol.py');
  session = new Session(root, workerPath);
  try{await session.restoreAutosave();}catch(error){session.saveError='Recupero automatico non riuscito: '+error.message;}
  win = new BrowserWindow({ width: 1080, height: 820, minWidth: 680, minHeight: 560, title: 'RAMBLA Premontato v'+require('./package.json').version,
    backgroundColor: '#111820', webPreferences: { additionalArguments:['--premontato-version='+require('./package.json').version], preload: path.join(__dirname, 'preload.js'), sandbox: true, contextIsolation: true, nodeIntegration: false } });
  win.setMenu(null); win.webContents.setWindowOpenHandler(() => ({ action: 'deny' })); win.webContents.on('will-navigate', e => e.preventDefault());
  win.webContents.session.setPermissionRequestHandler((_wc, _permission, callback) => callback(false));
  handle('resolveSnapshot', async () => { const result = await adapter.snapshot(await getSdk()); return { ...result, selected: result.selected.map(({ item, path: _mediaPath, ...record }) => record) }; });
  handle('selectScript', async () => { const result = await dialog.showOpenDialog(win, { properties: ['openFile'], filters: [{ name: 'Copione', extensions: ['txt', 'fountain', 'md', 'pdf'] }] }); return result.canceled ? null : session.setScript(result.filePaths[0]); });
  handle('selectMedia', async () => { const result = await adapter.snapshot(await getSdk()); const selected = result.selected.map(({ item, ...record }) => record); return session.setMedia(validateMediaRecords(selected), result); });
  handle('transcribeSelected', async () => {
    const before = await adapter.snapshot(await getSdk());
    session.assertContext(before);
    const results = await adapter.transcribeSelected(await getSdk(), event=>session.onProgress?.({phase:'transcript',phaseIndex:-1,percent:Math.round(event.current/event.total*100),label:'Trascrizione · '+event.name+' · '+event.current+'/'+event.total+(event.reused?' · cache Resolve':''),...event}));
    const resolveSnapshot = await adapter.snapshot(await getSdk());
    const sources = await adapter.getSelectedTranscriptions(await getSdk());
    const total = session.setTranscripts(sources, resolveSnapshot.fps, resolveSnapshot);
    session.onProgress?.({phase:'transcript-complete',phaseIndex:-1,percent:100,label:'Trascrizione pronta · '+total.count+' segmenti'});
    return { results, ...total };
  });
  handle('analyzeIntellisearch', async () => {
    const before = await adapter.snapshot(await getSdk());
    session.assertContext(before);
    return adapter.analyzeIntellisearchSelected(await getSdk(), { identifyFaces: true, isBetterMode: false });
  });
  handle('analyze', async () => { const current = await adapter.snapshot(await getSdk()); session.assertContext(current); await saveResolve(session.state.projectId).catch(()=>{}); return session.analyze(); });
  handle('cancelAnalysis', async () => session.cancelAnalysis());
  handle('getReviewState', async () => session.getReviewState());
  handle('saveDraft',async draft=>{session.setDraft(draft);return {saved:true};});
  handle('saveProject',async request=>{
    if(request?.draft)session.setDraft(request.draft);
    let file=session.projectFile;
    if(request?.saveAs || !file){const result=await dialog.showSaveDialog(win,{title:'Salva progetto Premontato',defaultPath:file || path.join(root,'projects','Scena.premontato.json'),filters:[{name:'Progetto Premontato',extensions:['json']}]});if(result.canceled || !result.filePath)return null;file=result.filePath;}
    await session.saveProject(file);await session.saveAutosave();
    try{await saveResolve(session.state.projectId);}catch{}
    publishProjectStatus();return session.getReviewState();
  });
  handle('openProject',async request=>{
    if(request?.draft)session.setDraft(request.draft);
    const result=await dialog.showOpenDialog(win,{title:'Apri progetto Premontato',defaultPath:path.join(root,'projects'),properties:['openFile'],filters:[{name:'Progetto Premontato',extensions:['json']}]});if(result.canceled)return null;
    if(session.state.script || session.state.media.length)await session.writeProject(path.join(root,'projects','recupero-'+Date.now()+'.premontato.json'));
    await session.loadProject(result.filePaths[0]);await session.saveAutosave();publishProjectStatus();return session.getReviewState();
  });
  handle('updateDecision', async request => { session.updateDecision(request); return session.applyPacing(); });
  handle('confirmVisualReview', async request => session.confirmVisualReview(request));
  handle('setDirections', async options => session.setDirections(options));
  handle('setPacing', async options => session.setPacing(options));
  handle('confirmTakes', async segments => session.confirmTakes(segments));
  handle('createReviewTimeline', async request => {
    await session.validateMediaUnchanged();
    await saveResolve(session.state.projectId);
    const plan = session.state.analysis?.plan;
    const review = prepareReviewTimeline(plan, request?.confirmed);
    const created = await adapter.createTimeline(await getSdk(), `PREMONTATO v${require('./package.json').version} - ${new Date().toISOString().replace(/\D/g, '').slice(0, 14)}`, review.decisions, session.state);
    try{await saveResolve(session.state.projectId);}catch{}
    return { ...created, included: review.decisions.length, omitted: review.omitted };
  });
  handle('update', async request => {
    if(request?.draft)session.setDraft(request.draft);
    updateProgress({phase:'check',percent:null});
    const credentialPath=updateManager.resolveGithubCredentialPath(process.env.PROGRAMDATA);
    if(!credentialPath)throw new Error('Credenziale GitHub RMBL non trovata: verifica l’installazione Auto-Cut.');
    let token=updateManager.loadProtectedToken(credentialPath),jobRoot=null;
    try{
      const update=await updateManager.findLatestUpdate(require('./package.json').version,token);
      if(update.status!=='available'){updateProgress({phase:'current',percent:100,version:update.version});return update;}
      if(!/(?:^|[\\/])electron(?:\.exe)?$/i.test(process.execPath))throw new Error('Aggiorna dal pannello Electron di Resolve per consentire il riavvio automatico');
      const fsp=require('node:fs/promises');await fsp.mkdir(path.join(root,'updates'),{recursive:true});jobRoot=await fsp.mkdtemp(path.join(root,'updates','job-'));
      const archivePath=path.join(jobRoot,update.manifest.archive);
      await updateManager.downloadVerifiedArchive(update,token,archivePath,undefined,updateProgress);token='';
      updateProgress({phase:'save',percent:null});await session.saveAutosave();await saveResolve();
      await session.shutdownWorker();updateProgress({phase:'install',percent:null});
      await updateManager.runUpdateInstaller({script:path.join(__dirname,'update.ps1'),pluginRoot:__dirname,archivePath,sha256:update.manifest.sha256,version:update.manifest.version,onProgress:updateProgress});
      updateRestartPending=true;updateProgress({phase:'restart',percent:100,version:update.manifest.version});
      setTimeout(()=>updateManager.restartPlugin(app,async()=>{await session.saveAutosave();await session.shutdownWorker();try{sdk?.CleanUp();}catch{}sdk=null;shuttingDown=true;}).catch(error=>{shuttingDown=false;updateRestartPending=false;updateProgress({phase:'restart-error',percent:null,error:error.message});}),1200);
      return {status:'updated',version:update.manifest.version,restarting:true};
    }catch(error){updateProgress({phase:'error',percent:null,error:error.message});throw error;}
    finally{token='';if(jobRoot)await require('node:fs/promises').rm(jobRoot,{recursive:true,force:true}).catch(()=>{});}
  });
  handle('prepareSupportReport', async () => {
    activeSupportReport = null;
    const status = await updateManager.checkGithubCli();
    if (!status.ready) throw new Error(status.message);
    activeSupportReport = await diagnostics.preview();
    return activeSupportReport;
  });
  handle('submitSupportReport', async request => {
    if (!activeSupportReport || !request || typeof request.reportId !== 'string') throw new Error('Apri e controlla prima l’anteprima diagnostica');
    const url = await updateManager.createGithubIssue(activeSupportReport, {
      confirmed: request.confirmed === true, expectedReportId: request.reportId
    });
    activeSupportReport = null;
    return { url };
  });
  session.onProgress = value => win?.webContents.send('premontato:progress', value);
  win.on('close',event=>{
    if(shuttingDown)return;
    event.preventDefault();if(closing)return;
    if(busy || updateRestartPending){publishProjectStatus();win.webContents.send('premontato:projectStatus',{...session.projectStatus(),error:'Operazione in corso: attendi oppure annulla l’analisi prima di chiudere.'});return;}
    closing=true;
    (async()=>{try{const draft=await win.webContents.executeJavaScript('window.capturePremontatoDraft?.()');if(draft)session.setDraft(draft);await session.saveAutosave();await session.shutdownWorker();try{sdk?.CleanUp();}catch{}shuttingDown=true;app.quit();}
    catch(error){closing=false;const result=await dialog.showMessageBox(win,{type:'error',title:'Salvataggio non riuscito',message:'Non riesco a salvare la sessione Premontato.',detail:error.message,buttons:['Riprova','Chiudi senza salvare'],defaultId:0,cancelId:0});if(result.response===1){shuttingDown=true;await session.shutdownWorker();app.quit();}}})();
  });
  const autoSaveTimer=setInterval(async()=>{if(busy || shuttingDown || closing || !session.state.script && !session.state.media.length)return;busy=true;try{await session.saveAutosave();if(session.state.projectId)await saveResolve(session.state.projectId);}catch(error){session.saveError=error.message;}finally{busy=false;publishProjectStatus();}},60000);autoSaveTimer.unref();
  await win.loadFile(path.join(__dirname, 'index.html'));
}
if (!app.requestSingleInstanceLock()) app.quit(); else app.whenReady().then(start).catch(async error => { await dialog.showMessageBox({ type: 'error', title: 'RAMBLA Premontato', message: 'Avvio non riuscito', detail: error.message }); app.quit(); });
app.on('window-all-closed', () => { try { sdk?.CleanUp(); } catch {} app.quit(); });



