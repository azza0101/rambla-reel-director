const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path');
const {GroqClient}=require('../../runtime/premontato/groq_client');
test('OpenRouter credential is encrypted, stored independently, and never returned by status',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'omni-credentials-'));
 const vault={isEncryptionAvailable:()=>true,encryptString:s=>Buffer.from('encrypted:'+s),decryptString:b=>b.toString().slice(10)};
 try {const c=new GroqClient(root,{vault}); const key='sk-or-v1-abcdefghijklmnopqrstuv'; assert.equal(c.openRouterStatus().configured,false); await c.configureOpenRouter(key); const data=await fs.readFile(path.join(root,'credentials','openrouter-key.bin'),'utf8');assert.notEqual(data,key);assert.equal(data,'encrypted:'+key);assert.deepEqual(c.openRouterStatus(),{configured:true});assert.ok(!JSON.stringify(c.openRouterStatus()).includes(key));await assert.rejects(c.configureOpenRouter('bad'),/non valida/);}
 finally {await fs.rm(root,{recursive:true,force:true});}
});
test('OpenRouter credential cannot be saved without OS encryption',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'omni-credentials-'));
 try {const c=new GroqClient(root,{vault:{isEncryptionAvailable:()=>false}});await assert.rejects(c.configureOpenRouter('sk-or-v1-abcdefghijklmnopqrstuv'),/Protezione/);}
 finally {await fs.rm(root,{recursive:true,force:true});}
});
