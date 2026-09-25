import json,subprocess

def test_animation_export_orders_timestamps_and_marks_only_adjacent_phrases():
    from backend.app.animation_export_ui import BUILD_JS
    cases=r'''
const chunks=[{id:'a',text:'Uno',start:0.1,end:1.25},{id:'b',text:'Due',start:1.5,end:3},{id:'c',text:'Tre',start:3,end:4},{id:'d',text:'Quattro',start:5,end:7.75}];
const result=buildAnimationExport(chunks,new Set(['d','b','a']),'project');
const phrases=result.items.filter(x=>x.type==='phrase');
if(phrases.map(x=>x.id).join(',')!=='a,b,d')throw Error('Order');
if(phrases[0].duration_seconds!==1.15)throw Error('Duration');
if(!phrases[1].concatenated_with_previous||phrases[2].concatenated_with_previous)throw Error('Adjacency');
if(phrases[1].gap_from_previous_seconds!==.25)throw Error('Pause');
if(result.items.filter(x=>x.type==='separator').length!==2)throw Error('Separators');
if(result.phrase_count!==3)throw Error('Count');
if(buildAnimationExport(chunks,new Set(['unknown']),'p').phrase_count!==0)throw Error('Stale selection');
for(const bad of [null,undefined,'',NaN]){
 let failed=false;try{buildAnimationExport([{id:'x',start:bad,end:2}],new Set(['x']),'p')}catch(e){failed=true}
 if(!failed)throw Error('Invalid timing accepted');
}
console.log(JSON.stringify(result));
'''
    run=subprocess.run(['node','-e',BUILD_JS+cases],capture_output=True,text=True,encoding='utf-8')
    assert run.returncode==0,run.stderr
    payload=json.loads(run.stdout)
    assert payload['schema_version']=='rambla-animation-phrases-1'

def test_animation_multi_select_does_not_change_active_beat_or_media_selection():
    from backend.app.animation_export_ui import JS
    harness=r'''
const nodes={};
function node(id){return nodes[id]||(nodes[id]={id,innerHTML:'',textContent:'',classList:{toggle(){}},setAttribute(){},prepend(){},before(){}})}
const $=node,document={getElementById:node,createElement:()=>node('created')};
let state={pid:'p',active:'a',sel:new Map([['a',['media-1']]]),data:{chunks:[{id:'a',start:0,end:1,text:'A'},{id:'b',start:1,end:2,text:'B'}]}};
let buttons=[];let draw=()=>{buttons=state.data.chunks.map(c=>({...node('phrase-'+c.id),dataset:{c:c.id},onclick:()=>{state.active=c.id}}));node('phrases').querySelectorAll=()=>buttons};
'''
    checks=r'''
draw();node('animationToggle').onclick();
buttons[0].onclick();buttons[1].onclick();
if(animationSelected().size!==2)throw Error('Multiple selection failed');
if(state.active!=='a'||state.sel.get('a')[0]!=='media-1')throw Error('Changed curation');
if(JSON.parse(animationJson()).phrase_count!==2)throw Error('Export missing selection');
draw();if(animationSelected().size!==2)throw Error('Redraw lost selection');
buttons[0].onclick();if(animationSelected().size!==1)throw Error('Cannot deselect');
state.pid='other';draw();if(animationSelected().size!==0||animationMode)throw Error('Project leak');
state.pid='p';draw();if(animationSelected().size!==1)throw Error('Project selection lost');
node('animationToggle').onclick();node('animationClear').onclick();if(animationSelected().size)throw Error('Clear failed');
'''
    run=subprocess.run(['node','-e',harness+JS+checks],capture_output=True,text=True,encoding='utf-8')
    assert run.returncode==0,run.stderr
