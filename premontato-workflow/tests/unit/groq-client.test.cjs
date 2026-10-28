const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path');
const {GroqClient,validateLabels,makeRequest}=require('../../runtime/premontato/groq_client');
const scene={beats:[{id:'b',number:1,kind:'dialogue',character:'ALICE',text:'Grazie'}],cast:{P1:'ALICE'},clips:[{key:'m',units:[{id:'S0',text:'Grazie',start:10,end:20}]}]};
test('request contains grounded text, never media paths or face payload',()=>{
 const q=makeRequest(scene,scene.clips[0]);const s=JSON.stringify(q);assert.match(s,/ALICE/);assert.match(s,/S0/);assert.equal(s.includes('start_frame'),false);assert.equal(q.model,'qwen/qwen3.8-27b');
});
test('classifier rejects missing, invented and unknown-role IDs',()=>{
 assert.throws(()=>validateLabels(scene,scene.clips[0],{}));assert.throws(()=>validateLabels(scene,scene.clips[0],{S0:'1/P9'}));assert.throws(()=>validateLabels(scene,scene.clips[0],{S0:'1/P1',S1:'X'}));assert.deepEqual(validateLabels(scene,scene.clips[0],{S0:'1/P1'}),{S0:'1/P1'});
});
test('second identical run reuses validated classification, altered text invalidates cache',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'premontato-groq-'));let calls=0;
 const c=new GroqClient(root,{keyProvider:()=> 'test-key',fetchImpl:async()=>{calls++;return {ok:true,status:200,json:async()=>({model:'qwen/qwen3.8-27b',choices:[{finish_reason:'stop',message:{content:'{"S0":"1/P1"}'}}]})};}});
 try{await c.classify(scene);const result=await c.classify(scene);assert.equal(calls,1);assert.equal(result.summary.cache_hits,1);const altered=structuredClone(scene);altered.clips[0].units[0].text='Grazie mille';await c.classify(altered);assert.equal(calls,2);}finally{await fs.rm(root,{recursive:true,force:true});}
});
test('truncated/refused output never becomes a cached classification',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'premontato-groq-'));
 const c=new GroqClient(root,{keyProvider:()=> 'test-key',fetchImpl:async()=>({ok:true,status:200,json:async()=>({choices:[{finish_reason:'length',message:{content:'{}'}}]})})});
 try{await assert.rejects(c.classify(scene),/incompleta/i);}finally{await fs.rm(root,{recursive:true,force:true});}
});

test('a malformed role is retried and only the validated replacement is cached',async()=>{const root=await fs.mkdtemp(path.join(os.tmpdir(),'premontato-groq-'));let calls=0;const c=new GroqClient(root,{keyProvider:()=> 'test-key',fetchImpl:async()=>({ok:true,status:200,json:async()=>({choices:[{finish_reason:'stop',message:{content:JSON.stringify({S0:++calls===1?'1/P9':'1/P1'})}}]})})});try{const result=await c.classify(scene);assert.equal(calls,2);assert.equal(result.labels.m.S0,'1/P1');await c.classify(scene);assert.equal(calls,2);}finally{await fs.rm(root,{recursive:true,force:true});}});

test('numeric beat labels resolve to existing screenplay roles locally',async()=>{const root=await fs.mkdtemp(path.join(os.tmpdir(),'premontato-groq-'));const c=new GroqClient(root,{keyProvider:()=> 'test-key',fetchImpl:async()=>({ok:true,status:200,json:async()=>({choices:[{finish_reason:'stop',message:{content:'{"S0":1}'}}]})})});try{const result=await c.classify(scene);assert.equal(result.labels.m.S0,'1/P1');}finally{await fs.rm(root,{recursive:true,force:true});}});

const dailyBody={error:{message:'Rate limit reached on tokens per day (TPD): Limit 200000, Used 199797, Requested 1312. Please try again in 7m59.087s.'}};
test('daily quota fails once with a precise resumable error instead of minute retries',async()=>{let calls=0,sleeps=0;const root=await fs.mkdtemp(path.join(os.tmpdir(),'premontato-daily-'));const c=new GroqClient(root,{keyProvider:()=> 'test-key',sleep:async()=>{sleeps++;},fetchImpl:async()=>{calls++;return {ok:false,status:429,json:async()=>dailyBody};}});try{await assert.rejects(c.classify(scene),e=>e.code==='GROQ_DAILY_QUOTA'&&e.retryAfterSeconds===480&&/giornaliera/.test(e.message));assert.equal(calls,1);assert.equal(sleeps,0);}finally{await fs.rm(root,{recursive:true,force:true});}});
test('minute quota still waits and retries the same grounded request',async()=>{let calls=0;const waits=[];const root=await fs.mkdtemp(path.join(os.tmpdir(),'premontato-minute-'));const c=new GroqClient(root,{keyProvider:()=> 'test-key',sleep:async ms=>waits.push(ms),fetchImpl:async()=>++calls===1?{ok:false,status:429,headers:{get:k=>k==='retry-after'?'2':null},json:async()=>({error:{message:'Tokens per minute, try again in 2s.'}})}:{ok:true,status:200,json:async()=>({choices:[{finish_reason:'stop',message:{content:'{"S0":1}'}}]})}});try{await c.classify(scene);assert.equal(calls,2);assert.deepEqual(waits,[2000]);}finally{await fs.rm(root,{recursive:true,force:true});}});
test('screenplay structuring and editorial calls respect daily quota without repeated requests',async()=>{for(const phase of ['script','editorial']){let calls=0,sleeps=0;const root=await fs.mkdtemp(path.join(os.tmpdir(),'premontato-phase-daily-'));const c=new GroqClient(root,{keyProvider:()=> 'test-key',sleep:async()=>{sleeps++;},fetchImpl:async()=>{calls++;return {ok:false,status:429,json:async()=>dailyBody};}});try{await assert.rejects(phase==='script'?c.prepareScript('SCENA 1\nALICE\nGrazie davvero.'):c.planEditorial(scene,{m:{S0:'1/P1'}},{}),e=>e.code==='GROQ_DAILY_QUOTA');assert.equal(calls,1);assert.equal(sleeps,0);}finally{await fs.rm(root,{recursive:true,force:true});}}});
