const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
test('sandboxed preload exposes all commands and version without importing local files',()=>{
 let exposed;const electron={contextBridge:{exposeInMainWorld:(name,value)=>{assert.equal(name,'premontato');exposed=value;}},ipcRenderer:{invoke:async()=>({}),on:()=>{},removeListener:()=>{}}};
 const sandbox={require:name=>{if(name==='electron/renderer')return electron;throw Error('module not found: '+name);},process:{argv:['electron.exe','--premontato-version=0.9.1']}};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../plugin/preload.js'),'utf8'),sandbox);
 assert.equal(exposed.version,'0.9.1');assert.equal(typeof exposed.update,'function');assert.equal(typeof exposed.getReviewState,'function');assert.equal(typeof exposed.onProgress,'function');assert.equal(Object.isFrozen(exposed),true);
});

test('version remains visible in the initial HTML independently of preload startup',()=>{
 const folder=path.join(__dirname,'../../plugin'),version=JSON.parse(fs.readFileSync(path.join(folder,'package.json'))).version,html=fs.readFileSync(path.join(folder,'index.html'),'utf8');
 assert.ok(html.includes('aria-label="Versione plugin">v'+version+'</span>'));assert.ok(html.includes('<title>RAMBLA Premontato v'+version+'</title>'));
});
