const {test}=require('node:test'),assert=require('node:assert/strict'),path=require('node:path');
const {invalidatePluginModules}=require('../../plugin/ipc_security');
test('reload removes every product JS/JSON module including transitive script code but preserves SDK and other plugins',()=>{
 const root=path.resolve('plugin');const files=['main.js','runtime/premontato/local_gemma.js','runtime/premontato/screenplay_structure.js','package.json','WorkflowIntegration.node'].map(f=>path.join(root,f));const outside=path.resolve('plugin-other/main.js');const cache=Object.fromEntries([...files,outside].map(f=>[f,{}]));invalidatePluginModules(cache,root);assert.deepEqual(Object.keys(cache).sort(),[files[4],outside].sort());
});
