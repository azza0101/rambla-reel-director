const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
test('visual review toggles open and closed without repeated analysis, labels follow nested visibility',async()=>{
 const source=fs.readFileSync(path.join(__dirname,'../../plugin/renderer.js'),'utf8');
 const start=source.indexOf('function syncVisualVisibility('),end=source.indexOf("$('load-visual-review').addEventListener",start);
 const nodes=new Map();const $=id=>{if(!nodes.has(id))nodes.set(id,{hidden:true,disabled:false,setAttribute(k,v){this[k]=v;}});return nodes.get(id);};
 let loads=0;const state={analysis:{}},window={__lastReviewState:state,premontato:{loadVisualReview:async()=>{loads++;state.analysis.visualReview={intervals:[]};return state;}}};
 const context={$,window,visualReviewOpen:false,render:()=>context.syncVisualVisibility(state),message:()=>{},showError:e=>{throw e;}};
 vm.createContext(context);vm.runInContext(source.slice(start,end),context);
 await context.toggleVisualReview();assert.equal(loads,1);assert.equal($('visual-review').hidden,false);assert.match($('load-visual-review').textContent,/^Chiudi/);
 await context.toggleVisualReview();assert.equal($('visual-review').hidden,true);assert.match($('load-visual-review').textContent,/^Apri/);
 await context.toggleVisualReview();assert.equal(loads,1);assert.equal($('visual-review').hidden,false);
 $('visual-people-panel').hidden=false;context.syncVisualVisibility();assert.match($('visual-faces-toggle').textContent,/^Chiudi/);
 $('visual-people-panel').hidden=true;context.syncVisualVisibility();assert.match($('visual-faces-toggle').textContent,/^Apri/);
 context.visualReviewOpen=false;context.syncVisualVisibility(state);assert.equal($('visual-review').hidden,true);
});
test('timeline creation is an explicit click without a final checkbox',()=>{
 const html=fs.readFileSync(path.join(__dirname,'../../plugin/index.html'),'utf8'),js=fs.readFileSync(path.join(__dirname,'../../plugin/renderer.js'),'utf8');
 assert.doesNotMatch(html,/id="reviewed"/);assert.equal(js.includes("$('reviewed')"),false);assert.match(js,/createReviewTimeline\(\{confirmed:true,sceneDebug:/);assert.match(html,/id="scene-debug"[^>]*checked/);
});
