const {app,BrowserWindow,ipcMain,dialog}=require('electron');
const path=require('node:path');const fs=require('node:fs');const net=require('node:net');const crypto=require('node:crypto');const {spawn}=require('node:child_process');
const {snapshot}=require('./source_adapter');
const WorkflowIntegration=require('./WorkflowIntegration.node');
const PLUGIN_ID='com.rambla.autocut';
let window=null,worker=null,base='',token='',resolve=null,closing=false,initializing=null,updating=false;
if(!app.requestSingleInstanceLock()){app.quit()}else{
 app.on('second-instance',()=>{if(window){if(window.isMinimized())window.restore();window.focus()}});
 app.whenReady().then(start).catch(showError);
}
async function showError(error){await dialog.showMessageBox({type:'error',title:'RMBL Auto-Cut',message:'Avvio non riuscito',detail:String(error.message||error)});app.quit()}
async function freePort(){return await new Promise((ok,fail)=>{const server=net.createServer();server.once('error',fail);server.listen(0,'127.0.0.1',()=>{const port=server.address().port;server.close(()=>ok(port))})})}
async function request(endpoint,options={}){return await fetch(base+endpoint,{...options,headers:{...options.headers,'X-Autocut-Session':token},signal:AbortSignal.timeout(5000)})}
async function getResolve(){
 if(resolve)return resolve;
 if(!initializing)initializing=(async()=>{if(!await WorkflowIntegration.Initialize(PLUGIN_ID))throw Error('Interfaccia Workflow Integration non disponibile');const value=await WorkflowIntegration.GetResolve();if(!value)throw Error('Resolve non risponde al plugin');return value})();
 try{resolve=await initializing;return resolve}finally{initializing=null}
}
async function start(){
 const config=JSON.parse(fs.readFileSync(path.join(__dirname,'runtime.json'),'utf8').replace(/^\uFEFF/,''));
 for(const key of ['app_root','python','data_root'])if(typeof config[key]!=='string'||!config[key])throw Error('Configurazione runtime incompleta: reinstalla il plugin');
 if(!fs.existsSync(config.python))throw Error('Runtime Python non disponibile: reinstalla il plugin');
 token=crypto.randomBytes(32).toString('hex');const port=await freePort();base='http://127.0.0.1:'+port;
 fs.mkdirSync(config.data_root,{recursive:true});const log=fs.openSync(path.join(config.data_root,'startup.log'),'a');
 worker=spawn(config.python,['-m','backend.app.autocut_service','--port',String(port),'--data-root',config.data_root],{cwd:config.app_root,windowsHide:true,env:{...process.env,PYTHONPATH:config.app_root,PYTHONUNBUFFERED:'1',RMBL_AUTOCUT_SESSION:token,PATH:path.join(config.app_root,'runtime','bin')+path.delimiter+process.env.PATH},stdio:['ignore',log,log]});
 fs.closeSync(log);
 window=new BrowserWindow({width:1050,height:850,minWidth:620,minHeight:480,title:'RMBL Auto-Cut',backgroundColor:'#101418',webPreferences:{preload:path.join(__dirname,'preload.js'),sandbox:true,contextIsolation:true,nodeIntegration:false}});
 window.setMenu(null);await window.loadFile(path.join(__dirname,'loading.html'));
 window.webContents.setWindowOpenHandler(()=>({action:'deny'}));
 window.webContents.on('will-navigate',(event,url)=>{if(!url.startsWith(base+'/autocut'))event.preventDefault()});
 window.webContents.session.webRequest.onBeforeSendHeaders({urls:[base+'/*']},(details,done)=>done({requestHeaders:{...details.requestHeaders,'X-Autocut-Session':token}}));
 ipcMain.handle('autocut:snapshot',async event=>{
  if(event.sender!==window.webContents||!event.senderFrame.url.startsWith(base+'/autocut'))throw Error('Untrusted integration page');
  return await snapshot(await getResolve());
 });
 ipcMain.handle('autocut:update',async event=>{
  if(event.sender!==window.webContents||!event.senderFrame.url.startsWith(base+'/autocut'))throw Error('Untrusted integration page');
  if(updating)throw Error('Aggiornamento già in corso');
  const check=await request('/autocut/busy');if(!check.ok||(await check.json()).busy)throw Error('Attendi la fine di Auto-Cut o APPLICA');
  const executable=path.basename(process.execPath).toLowerCase();
  if(executable==='resolve.exe'||executable==='resolve')throw Error('Questo host richiede la riapertura manuale del solo plugin');
  updating=true;
  try{
   const stopped=await request('/autocut/shutdown',{method:'POST'});if(!stopped.ok)throw Error('Motore occupato: aggiornamento annullato');
   await new Promise((ok,fail)=>{if(worker.exitCode!==null)return ok();const timeout=setTimeout(()=>fail(Error('Arresto motore non completato')),10000);worker.once('exit',()=>{clearTimeout(timeout);ok()})});
   const update=spawn(config.python,['-m','backend.app.autocut_update','--app-root',config.app_root,'--plugin-root',__dirname,'--data-root',config.data_root],{cwd:config.app_root,windowsHide:true,env:{...process.env,PYTHONPATH:config.app_root},stdio:['ignore','ignore','ignore']});
   await new Promise((ok,fail)=>{update.once('error',fail);update.once('exit',code=>code===0?ok():fail(Error('Aggiornamento non completato'))) });
  }finally{
   // Only this Electron integration is relaunched. Resolve is never terminated.
   if(worker.exitCode!==null){closing=true;app.relaunch();setTimeout(()=>app.quit(),250)}else updating=false;
  }
  return {status:'reloading'};
 });
 window.on('close',event=>{
  if(closing)return;event.preventDefault();if(updating)return;
  (async()=>{
   try{
    const response=await request('/autocut/busy');if(!response.ok)throw Error('Stato del motore non disponibile');
    if((await response.json()).busy){await dialog.showMessageBox(window,{type:'info',message:'Auto-Cut sta lavorando',detail:'Attendi la fine dell’operazione prima di chiudere il plugin.'});return}
    const stop=await request('/autocut/shutdown',{method:'POST'});if(!stop.ok)return;
    closing=true;if(resolve)WorkflowIntegration.CleanUp();window.destroy();app.quit();
   }catch(error){await dialog.showMessageBox(window,{type:'warning',message:'Il motore non risponde',detail:'La finestra resta aperta per evitare di interrompere un montaggio in corso. '+error.message})}
  })();
 });
 let ready=false;
 for(let attempt=0;attempt<160;attempt++){
  if(worker.exitCode!==null)throw Error('Motore Auto-Cut arrestato: consulta '+path.join(config.data_root,'startup.log'));
  try{const response=await request('/autocut/health');if(response.ok&&(await response.json()).service==='rmbl-autocut'){ready=true;break}}catch(_){}
  await new Promise(ok=>setTimeout(ok,250));
 }
 if(!ready)throw Error('Timeout avvio Auto-Cut: consulta '+path.join(config.data_root,'startup.log'));
 await window.loadURL(base+'/autocut');
}
app.on('window-all-closed',()=>app.quit());
