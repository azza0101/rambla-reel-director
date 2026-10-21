const crypto=require('node:crypto');const test=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');const path=require('node:path');const {EventEmitter}=require('node:events');
async function harness(busy=false){
 const root=path.resolve('.runtime-temp','autocut-node-'+crypto.randomUUID());fs.mkdirSync(root,{recursive:true});
 fs.writeFileSync(path.join(root,'runtime.json'),JSON.stringify({app_root:root,python:process.execPath,data_root:path.join(root,'data')}));
 let window;const handlers={};const workers=[];let relaunched=0,quit=0;
 const app=new EventEmitter();app.requestSingleInstanceLock=()=>true;app.whenReady=()=>Promise.resolve();app.quit=()=>quit++;app.relaunch=()=>relaunched++;
 class Window extends EventEmitter{
  constructor(){super();window=this;this.webContents=new EventEmitter();this.webContents.setWindowOpenHandler=()=>{};this.webContents.session={webRequest:{onBeforeSendHeaders:()=>{}}};}
  setMenu(){} async loadFile(){} async loadURL(url){this.url=url} destroy(){}
 }
 const native={Initialize:async()=>true,GetResolve:async()=>null,CleanUp:()=>{}};
 function spawn(){const child=new EventEmitter();child.exitCode=null;workers.push(child);if(workers.length>1)queueMicrotask(()=>{child.exitCode=0;child.emit('exit',0)});return child}
 const fakeRequire=name=>name==='electron'?{app,BrowserWindow:Window,ipcMain:{handle:(name,fn)=>handlers[name]=fn},dialog:{showMessageBox:async()=>{}}}:name==='./WorkflowIntegration.node'?native:name==='./source_adapter'?{snapshot:async()=>({})}:name==='node:child_process'?{spawn}:require(name);
 const fetch=async url=>({ok:true,json:async()=>url.endsWith('/busy')?{busy}:url.endsWith('/health')?{service:'rmbl-autocut'}:({}),...url.endsWith('/shutdown')?(workers[0].exitCode=0,queueMicrotask(()=>workers[0].emit('exit',0)),{}):{}});
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'main.js'),'utf8'),{require:fakeRequire,__dirname:root,process,fetch,AbortSignal,setTimeout,clearTimeout,console});
 for(let i=0;i<100&&!window?.url;i++)await new Promise(ok=>setTimeout(ok,5));
 assert.ok(window?.url,'Integration should start');
 return {event:{sender:window.webContents,senderFrame:{url:window.url}},update:handlers['autocut:update'],counts:()=>({relaunched,quit,workers:workers.length})};
}
test('update relaunches only the integration and shuts down its worker',async()=>{
 const h=await harness();await h.update(h.event);await new Promise(ok=>setTimeout(ok,300));
 assert.deepEqual(h.counts(),{relaunched:1,quit:1,workers:2});
});
test('update is blocked while Auto-Cut works',async()=>{
 const h=await harness(true);await assert.rejects(h.update(h.event),/Attendi/);
 assert.deepEqual(h.counts(),{relaunched:0,quit:0,workers:1});
});
