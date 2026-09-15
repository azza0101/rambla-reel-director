// Pure controller unit test: no browser, network, model, or user clipboard.
const vm=require('node:vm'), fs=require('node:fs'), assert=require('node:assert/strict');
const input=JSON.parse(fs.readFileSync(process.argv[2],'utf8')), elements=new Map(), requests=[];
function el(id){if(!elements.has(id))elements.set(id,{disabled:false,hidden:false,textContent:'',innerHTML:'',value:'',files:[],src:'',classList:{add(){},remove(){}},showModal(){this.open=true},close(){this.open=false},click(){},pause(){},removeAttribute(){}});return elements.get(id)}
const package={instructions:'Whole reel instructions',project_id:'p',chunks:[{id:'c1'}]}, plan={project_id:'p',visual_beats:[]};
let ready=false, fail=false, clipboard='';
const context={document:{getElementById:el,querySelectorAll:()=>[],createElement:()=>({click(){}})},window:{addEventListener(){}},location:{search:''},localStorage:{getItem:()=>null,setItem(){},removeItem(){}},URLSearchParams,URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},Blob,Map,Error,JSON,setTimeout,clearInterval,setInterval,navigator:{clipboard:{writeText:async s=>{clipboard=s}}},fetch:async(url,opts)=>{requests.push([url,opts]);let data={};if(url.endsWith('/editorial-input'))data=package;else if(url.endsWith('/editorial-plan')){if(fail)return{ok:false,json:async()=>({detail:'$.visual_beats: invalid coverage'})};ready=true;data={status:'imported'}}else if(url.endsWith('/curation'))data={analysis_ready:true,editorial_plan_ready:ready,chunks:[],selection_plan:{chunks:{}}};return{ok:true,json:async()=>data}}};
vm.createContext(context);
vm.runInContext(input.script.replace('draw();restore()})();','draw();globalThis.test={state,hydrate,draw,card};})();'),context);
(async()=>{
  context.test.state.pid='p';await context.test.hydrate();
  assert.equal(el('findImages').disabled,true);assert.equal(el('copyEditorial').disabled,false);
  await el('copyEditorial').onclick();assert.ok(clipboard.includes('Whole reel instructions'));assert.ok(clipboard.includes('"project_id": "p"'));
  el('importEditorial').onclick();assert.equal(el('importDialog').open,true);
  el('planJson').value=JSON.stringify(plan);fail=true;await el('applyPlan').onclick();assert.ok(el('importError').textContent.includes('invalid coverage'));assert.equal(el('importDialog').open,true);
  fail=false;await el('applyPlan').onclick();assert.equal(el('importDialog').open,false);assert.equal(el('findImages').disabled,false);assert.equal(el('findVideos').disabled,false);
  assert.equal(requests.filter(r=>r[0].endsWith('/editorial-plan')).length,2);
  el('planFile').files=[{text:async()=>'{"from":"file"}'}];await el('planFile').onchange();assert.equal(el('planJson').value,'{"from":"file"}');
  const assets=Array.from({length:8},(_,i)=>({asset_id:'v'+i,kind:'video',provider:i<4?'youtube':'pexels',title:'candidate '+i,preview_status:i<4?'preview_pending':'ready',selectable:i>=4,source_url:'https://example.com/'+i,source_page:'https://example.com/'+i,matched_query:'specific action',score:.75,source_start_seconds:i>=4?3:null,source_end_seconds:i>=4?6.5:null}));
  context.test.state.data={editorial_plan_ready:true,chunks:[{id:'b',text:'test beat',assets}],provider_status:{warnings:['Pexels key missing']},retrieval_warnings:['rerun old retrieval']};
  context.test.state.active='b';context.test.draw();
  assert.equal((el('videos').innerHTML.match(/<article/g)||[]).length,3);
  assert.equal((el('stockVideos').innerHTML.match(/<article/g)||[]).length,3);
  assert.ok(el('videos').innerHTML.includes('Source found / preview pending'));
  assert.ok(el('videos').innerHTML.includes('class="select" disabled'));
  assert.ok(el('stockVideos').innerHTML.includes('<video controls'));
  assert.ok(el('stockVideos').innerHTML.includes('3–6.5 s'));
  assert.ok(el('stockVideos').innerHTML.includes('<details><summary>Retrieval details'));
  assert.ok(el('providerWarnings').textContent.includes('Pexels key missing'));
  assert.ok(el('providerWarnings').textContent.includes('rerun old retrieval'));
  console.log('PASS editorial import, sourcing gate, separate shelves, pending disabled, clip ranges, expandable debug, warnings');
})().catch(e=>{console.error(e);process.exitCode=1});
