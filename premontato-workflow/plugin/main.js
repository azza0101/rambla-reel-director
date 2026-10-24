'use strict';
const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { assertTrusted, validateMediaRecords } = require('./ipc_security');
const { Session, prepareReviewTimeline } = require('./session');
const adapter = require('./resolve_adapter');
const updateManager = require('./updater');
const { spawn } = require('node:child_process');
const ID = 'com.rambla.premontato';
app.setPath('userData', path.join(app.getPath('appData'), 'RAMBLA', 'Premontato'));
let win, sdk, session, diagnostics, activeSupportReport, busy = false;
const page = pathToFileURL(path.join(__dirname, 'index.html')).href;

async function getSdk() {
  if (sdk) return sdk;
  try { sdk = require('./WorkflowIntegration.node'); if (!await sdk.InitializePromise(ID)) throw new Error('InitializePromise rifiutata'); return sdk; }
  catch (error) { throw new Error(`Bridge Workflow Integration non disponibile: ${error.message}`); }
}
function handle(name, fn) {
  ipcMain.handle(`premontato:${name}`, async (event, ...args) => {
    assertTrusted(event, win, page);
    if (busy && name !== 'cancelAnalysis') throw new Error('Operazione già in corso');
    if (name !== 'cancelAnalysis') busy = true;
    try { return await fn(...args); }
    catch (error) {
      try { await diagnostics?.record('operation_failed', { operation: name, error }); } catch {}
      throw error;
    } finally { if (name !== 'cancelAnalysis') busy = false; }
  });
}
async function start() {
  const root = app.getPath('userData');
  diagnostics = updateManager.createDiagnostics({ logPath: path.join(root, 'logs', 'premontato-diagnostics.jsonl'),
    appVersion: require('./package.json').version, platform: process.platform, release: require('node:os').release() });
  await diagnostics.record('application_started');
  const workerPath = path.join(__dirname, 'worker', 'protocol.py');
  session = new Session(root, workerPath);
  win = new BrowserWindow({ width: 1080, height: 820, minWidth: 680, minHeight: 560, title: 'RAMBLA Premontato',
    backgroundColor: '#111820', webPreferences: { preload: path.join(__dirname, 'preload.js'), sandbox: true, contextIsolation: true, nodeIntegration: false } });
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
  handle('analyze', async () => { const current = await adapter.snapshot(await getSdk()); session.assertContext(current); return session.analyze(); });
  handle('cancelAnalysis', async () => session.cancelAnalysis());
  handle('getReviewState', async () => session.getReviewState());
  handle('updateDecision', async request => { session.updateDecision(request); return session.applyPacing(); });
  handle('confirmVisualReview', async request => session.confirmVisualReview(request));
  handle('setPacing', async options => session.setPacing(options));
  handle('confirmTakes', async segments => session.confirmTakes(segments));
  handle('createReviewTimeline', async request => {
    const plan = session.state.analysis?.plan;
    const review = prepareReviewTimeline(plan, request?.confirmed);
    const created = await adapter.createTimeline(await getSdk(), `PREMONTATO - ${new Date().toISOString().replace(/\D/g, '').slice(0, 14)}`, review.decisions, session.state);
    return { ...created, included: review.decisions.length, omitted: review.omitted };
  });
  handle('update', async () => {
    const credentialPath = updateManager.resolveGithubCredentialPath(process.env.PROGRAMDATA);
    if (!credentialPath) throw new Error('Credenziale GitHub RMBL non trovata: verifica l’installazione Auto-Cut e il suo file runtime.json.');
    let token = updateManager.loadProtectedToken(credentialPath);
    let archivePath = null;
    try {
      const currentVersion = require('./package.json').version;
      const update = await updateManager.findLatestUpdate(currentVersion, token);
      if (update.status === 'unpublished' || update.status === 'current') return update;
      archivePath = path.join(root, 'updates', update.manifest.archive);
      await updateManager.downloadVerifiedArchive(update, token, archivePath);
      token = '';
      await session.shutdownWorker();
      await new Promise((resolve, reject) => {
        const child = spawn('powershell.exe', ['-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', path.join(__dirname, 'update.ps1'),
          '-PluginRoot', __dirname, '-ArchivePath', archivePath, '-ExpectedSha256', update.manifest.sha256, '-Version', update.manifest.version],
        { windowsHide: true, stdio: 'ignore' });
        child.once('error', () => reject(new Error('Impossibile avviare l’installazione dell’aggiornamento')));
        child.once('exit', code => code === 0 ? resolve() : reject(new Error(code === 1223 ? 'Aggiornamento annullato nella richiesta UAC.' : 'Installazione aggiornamento non riuscita; l’installazione precedente è stata conservata.')));
      });
      return { status: 'updated', version: update.manifest.version };
    } finally {
      token = '';
      if (archivePath) await require('node:fs/promises').rm(archivePath, { force: true }).catch(() => {});
    }
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
  await win.loadFile(path.join(__dirname, 'index.html'));
}
if (!app.requestSingleInstanceLock()) app.quit(); else app.whenReady().then(start).catch(async error => { await dialog.showMessageBox({ type: 'error', title: 'RAMBLA Premontato', message: 'Avvio non riuscito', detail: error.message }); app.quit(); });
app.on('window-all-closed', () => { try { sdk?.CleanUp(); } catch {} app.quit(); });



