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
test('local requests stay on localhost and never forward cloud credentials',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'local-gemma-'));let target,options;
 try{await fs.writeFile(path.join(root,'local-gemma.json'),JSON.stringify({enabled:true}));const c=new GroqClient(root,{fetchImpl:async(u,o)=>{target=u;options=o;return {status:200};}});c.ensureLocal=async()=>{c.localToken='private-local';return 'http://127.0.0.1:25000';};await c.request('https://api.groq.com/openai/v1/chat/completions',{headers:{Authorization:'Bearer cloud-secret'},body:JSON.stringify({model:'cloud',max_completion_tokens:900})});assert.equal(target,'http://127.0.0.1:25000/v1/chat/completions');assert.equal(options.headers.Authorization,'Bearer private-local');assert.equal(c.status().model,'Gemma 4 locale');}finally{await fs.rm(root,{recursive:true,force:true});}
});
test('a local failure is surfaced without falling back to cloud',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'local-gemma-'));let calls=0;
 try{await fs.writeFile(path.join(root,'local-gemma.json'),JSON.stringify({enabled:true}));const c=new GroqClient(root,{fetchImpl:async()=>{calls++;}});c.ensureLocal=async()=>{throw Error('runtime unavailable');};await assert.rejects(c.request('https://api.groq.com/openai/v1/chat/completions',{body:'{}'}),/unavailable/);assert.equal(calls,0);}finally{await fs.rm(root,{recursive:true,force:true});}
});
