import json
import shutil
import subprocess
from pathlib import Path

import pytest


def test_director_status_and_terminal_cleanup_execute_in_javascript():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node runtime unavailable")
    root = Path(__file__).resolve().parents[2]
    base = (root / "backend/app/curation_ui.py").read_text(encoding="utf-8")
    ui = (root / "backend/app/curation_ui_v2.py").read_text(encoding="utf-8")
    watch = next(line for line in base.splitlines() if line.startswith("async function watch(id)"))
    sync = next(line for line in ui.splitlines() if line.startswith("function syncDirectorControlsV5()"))
    harness = r"""
const assert=require('node:assert/strict');
const nodes={};const $=id=>nodes[id]??=( {textContent:'',value:'',hidden:false} );
const state={run:'media-job',currentStageV12:'videos',data:{analysis_ready:true,editorial_plan_ready:true}};
let workflowFailureV12=null;
const directorStatusV5={providers:{auto:{configured:true,chain:['gemini','groq']}}};
$('directorProviderV5').value='auto';
SYNC
syncDirectorControlsV5();
assert.match($('directorStateV5').textContent,/Piano completato/);
state.currentStageV12='director_api';syncDirectorControlsV5();
assert.match($('directorStateV5').textContent,/running|corso/);
let tick,terminal=0;
const setInterval=fn=>(tick=fn,1),clearInterval=()=>{};
const esc=x=>String(x),planDetails=()=>'';
const hydrate=async()=>{throw new Error('hydrate failed')};
const fetch=async()=>({json:async()=>({status:'SUCCEEDED',stage_type:'director_api',total_progress:100,events:[]})});
const window={ramblaRunProgress:()=>assert.equal(state.run,null),ramblaRunTerminal:()=>{terminal++;syncDirectorControlsV5()}};
WATCH
(async()=>{await watch('director-job');try{await tick()}catch(e){assert.equal(e.message,'hydrate failed')}
assert.equal(state.run,null);assert.equal(terminal,1);assert.equal($('stop').hidden,true);
assert.match($('directorStateV5').textContent,/Piano completato/);
await tick();assert.equal(terminal,1);
workflowFailureV12='director_api';syncDirectorControlsV5();assert.match($('directorStateV5').textContent,/non riuscito/);
})().catch(e=>{console.error(e);process.exitCode=1});
""".replace("SYNC",sync).replace("WATCH",watch)
    result=subprocess.run([node,"-e",harness],capture_output=True,text=True,encoding="utf-8")
    assert result.returncode == 0, result.stderr
