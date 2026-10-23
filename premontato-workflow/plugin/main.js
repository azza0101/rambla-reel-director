'use strict';
const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { assertTrusted, validateMediaRecords } = require('./ipc_security');
const { Session } = require('./session');
const adapter = require('./resolve_adapter');
const ID = 'com.rambla.premontato';
app.setPath('userData', path.join(app.getPath('appData'), 'RAMBLA', 'Premontato'));
let win, sdk, session, busy = false;
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
    try { return await fn(...args); } finally { if (name !== 'cancelAnalysis') busy = false; }
  });
}
async function start() {
  const root = app.getPath('userData');
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
    const results = await adapter.transcribeSelected(await getSdk());
    const resolveSnapshot = await adapter.snapshot(await getSdk());
    const sources = await adapter.getSelectedTranscriptions(await getSdk());
    const total = session.setTranscripts(sources, resolveSnapshot.fps, resolveSnapshot);
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
  handle('confirmTakes', async segments => session.confirmTakes(segments));
  handle('createReviewTimeline', async () => {
    const plan = session.state.analysis?.plan;
    if (!plan || plan.unmatched_beats.length || !plan.decisions.length) throw new Error('Piano incompleto: correggi trascrizioni o seleziona take per tutti i beat prima di creare la timeline');
    return adapter.createTimeline(await getSdk(), `PREMONTATO - ${new Date().toISOString().replace(/\D/g, '').slice(0, 14)}`, plan.decisions, session.state);
  });
  session.onProgress = value => win?.webContents.send('premontato:progress', value);
  await win.loadFile(path.join(__dirname, 'index.html'));
}
if (!app.requestSingleInstanceLock()) app.quit(); else app.whenReady().then(start).catch(async error => { await dialog.showMessageBox({ type: 'error', title: 'RAMBLA Premontato', message: 'Avvio non riuscito', detail: error.message }); app.quit(); });
app.on('window-all-closed', () => { try { sdk?.CleanUp(); } catch {} app.quit(); });



