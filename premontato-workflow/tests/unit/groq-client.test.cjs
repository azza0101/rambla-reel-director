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
