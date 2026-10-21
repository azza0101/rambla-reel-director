const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),vm=require('node:vm');
test('Electron IPC rejects untrusted frames, guards update/export and never restarts Resolve',async t=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'srt-main-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));const handlers={},events={};let win,finishUpdate,restarts=0,copied=null;
 const tl={GetUniqueId:()=> 'tl',GetName:()=> 'Timeline',GetSetting:()=>25,GetStartFrame:()=>0,GetEndFrame:()=>100,GetStartTimecode:()=> '00:00:00:00',GetMarkInOut:()=>({video:{in:0,out:25}}),GetTrackCount:()=>1,GetItemListInTrack:()=>[{GetStart:()=>0,GetEnd:()=>25,GetName:()=> 'Hello'}]};
 const project={GetUniqueId:()=> 'p',GetName:()=> 'Project',GetCurrentTimeline:()=>tl};
 const app={getPath:()=>root,setPath:()=>{},requestSingleInstanceLock:()=>true,on:()=>{},whenReady:()=>Promise.resolve(),quit:()=>{restarts++},relaunch:()=>{restarts++}};
 class Window{constructor(){win=this;this.webContents={mainFrame:{url:''},setWindowOpenHandler:()=>{},on:()=>{},session:{setPermissionRequestHandler:()=>{}}}}setMenu(){}on(n,f){events[n]=f}async loadFile(p){this.webContents.mainFrame.url=require('node:url').pathToFileURL(p).href}}
 const electron={clipboard:{writeText:text=>{copied=text}},app,BrowserWindow:Window,ipcMain:{handle:(n,f)=>handlers[n]=f},dialog:{showMessageBox:async()=>{throw Error('unexpected startup error')}},shell:{openPath:async()=>''}};
 const base=path.resolve(__dirname,'../plugin');const requireLocal=p=>p==='electron'?electron:p==='./WorkflowIntegration.node'?{InitializePromise:async()=>true,SetAPITimeout:()=>{},GetResolvePromise:async()=>({GetProjectManager:()=>({GetCurrentProject:()=>project})}),CleanUp:()=>{}}:p==='./updater'?{recover:()=>{},update:()=>new Promise(ok=>finishUpdate=ok)}:p.startsWith('./')?require(path.join(base,p)):require(p);
 vm.runInNewContext(fs.readFileSync(path.join(base,'main.js'),'utf8'),{require:requireLocal,__dirname:base,process,console,Buffer});await new Promise(ok=>setImmediate(ok));
 const event={sender:win.webContents,senderFrame:win.webContents.mainFrame};
 await assert.rejects(handlers['srt:refresh']({sender:win.webContents,senderFrame:{url:event.senderFrame.url}}),/autorizzata/);
 const state=await handlers['srt:refresh'](event);assert.equal(state.snapshot.captions[0].content,'Hello');
 await assert.rejects(handlers['srt:copy']({sender:{},senderFrame:win.webContents.mainFrame}),/autorizzata/);await handlers['srt:copy'](event);assert.equal(copied,'1\r\n00:00:00,000 --> 00:00:01,000\r\nHello\r\n\r\n');
 await handlers['srt:save'](event,{folder:root});const exported=await handlers['srt:export'](event);assert.ok(fs.existsSync(exported.path));
 const update=handlers['srt:update'](event);await new Promise(ok=>setImmediate(ok));await assert.rejects(handlers['srt:export'](event),/corso/);let blocked=false;events.close({preventDefault:()=>blocked=true});assert.equal(blocked,true);finishUpdate({status:'updated',version:'3.2.1'});await update;assert.equal(restarts,0);await assert.rejects(handlers['srt:export'](event),/riapri/);
});
