'use strict';
const {app,BrowserWindow,ipcMain,dialog,shell,clipboard}=require('electron');
const path=require('node:path'),fs=require('node:fs'),{pathToFileURL}=require('node:url');
const ID='com.rambla.srt';
// Set before locking: Electron's default userData is shared by unrelated plugins.
app.setPath('userData',path.join(app.getPath('appData'),'RAMBLA','SRT'));
let window,sdk,session,resolve,working=false,restartRequired=false;
const page=pathToFileURL(path.join(__dirname,'index.html')).href;
async function getResolve(){if(resolve)return resolve;try{sdk=require('./WorkflowIntegration.node');if(!await sdk.InitializePromise(ID))throw Error('Inizializzazione rifiutata');sdk.SetAPITimeout(10);resolve=await sdk.GetResolvePromise();if(!resolve)throw Error('Resolve non disponibile');return resolve}catch(e){throw Error('Collegamento a Resolve non disponibile. Apri RAMBLA SRT da Workspace > Workflow Integrations. '+e.message)}}
function trusted(event){if(event.sender!==window.webContents||event.senderFrame!==window.webContents.mainFrame||event.senderFrame.url!==page)throw Error('Pagina non autorizzata')}
function handle(name,fn){ipcMain.handle('srt:'+name,async(event,...args)=>{trusted(event);if(working)throw Error('Operazione in corso');if(restartRequired)throw Error('Aggiornamento installato: chiudi e riapri solo RAMBLA SRT');working=true;try{return await fn(...args)}finally{working=false}})}
async function start(){
 const updater=require('./updater'),root=app.getPath('userData');fs.mkdirSync(root,{recursive:true});updater.recover(__dirname,root);
 const {Session}=require('./session'),{snapshot}=require('./resolve_adapter');session=new Session(root,async()=>snapshot(await getResolve()));
 window=new BrowserWindow({width:1000,height:850,minWidth:620,minHeight:480,title:'RAMBLA SRT',backgroundColor:'#101418',webPreferences:{preload:path.join(__dirname,'preload.js'),sandbox:true,contextIsolation:true,nodeIntegration:false}});window.setMenu(null);
 window.webContents.setWindowOpenHandler(()=>({action:'deny'}));window.webContents.on('will-navigate',e=>e.preventDefault());window.webContents.session.setPermissionRequestHandler((_,__,done)=>done(false));
 handle('refresh',()=>session.refresh());handle('save',patch=>session.save(patch));handle('add',()=>session.addRange());handle('remove',i=>session.removeRange(i));
 handle('folder',async()=>{const r=await dialog.showOpenDialog(window,{properties:['openDirectory','createDirectory']});return r.canceled?null:session.save({folder:r.filePaths[0]})});
 handle('copy',async()=>{const text=await session.copy();clipboard.writeText(text);return {bytes:Buffer.byteLength(text)}});
 handle('export',()=>session.export());handle('open',async()=>{if(!session.lastFolder)throw Error('Esporta prima un SRT');const error=await shell.openPath(session.lastFolder);if(error)throw Error(error);return true});
 handle('version',()=>require('./package.json').version);
 handle('check',()=>updater.check(require('./package.json').version));
 handle('update',async()=>{session.assertIdle();session.busy=true;try{const result=await updater.update(__dirname,root);if(result.status==='updated')restartRequired=true;return result}finally{session.busy=false}});
 window.on('close',event=>{if(working){event.preventDefault();return}try{sdk?.CleanUp()}catch{}resolve=null});
 await window.loadFile(path.join(__dirname,'index.html'));
}
if(!app.requestSingleInstanceLock())app.quit();else{app.on('second-instance',()=>{window?.show();window?.focus()});app.whenReady().then(start).catch(async e=>{await dialog.showMessageBox({type:'error',title:'RAMBLA SRT',message:'Avvio non riuscito',detail:e.message});app.quit()})}
app.on('window-all-closed',()=>app.quit());
