const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
test('every packaged top-level plugin file is allowed by existing updater',()=>{
 const root=path.join(__dirname,'../../plugin'),script=fs.readFileSync(path.join(root,'update.ps1'),'utf8');
 const list=/\$pluginFiles=@\(([^\n]+)\)/.exec(script)[1];const allowed=[...list.matchAll(/'([^']+)'/g)].map(m=>m[1]);
 const files=fs.readdirSync(root).filter(f=>/\.(js|json|xml|html|css|ps1)$/.test(f));assert.deepEqual(files.filter(f=>!allowed.includes(f)),[]);
});
