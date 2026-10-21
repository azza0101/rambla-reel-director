'use strict';
// Development tool. Produces an allowlisted distribution and code-only update.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),{FILES}=require('../plugin/updater'),version=require('../plugin/package.json').version;
const hashes={},files={};for(const name of FILES){const bytes=fs.readFileSync(path.join(root,'plugin',name));hashes[name]=crypto.createHash('sha256').update(bytes).digest('hex');files[name]=bytes.toString('base64')}
fs.writeFileSync(path.join(root,'install/checksums.json'),JSON.stringify(hashes,null,2));
fs.writeFileSync(path.join(root,'install/checksums.sha256'),FILES.map(name=>hashes[name]+'  '+name+'\n').join(''));
if(process.argv.includes('--checksums-only'))process.exit(0);
const out=path.join(root,'dist','RAMBLA-SRT-'+version);fs.mkdirSync(out,{recursive:true});
const distribution=[...FILES.map(n=>'plugin/'+n),'install/Install-Windows.ps1','install/install-mac.sh','install/checksums.json','install/checksums.sha256','INSTALLA_WINDOWS.cmd','INSTALLA_MAC.command','USAGE.md','MAC_DISTRIBUTION.md','VALIDATION.md'];
for(const name of distribution){const target=path.join(out,name);fs.mkdirSync(path.dirname(target),{recursive:true});fs.copyFileSync(path.join(root,name),target)}
const asset=`RAMBLA-SRT-${version}.json`,raw=Buffer.from(JSON.stringify({schema:1,id:'com.rambla.srt',version,files}));fs.writeFileSync(path.join(root,'dist',asset),raw);fs.writeFileSync(path.join(root,'dist','srt-update.json'),JSON.stringify({schema:1,id:'com.rambla.srt',version,asset,sha256:crypto.createHash('sha256').update(raw).digest('hex')},null,2));
console.log('Distribution: '+out);console.log('Update manifest: '+path.join(root,'dist','srt-update.json'));
