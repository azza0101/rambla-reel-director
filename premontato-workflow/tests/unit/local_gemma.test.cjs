const {test}=require('node:test');
const assert=require('node:assert/strict');
const {localRequest,weakNameOnly}=require('../../runtime/premontato/local_gemma');
test('local payload removes cloud-only options and disables thinking',()=>{
 const body=localRequest({model:'cloud',reasoning_effort:'none',max_completion_tokens:900,messages:[]});
 assert.equal(body.model,'local');assert.equal(body.max_tokens,900);assert.equal(body.reasoning_effort,undefined);assert.equal(body.chat_template_kwargs.enable_thinking,false);
});
test('name guard preserves meaningful short dialogue',()=>{
 assert.equal(weakNameOnly('Mario! Mario!',['Mario']),true);
 assert.equal(weakNameOnly('Mario, vieni subito',['Mario']),false);
 assert.equal(weakNameOnly('Un prosciutto!',['Mario']),false);
});
const fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path');
const {GroqClient}=require('../../runtime/premontato/local_gemma');
test('a replacement client shuts down the previous local owner for the same data root',()=>{
 const root=path.join(os.tmpdir(),'same-owner-test');const first=new GroqClient(root);let killed=0;first.child={kill:()=>{killed++;}};first.endpoint='http://127.0.0.1:1';new GroqClient(root);assert.equal(killed,1);assert.equal(first.child,null);assert.equal(first.endpoint,null);
});
test('local classification schema permits only supplied beat numbers and exact utterance IDs',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'local-schema-'));let body;
 try{await fs.writeFile(path.join(root,'local-gemma.json'),JSON.stringify({enabled:true}));const c=new GroqClient(root,{fetchImpl:async(_url,o)=>{body=JSON.parse(o.body);return {status:200};}});c.ensureLocal=async()=> 'http://127.0.0.1:1';c.groundedScene={beats:[{number:2}]};await c.request('',{body:JSON.stringify({messages:[{role:'user',content:'Context\nUTTERANCES (1)\nS0 | real words'}]})},'classify');const schema=body.response_format.json_schema.schema;assert.deepEqual(schema.required,['S0']);assert.deepEqual(schema.properties.S0.enum,['X',2]);assert.equal(schema.additionalProperties,false);}finally{await fs.rm(root,{recursive:true,force:true});}
});
test('local requests stay on localhost and never forward cloud credentials',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'local-gemma-'));let target,options;
 try{await fs.writeFile(path.join(root,'local-gemma.json'),JSON.stringify({enabled:true}));const c=new GroqClient(root,{fetchImpl:async(u,o)=>{target=u;options=o;return {status:200};}});c.ensureLocal=async()=>{c.localToken='private-local';return 'http://127.0.0.1:25000';};await c.request('https://api.groq.com/openai/v1/chat/completions',{headers:{Authorization:'Bearer cloud-secret'},body:JSON.stringify({model:'cloud',max_completion_tokens:900})});assert.equal(target,'http://127.0.0.1:25000/v1/chat/completions');assert.equal(options.headers.Authorization,'Bearer private-local');assert.equal(c.status().model,'Gemma 4 locale');}finally{await fs.rm(root,{recursive:true,force:true});}
});
test('a local failure is surfaced without falling back to cloud',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'local-gemma-'));let calls=0;
 try{await fs.writeFile(path.join(root,'local-gemma.json'),JSON.stringify({enabled:true}));const c=new GroqClient(root,{fetchImpl:async()=>{calls++;}});c.ensureLocal=async()=>{throw Error('runtime unavailable');};await assert.rejects(c.request('https://api.groq.com/openai/v1/chat/completions',{body:'{}'}),/unavailable/);assert.equal(calls,0);}finally{await fs.rm(root,{recursive:true,force:true});}
});
