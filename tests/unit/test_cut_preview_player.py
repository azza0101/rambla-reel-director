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


def test_cut_click_shows_pending_activity_before_server_reply_and_progress_is_real():
    node=shutil.which('node')
    if not node:pytest.skip('node unavailable')
    harness=r'''
const vm=require('vm'),assert=require('assert'),nodes=new Map();
const c={Map,Date,Math,Number,String,state:{pid:'p',project:{source_video:{}}},draw(){},setInterval(){},
$:id=>{if(!nodes.has(id))nodes.set(id,{scrollIntoView(){},querySelector(){return{}},querySelectorAll(){return[]}});return nodes.get(id)},
api:()=>new Promise(()=>{}),document:{},navigator:{clipboard:{}}};vm.createContext(c);
'''
    script=harness+'vm.runInContext('+__import__('json').dumps(JS)+',c);'+r'''
vm.runInContext('drawCut=()=>{}',c);c.cutAction('analyze');
assert.equal(vm.runInContext('cutData.job.status',c),'starting');
assert.equal(nodes.get('cutPassFold').open,true);
assert.equal(c.cutProgressState({status:'running',completed:0,total:4}).active,true);
assert.equal(c.cutProgressState({status:'running',completed:0,total:4}).percent,0);
assert.equal(c.cutProgressState({status:'running',completed:2.4,total:4}).percent,60);
assert.equal(c.cutProgressState({status:'failed',completed:2,total:4,message:'429 Rate limit'}).label,'Limite temporaneo Groq');
assert.equal(c.cutProgressState({status:'succeeded'}).percent,100);
'''
    result=subprocess.run([node,'-e',script],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stderr


def test_text_range_exclusions_preserve_hidden_take_indices_and_restore():
    node=shutil.which('node')
    if not node:pytest.skip('node unavailable')
    import json
    harness="const vm=require('vm'),assert=require('assert');const c={$:()=>({}),state:{},draw(){},setInterval(){}};vm.createContext(c);"
    script=harness+'vm.runInContext('+json.dumps(JS)+',c);'+r"""
    const words=[{index:0},{index:1},{index:5},{index:6}];
    assert.deepEqual(Array.from(c.cutRangeEdit(words,[20],6,1)),[1,5,6,20]);
    assert.deepEqual(Array.from(c.cutRangeEdit(words,[1,5,6,20],1,6)),[20]);
    assert.deepEqual(Array.from(c.cutRangeEdit(words,[],0,0)),[0]);
    """
    result=subprocess.run([node,'-e',script],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stderr


def test_first_click_saves_one_word_then_second_extends_without_restoring_it():
    node=shutil.which('node')
    if not node:pytest.skip('node unavailable')
    import json
    harness="const vm=require('vm'),assert=require('assert');const c={$:()=>({}),state:{},draw(){},setInterval(){}};vm.createContext(c);"
    script=harness+'vm.runInContext('+json.dumps(JS)+',c);'+r"""
    vm.runInContext(`cutExcludeMode=true;cutData={plan:{excluded_word_indices:[20]},words:[{index:0},{index:1},{index:2}]};drawCutText=()=>{};var saves=[];saveCut=async(a,b,excluded)=>{saves.push(excluded);cutData.plan.excluded_word_indices=excluded;return true}`,c);
    (async()=>{
      await c.cutWordClick(0);
      assert.deepEqual(Array.from(vm.runInContext('saves[0]',c)),[0,20]);
      await c.cutWordClick(2);
      assert.deepEqual(Array.from(vm.runInContext('saves[1]',c)),[0,1,2,20]);
      await c.cutWordClick(1);
      assert.deepEqual(Array.from(vm.runInContext('saves[2]',c)),[0,2,20]);
    })().catch(e=>{console.error(e);process.exitCode=1});
    """
    result=subprocess.run([node,'-e',script],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stderr


def test_highlight_wraps_words_and_spaces_in_one_continuous_run():
    node=shutil.which('node')
    if not node:pytest.skip('node unavailable')
    import json
    harness="const vm=require('vm'),assert=require('assert');const c={$:()=>({}),state:{},draw(){},setInterval(){},esc:s=>s};vm.createContext(c);"
    script=harness+'vm.runInContext('+json.dumps(JS)+',c);'+r"""
    const markup=c.cutTextMarkup([{index:0,text:'una',group_index:2,excluded:false},{index:1,text:'frase',group_index:2,excluded:false},{index:2,text:'normale',group_index:null,excluded:false}]);
    assert.equal((markup.match(/class="cutTextRun cutAlternative/g)||[]).length,1);
    assert.equal((markup.match(/data-cut-open="2"/g)||[]).length,1);
    assert.ok(markup.includes('una</span> <span'));
    """
    result=subprocess.run([node,'-e',script],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stderr


def test_confirmed_cut_preview_is_available_without_a_draft_plan():
    node=shutil.which('node')
    if not node:pytest.skip('node unavailable')
    import json
    harness="const vm=require('vm'),assert=require('assert');const c={$:()=>({}),state:{},draw(){},setInterval(){}};vm.createContext(c);"
    script=harness+'vm.runInContext('+json.dumps(JS)+',c);'+r"""
    assert.equal(c.cutPreviewBlockReason({source:true,plan:false,confirmed:true,workflowBusy:true,busy:false}),'');
    assert.ok(c.cutPreviewBlockReason({source:true,plan:false,confirmed:false,workflowBusy:false,busy:false}).includes('Auto-cut'));
    assert.ok(c.cutPreviewBlockReason({source:true,plan:true,confirmed:false,workflowBusy:true,busy:false}).includes('analisi'));
    assert.equal(c.cutPreviewBlockReason({source:true,plan:true,confirmed:false,workflowBusy:false,busy:false}),'');
    """
    result=subprocess.run([node,'-e',script],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stderr


def test_cut_undo_redo_preserve_history_on_failed_save_and_clear_redo_on_new_edit():
    node=shutil.which('node')
    if not node:pytest.skip('node unavailable')
    import json
    harness="const vm=require('vm'),assert=require('assert');const c={$:()=>({}),state:{},draw(){},setInterval(){}};vm.createContext(c);"
    script=harness+'vm.runInContext('+json.dumps(JS)+',c);'+r"""
    vm.runInContext(`drawCut=()=>{};cutData={plan:{excluded_word_indices:[1,2]}};recordCutEdit([],[1]);recordCutEdit([1],[1,2]);saveCut=async(a,b,excluded)=>{cutData.plan.excluded_word_indices=excluded;return true}`,c);
    (async()=>{
      await c.cutHistoryMove('undo');
      assert.deepEqual(Array.from(vm.runInContext('cutData.plan.excluded_word_indices',c)),[1]);
      await c.cutHistoryMove('redo');
      assert.deepEqual(Array.from(vm.runInContext('cutData.plan.excluded_word_indices',c)),[1,2]);
      vm.runInContext('saveCut=async()=>false',c);
      await c.cutHistoryMove('undo');
      assert.equal(vm.runInContext('cutUndoStack.length',c),2);
      vm.runInContext(`saveCut=async(a,b,excluded)=>{cutData.plan.excluded_word_indices=excluded;return true}`,c);
      await c.cutHistoryMove('undo');
      c.recordCutEdit([1],[3]);
      assert.equal(vm.runInContext('cutRedoStack.length',c),0);
    })().catch(e=>{console.error(e);process.exitCode=1});
    """
    result=subprocess.run([node,'-e',script],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stderr
