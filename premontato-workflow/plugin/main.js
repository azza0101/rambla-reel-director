'use strict';
const { app, BrowserWindow, ipcMain, dialog, safeStorage, net } = require('electron');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { assertTrusted, validateMediaRecords } = require('./ipc_security');
const { Session, prepareReviewTimeline } = require('./session');
const adapter = require('./resolve_adapter');
const updateManager = require('./updater');
const ID = 'com.rambla.premontato';
app.setPath('userData', path.join(app.getPath('appData'), 'RAMBLA', 'Premontato'));
let autoSaveTimer, sdkInitialization;
const handlerNames=new Set();
let win, sdk, session, diagnostics, activeSupportReport, busy = false, shuttingDown=false, closing=false, updateRestartPending=false;
const page = pathToFileURL(path.join(__dirname, 'index.html')).href;

async function getSdk() {
  if(sdk)return sdk;
  if(!sdkInitialization)sdkInitialization=(async()=>{
    try {
      const candidate=require('./WorkflowIntegration.node');
      if(!await candidate.InitializePromise(ID))throw new Error('InitializePromise rifiutata: riapri Premontato da Workspace > Workflow Integrations in Resolve');
      sdk=candidate;return sdk;
    } catch(error) { sdk=null;throw new Error('Collegamento Resolve non inizializzato: '+error.message); }
  })().finally(()=>{sdkInitialization=null;});
  return sdkInitialization;
}
function handle(name, fn) {
  handlerNames.add('premontato:'+name);
  ipcMain.handle(`premontato:${name}`, async (event, ...args) => {
    assertTrusted(event, win, page);
    if (updateRestartPending) throw new Error('Riavvio del pannello in corso');
    if (busy && !['cancelAnalysis','cancelCatalog'].includes(name)) throw new Error('Operazione già in corso');
    if (!['cancelAnalysis','cancelCatalog'].includes(name)) busy = true;
    try {
      let result=await fn(...args);
      if(['analyze','updateDecision','confirmVisualReview','setPacing','setDirections','selectScenes','setScriptPages','confirmTakes','selectMedia','selectScript','transcribeSelected'].includes(name)){const pending=session.state.uiDraft?.directions;session.state.uiDraft=['updateDecision','confirmVisualReview','setPacing','confirmTakes'].includes(name) && pending ? {directions:pending} : null;}
      if(['selectScript','selectMedia','transcribeSelected','analyze','updateDecision','confirmVisualReview','setPacing','setDirections','selectScenes','setScriptPages','confirmTakes','createReviewTimeline','loadVisualReview','saveDraft'].includes(name)){
        try{await session.saveAutosave();}catch(error){session.saveError='Salvataggio automatico non riuscito: '+error.message;}
        publishProjectStatus();if(result?.stage)result=session.getReviewState();
      }
      return result;
    }
    catch (error) {
      if(/Not initialized|InitializePromise rifiutata/i.test(error.message || ''))sdk=null;
      try { await diagnostics?.record('operation_failed', { operation: name, error: /^(catalog|cancelCatalog)/.test(name)?new Error('Operazione catalogo non riuscita; dettagli nel checkpoint locale'):error }); } catch {}
      throw error;
    } finally { if (!['cancelAnalysis','cancelCatalog'].includes(name)) busy = false; }
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
  const catalog=new (require('./day_catalog_session').DayCatalog)(root,session);
  catalog.onProgress=value=>win?.webContents.send('premontato:catalogProgress',value);
  require('./day_catalog_ipc').registerCatalogHandlers({handle,catalog,getSdk});
  session.groq=new (require('./session').GroqClient)(root,{vault:safeStorage,fetchImpl:net?.fetch ? net.fetch.bind(net) : globalThis.fetch});
  try{await session.restoreAutosave();}catch(error){session.saveError='Recupero automatico non riuscito: '+error.message;}
  win = new BrowserWindow({ width: 1080, height: 820, minWidth: 680, minHeight: 560, title: 'RAMBLA Premontato v'+require('./package.json').version,
    backgroundColor: '#111820', webPreferences: { additionalArguments:['--premontato-version='+require('./package.json').version], preload: path.join(__dirname, 'preload.js'), sandbox: true, contextIsolation: true, nodeIntegration: false } });
  win.setMenu(null); win.webContents.setWindowOpenHandler(() => ({ action: 'deny' })); win.webContents.on('will-navigate', e => e.preventDefault());
  win.webContents.session.setPermissionRequestHandler((_wc, _permission, callback) => callback(false));
  handle('resolveSnapshot', async () => { const result = await adapter.snapshot(await getSdk(),{includeSelection:false}); return { ...result, selected: result.selected.map(({ item, path: _mediaPath, ...record }) => record) }; });
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
  handle('analyze', async () => { const current = await adapter.snapshot(await getSdk(),{includeSelection:false}); session.assertProject(current); session.state.timelineId=current.timelineId; session.state.timeline=current.timeline; await saveResolve(session.state.projectId).catch(()=>{}); if(session.state.media?.some(media=>!(session.state.transcripts || []).some(source=>source.media_id===media.media_id && source.segments?.length))){const sources=await adapter.getSelectedTranscriptions(await getSdk(),{media:session.state.media,transcribeMissing:true,onProgress:({current,total,name})=>session.onProgress?.({phase:'transcript',phaseIndex:-1,percent:Math.round(current/total*100),current,total,label:'Recupero trascrizioni Resolve: '+name+' · '+current+'/'+total})});session.setTranscripts(sources,current.fps,{...current,selected:session.state.media});} return session.analyze(); });
  handle('cancelAnalysis', async () => session.cancelAnalysis());
  handle('configureGroq',async options=>{await session.groq.configure(options);session.state.analysis=null;session.state.uiDraft=null;session.state.stage='idle';await session.saveAutosave();return session.getReviewState();});
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
  handle('loadVisualReview', async () => session.loadVisualReview());
  handle('confirmVisualReview', async request => session.confirmVisualReview(request));
  handle('setDirections', async options => session.setDirections(options));
  handle('setPacing', async options => session.setPacing(options));
  handle('selectScenes',async request=>{const current=await adapter.snapshot(await getSdk(),{includeSelection:false});session.assertProject(current);return session.selectScenes(request);});
  handle('setScriptPages',async request=>session.setScriptPages(request));
  handle('confirmTakes', async segments => session.confirmTakes(segments));
  handle('createReviewTimeline', async request => {
    await session.validateMediaUnchanged();
    await saveResolve(session.state.projectId);
    const plan = session.state.analysis?.plan;
    const review = prepareReviewTimeline(plan, request?.confirmed);
    const sdk=await getSdk(),context=await adapter.getResolve(sdk);
    const debug=await session.prepareTimelineDebug(review.decisions,request?.sceneDebug ?? session.state.uiDraft?.sceneDebug ?? true,{fps:Number(await context.timeline.GetSetting('timelineFrameRate')),width:Number(await context.timeline.GetSetting('timelineResolutionWidth')) || 1920,height:Number(await context.timeline.GetSetting('timelineResolutionHeight')) || 1080});
    const created = await adapter.createTimeline(sdk, `PREMONTATO v${require('./package.json').version} - ${new Date().toISOString().replace(/\D/g, '').slice(0, 14)}`, debug.decisions, {...session.state,sceneDebug:debug.sceneDebug,activateCreated:true});
    if(created.opened){session.state.timelineId=created.timelineId;session.state.timeline=created.timelineName;}
    try{await saveResolve(session.state.projectId);}catch{}
    return { ...created, included: review.decisions.length, omitted: review.omitted };
  });
  handle('update', async request => {
    if(request?.draft)session.setDraft(request.draft);
    updateProgress({phase:'credential',percent:null,detail:'Leggo la credenziale di download protetta da Windows.'});
    const credentialPath=updateManager.resolveGithubCredentialPath(process.env.PROGRAMDATA);
    if(!credentialPath)throw new Error('Credenziale GitHub RMBL non trovata: verifica l’installazione Auto-Cut.');
    let token=updateManager.loadProtectedToken(credentialPath),jobRoot=null;
    try{
      const update=await updateManager.findLatestUpdate(require('./package.json').version,token,undefined,updateProgress);
      if(update.status!=='available'){updateProgress({phase:'current',percent:100,version:update.version});return update;}
      if(!/(?:^|[\\/])electron(?:\.exe)?$/i.test(process.execPath))throw new Error('Aggiorna dal pannello Electron di Resolve per consentire il riavvio automatico');
      const fsp=require('node:fs/promises');await fsp.mkdir(path.join(root,'updates'),{recursive:true});jobRoot=await fsp.mkdtemp(path.join(root,'updates','job-'));
      const archivePath=path.join(jobRoot,update.manifest.archive);
      await updateManager.downloadVerifiedArchive(update,token,archivePath,undefined,updateProgress);token='';
      updateProgress({phase:'save',percent:null});await session.saveAutosave();await saveResolve();
      await session.shutdownWorker();updateProgress({phase:'install',percent:null});
      await updateManager.runUpdateInstaller({script:path.join(__dirname,'update.ps1'),pluginRoot:__dirname,archivePath,sha256:update.manifest.sha256,version:update.manifest.version,onProgress:updateProgress});
      updateRestartPending=true;updateProgress({phase:'restart',percent:100,version:update.manifest.version});
      setTimeout(()=>restartInHost().catch(error=>{shuttingDown=false;updateRestartPending=false;updateProgress({phase:'restart-error',percent:null,error:error.message});}),1200);
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
  autoSaveTimer=setInterval(async()=>{if(busy || shuttingDown || closing || !session.state.script && !session.state.media.length)return;busy=true;try{await session.saveAutosave();if(session.state.projectId)await saveResolve(session.state.projectId);}catch(error){session.saveError=error.message;}finally{busy=false;publishProjectStatus();}},60000);autoSaveTimer.unref();
  await win.loadFile(path.join(__dirname, 'index.html'));
}
async function reloadInHost() {
  // Resolve owns the Electron process registration: app.relaunch() creates an orphan.
  const connectedSdk=sdk;
  const holdProcessOpen=()=>{};app.on('window-all-closed',holdProcessOpen);
  shuttingDown=true;clearInterval(autoSaveTimer);
  app.removeListener('window-all-closed',onAllWindowsClosed);
  for(const name of handlerNames)ipcMain.removeHandler(name);
  handlerNames.clear();
  win?.destroy();win=null;session=null;sdk=null;
  const modules=['main.js','session.js','runtime/premontato/groq_client.js','runtime/premontato/editorial_client.js','runtime/premontato/video_coliche.json','updater.js','resolve_adapter.js','ipc_security.js','day_catalog_resolve.js','day_catalog_store.js','day_catalog_session.js','day_catalog_ipc.js','runtime/premontato/day_catalog_clips.js','runtime/premontato/day_catalog_vision.js','package.json'];
  for(const name of modules)delete require.cache[require.resolve(path.join(__dirname,name))];
  try { await require(__filename).launch({initializedSdk:connectedSdk}); }
  catch(error){await dialog.showMessageBox({type:'error',title:'RAMBLA Premontato',message:'Ricaricamento non riuscito. Riapri il pannello dal menu Workspace > Workflow Integrations di Resolve.',detail:error.message});app.quit();throw error;}
  finally{app.removeListener('window-all-closed',holdProcessOpen);}
}
async function restartInHost() {
  return updateManager.restartPlugin(app,async()=>{await session.saveAutosave();await session.shutdownWorker();},{reload:reloadInHost});
}
function onAllWindowsClosed(){if(BrowserWindow.getAllWindows().length)return;try{sdk?.CleanUp();}catch{}app.quit();}
async function launch({initializedSdk}={}) {
  if(initializedSdk)sdk=initializedSdk;
  app.on('window-all-closed',onAllWindowsClosed);
  await start();
}
module.exports={launch,restartInHost};
if(!globalThis[Symbol.for('com.rambla.premontato.bootstrapped')]){
  globalThis[Symbol.for('com.rambla.premontato.bootstrapped')]=true;
  if(!app.requestSingleInstanceLock())app.quit();
  else app.whenReady().then(()=>launch()).catch(async error=>{await dialog.showMessageBox({type:'error',title:'RAMBLA Premontato',message:'Avvio non riuscito',detail:error.message});app.quit();});
}
