const fs=require('fs'),vm=require('vm'),assert=require('assert');
const text=fs.readFileSync(process.argv[2],'utf8');
const code=text.slice(text.indexOf('let socialSearchScopeV5'),text.indexOf('const expandedShelvesV2'));
const nodes=new Map(),calls=[];let ready=false;
const context={$:id=>{if(!nodes.has(id))nodes.set(id,{disabled:false,textContent:'',showModal(){},close(){}});return nodes.get(id)},state:{run:null,active:'beat_002'},api:async(path)=>{calls.push(path);return {ready:path.includes('tiktok')||ready,detail:'check',login_state:'unknown'}},startStage:async path=>calls.push('START:'+path),researchBeatV2:async(mode,providers)=>calls.push('BEAT:'+mode+':'+providers.join(',')),reportError:e=>{throw e},Promise};
vm.createContext(context);vm.runInContext(code,context);
(async()=>{
 await context.prepareSocialV5();
 assert(calls.includes('/social/tiktok/login')&&calls.includes('/social/instagram/login'));
 assert(!calls.some(c=>c.startsWith('START:')));
 await context.checkSocialAndRunV5();
 assert(!calls.some(c=>c.startsWith('START:')));
 ready=true;await context.checkSocialAndRunV5();
 assert(calls.includes('START:source/social'));
 await context.prepareSocialV5('beat_002');await context.checkSocialAndRunV5();
 assert(calls.includes('BEAT:append:tiktok,instagram'));
 console.log('Social preflight interaction checks passed');
})().catch(e=>{console.error(e);process.exit(1)});
