const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {transformFile,PROFILE}=require('../../tools/omnicut_test_product.cjs');
const root=path.resolve(__dirname,'../..'),read=p=>fs.readFileSync(path.join(root,p),'utf8'),render=p=>transformFile(p,read(p),'0.1.0');
test('parallel product has isolated registration, data, IPC and backups without changing source',()=>{
 const before=read('plugin/main.js'),main=render('plugin/main.js');new vm.Script(main);assert.match(main,/com\.rambla\.omnicut\.test/);assert.doesNotMatch(main,/com\.rambla\.premontato|premontato:/);assert.match(main,/'RAMBLA', 'Omni-Cut test'/);assert.match(main,/omnicut-test:/);assert.equal(read('plugin/main.js'),before);
 const preload=render('plugin/preload.js');new vm.Script(preload);assert.match(preload,/omnicut-test:/);assert.doesNotMatch(preload,/premontato:/);
 const manifest=render('plugin/manifest.xml'),pkg=JSON.parse(render('plugin/package.json'));assert.match(manifest,/<Id>com\.rambla\.omnicut\.test<\/Id>/);assert.match(manifest,/<Name>RAMBLA Omni-Cut test<\/Name>/);assert.equal(pkg.name,'rambla-omnicut-test');assert.equal(pkg.version,'0.1.0');
 for(const file of ['install/Install-Premontato.ps1','plugin/update.ps1']){const s=render(file);assert.match(s,/com\.rambla\.omnicut\.test/);assert.doesNotMatch(s,/com\.rambla\.premontato|rambla-premontato/);assert.match(s,/Omni-Cut test.*Backups/);}
});
function updater(){const module={exports:{}};const content=render('plugin/updater.js');vm.runInNewContext(content,{require,module,exports:module.exports,Buffer,process,URL,AbortSignal,globalThis:{},setTimeout,clearTimeout,TextDecoder,console});return module.exports;}
test('Omni-Cut update manifest cannot accept Premontato packages or tags',()=>{const u=updater(),digest='a'.repeat(64);assert.equal(u.validateReleaseManifest({version:'0.1.1',archive:'OmniCutTest-0.1.1.zip',sha256:digest},'omnicut-test-v0.1.1').version,'0.1.1');assert.throws(()=>u.validateReleaseManifest({version:'0.1.1',archive:'Premontato-0.1.1.zip',sha256:digest},'premontato-v0.1.1'));});
test('Omni-Cut update discovery ignores newer other-product releases and uses its own assets',async()=>{
 const u=updater(),digest='a'.repeat(64),payload=Buffer.from(JSON.stringify({version:'0.1.1',archive:'OmniCutTest-0.1.1.zip',sha256:digest})),release={tag_name:'omnicut-test-v0.1.1',draft:false,prerelease:true,assets:[{name:'omnicut-test-update.json',url:'https://api.github.com/repos/azza0101/rambla-reel-director/releases/assets/1',size:payload.length},{name:'OmniCutTest-0.1.1.zip',url:'https://api.github.com/repos/azza0101/rambla-reel-director/releases/assets/2',size:50}]};let calls=0;
 const fetch=async url=>{calls++;return String(url).endsWith('/1')?{ok:true,arrayBuffer:async()=>payload}:{ok:true,json:async()=>[{tag_name:'premontato-v99.0.0',draft:false},{tag_name:'v9999',draft:false},release]};};
 const found=await u.findLatestUpdate('0.1.0','fake',fetch);assert.equal(found.status,'available');assert.equal(found.manifest.version,'0.1.1');assert.equal(found.manifest.archive,'OmniCutTest-0.1.1.zip');assert.equal(calls,2);
});
test('build profile refuses malformed versions and transforms only audited text files',()=>{assert.throws(()=>transformFile('plugin/package.json',read('plugin/package.json'),'../bad'),/version/i);assert.equal(transformFile('worker/staged_dialogue.py','Premontato'),'Premontato');assert.equal(PROFILE.id,'com.rambla.omnicut.test');});

test('parallel panel shows its own version before the bridge connects',()=>{const html=render('plugin/index.html');assert.match(html,/<title>RAMBLA Omni-Cut test v0\.1\.0<\/title>/);assert.match(html,/id="version"[^>]*>v0\.1\.0/);assert.doesNotMatch(html,/v0\.12\.1/);});
