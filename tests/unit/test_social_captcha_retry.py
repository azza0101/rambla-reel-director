import subprocess
from backend.app.social_gallery import JS

def test_retry_targets_only_current_provider_and_preserves_search_options():
    retry=next(line for line in JS.splitlines() if line.startswith('async function retrySocialV11'))
    script=r'''
const state={run:null},g={},calls=[];
function activeChunkV2(){return {id:'beat_7',action:'BROLL'}}
function galleryStateV9(){return g}
function orderedSocialV9(){return [1,2]}
async function researchBeatV2(...args){calls.push(args)}
'''+retry+r'''
(async()=>{
 const s={retryOptions:{variation_round:2,query_overrides:{s1:'bus india pov'},visual_verify:false}};
 await retrySocialV11('tiktok',s);
 if(calls.length!==1||calls[0][0]!=='append'||calls[0][1].join()!=='tiktok')throw Error('Wrong retry scope');
 if(calls[0][2].query_overrides.s1!=='bus india pov'||g.pending.round!==2)throw Error('Lost options');
 state.run='busy';await retrySocialV11('tiktok',s);if(calls.length!==1)throw Error('Concurrent retry');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    p=subprocess.run(['node','-e',script],capture_output=True,text=True,encoding='utf-8')
    assert p.returncode==0,p.stderr

def test_window_failure_is_visible_in_captcha_notice():
    show=next(line for line in JS.splitlines() if line.startswith('async function showChallengeWindowV11'))
    script="async function api(){throw Error('browser unavailable')}let rendered=0;function renderSearchStatusV9(){rendered++}"+show+";(async()=>{const s={};await showChallengeWindowV11('tiktok',s,{});if(!s.windowMessage.includes('browser unavailable')||rendered!==1)throw Error('Hidden failure')})().catch(e=>{console.error(e);process.exitCode=1});"
    p=subprocess.run(['node','-e',script],capture_output=True,text=True,encoding='utf-8')
    assert p.returncode==0,p.stderr
