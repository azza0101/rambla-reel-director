import shutil
import subprocess
import pytest
from backend.app.cut_pass_ui import JS


def test_clean_preview_resets_original_seek_and_refreshes_for_each_job():
    node=shutil.which('node')
    if not node:pytest.skip('node unavailable')
    harness=r'''
const vm=require('vm'),assert=require('assert');
const elements=new Map();
function element(){return {hidden:true,currentTime:0,src:'original',onloadedmetadata:null,
pause(){this.paused=true},load(){this.loaded=true},play(){this.played=true;return Promise.resolve()},
removeAttribute(){},querySelector(){return {value:0,textContent:''}},querySelectorAll(){return []}}}
const c={state:{pid:'p',project:{source_video:{}}},draw(){},setInterval(){},
$:id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id)},
document:{createElement:()=>element()},reportError:e=>{throw e},navigator:{clipboard:{}},
api:async()=>({job:{id:'new',kind:'preview',status:'succeeded',completed:4,message:'done',result:{url:'/preview'}}})};
vm.createContext(c);
'''
    script=harness+'\n'+ 'vm.runInContext('+__import__('json').dumps(JS)+',c);'+r'''
vm.runInContext("drawCut=()=>{};cutPid='p';cutData={job:{id:'old',kind:'preview',status:'succeeded',completed:4,message:'done'}};cutListenEnd=170;cutPlayer.onloadedmetadata=()=>{cutPlayer.currentTime=160};",c);
c.refreshCut().then(()=>{
 const v=elements.get('cutPlayer');assert.equal(v.src,'/preview');
 assert.equal(v.onloadedmetadata,null);assert.equal(v.loaded,true);
 assert.equal(vm.runInContext('cutListenEnd',c),null);
});
'''
    result=subprocess.run([node,'-e',script],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stderr
