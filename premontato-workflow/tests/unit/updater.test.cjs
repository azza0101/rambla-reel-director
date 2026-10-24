'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { isNewerVersion, validateReleaseManifest, resolveGithubCredentialPath, findLatestUpdate, downloadVerifiedArchive } = require('../../plugin/updater');

test('detects semantic version updates without confusing 0.10 with 0.2', () => {
  assert.equal(isNewerVersion('0.10.0', '0.2.9'), true);
  assert.equal(isNewerVersion('0.2.0', '0.2.0'), false);
  assert.equal(isNewerVersion('0.1.9', '0.2.0'), false);
  assert.throws(() => isNewerVersion('latest', '0.2.0'), /versione/i);
});

test('accepts only a versioned Premontato release manifest with a matching archive digest', () => {
  const valid = { version: '0.3.0', archive: 'Premontato-0.3.0.zip', sha256: 'a'.repeat(64) };
  assert.deepEqual(validateReleaseManifest(valid, 'premontato-v0.3.0'), valid);
  assert.throws(() => validateReleaseManifest({ ...valid, archive: '../payload.zip' }, 'premontato-v0.3.0'), /manifest/i);
  assert.throws(() => validateReleaseManifest({ ...valid, sha256: 'bad' }, 'premontato-v0.3.0'), /manifest/i);
  assert.throws(() => validateReleaseManifest(valid, 'autocut-v0.3.0'), /tag/i);
});

test('finds the existing RMBL DPAPI credential through the installed Auto-Cut runtime config', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'premontato-auth-'));
  try {
    const programData = path.join(root, 'ProgramData');
    const autoCut = path.join(programData, 'Blackmagic Design', 'DaVinci Resolve', 'Support', 'Workflow Integration Plugins', 'com.rambla.autocut');
    const appRoot = path.join(root, 'qwen-embedding-smoke', 'api-first-v5-cloud');
    const credential = path.join(root, 'qwen-embedding-smoke', 'rambla-data', 'credentials', 'github-token.dpapi');
    fs.mkdirSync(autoCut, { recursive: true });
    fs.mkdirSync(path.dirname(credential), { recursive: true });
    fs.writeFileSync(path.join(autoCut, 'runtime.json'), JSON.stringify({ app_root: appRoot }));
    fs.writeFileSync(credential, Buffer.from('dpapi-placeholder'));
    assert.equal(resolveGithubCredentialPath(programData), credential);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});

test('does not derive a credential path from an untrusted runtime config', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'premontato-auth-'));
  try {
    const autoCut = path.join(root, 'Blackmagic Design', 'DaVinci Resolve', 'Support', 'Workflow Integration Plugins', 'com.rambla.autocut');
    fs.mkdirSync(autoCut, { recursive: true });
    fs.writeFileSync(path.join(autoCut, 'runtime.json'), JSON.stringify({ app_root: path.join(root, '..', 'outside') }));
    assert.equal(resolveGithubCredentialPath(root), null);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});

test('finds a newer private GitHub release and downloads only its hash-matched asset', async () => {
  const token = 'github_pat_' + 'x'.repeat(48);
  const archive = Buffer.from('premontato-test-update');
  const sha256 = require('node:crypto').createHash('sha256').update(archive).digest('hex');
  const manifest = Buffer.from(JSON.stringify({ version: '0.3.0', archive: 'Premontato-0.3.0.zip', sha256 }));
  const release = { tag_name: 'premontato-v0.3.0', draft: false, prerelease: false, assets: [
    { id: 11, name: 'premontato-update.json', size: manifest.length, url: 'https://api.github.com/repos/azza0101/rambla-reel-director/releases/assets/11' },
    { id: 12, name: 'Premontato-0.3.0.zip', size: archive.length, url: 'https://api.github.com/repos/azza0101/rambla-reel-director/releases/assets/12' }
  ] };
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url: String(url), accept: options.headers.Accept });
    if (String(url).endsWith('/releases?per_page=100')) return new Response(JSON.stringify([release]), { status: 200 });
    if (String(url).endsWith('/assets/11')) return new Response(manifest, { status: 200 });
    if (String(url).endsWith('/assets/12')) return new Response(archive, { status: 200 });
    return new Response('', { status: 404 });
  };
  const update = await findLatestUpdate('0.2.0', token, fetchImpl);
  assert.equal(update.status, 'available');
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'premontato-download-'));
  try {
    const destination = path.join(root, 'update.zip');
    await downloadVerifiedArchive(update, token, destination, fetchImpl);
    assert.deepEqual(fs.readFileSync(destination), archive);
    assert.equal(calls.filter(call => call.accept === 'application/octet-stream').length, 2);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});

test('reports current when the latest published release is not newer', async () => {
  const release = { tag_name: 'premontato-v0.3.0', draft: false, prerelease: false, assets: [] };
  const update = await findLatestUpdate('0.3.0', 'token', async () => new Response(JSON.stringify([release]), { status: 200 }));
  assert.deepEqual(update, { status: 'current', version: '0.3.0' });
});

test('checks dedicated Premontato prereleases without considering other products', async () => {
  const archive = Buffer.from('premontato-next');
  const digest = require('node:crypto').createHash('sha256').update(archive).digest('hex');
  const manifest = Buffer.from(JSON.stringify({ version: '0.3.1', archive: 'Premontato-0.3.1.zip', sha256: digest }));
  const release = { tag_name: 'premontato-v0.3.1', draft: false, prerelease: true, assets: [
    { id: 21, name: 'premontato-update.json', size: manifest.length, url: 'https://api.github.com/repos/azza0101/rambla-reel-director/releases/assets/21' },
    { id: 22, name: 'Premontato-0.3.1.zip', size: archive.length, url: 'https://api.github.com/repos/azza0101/rambla-reel-director/releases/assets/22' }
  ] };
  const other = { tag_name: 'autocut-v99.0.0', draft: false, prerelease: false, assets: [] };
  const fetchImpl = async url => {
    if (String(url).endsWith('/releases?per_page=100')) return new Response(JSON.stringify([other, release]), { status: 200 });
    if (String(url).endsWith('/assets/21')) return new Response(manifest, { status: 200 });
    if (String(url).endsWith('/assets/22')) return new Response(archive, { status: 200 });
    return new Response('', { status: 404 });
  };
  const update = await findLatestUpdate('0.3.0', 'token', fetchImpl);
  assert.equal(update.status, 'available');
  assert.equal(update.manifest.version, '0.3.1');
});

test('streams real download byte progress and never writes an unverified archive',async()=>{
 const archive=Buffer.from('abcdefgh'),hash=require('node:crypto').createHash('sha256').update(archive).digest('hex');
 const update={status:'available',archiveAsset:{url:'https://api.github.com/repos/azza0101/rambla-reel-director/releases/assets/900',size:8},manifest:{sha256:hash}};
 const makeResponse=async()=>new Response(new ReadableStream({start(controller){controller.enqueue(archive.subarray(0,3));controller.enqueue(archive.subarray(3));controller.close();}}));
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'premontato-progress-')),events=[];
 try{await downloadVerifiedArchive(update,'private',path.join(dir,'ok.zip'),makeResponse,event=>events.push(event));assert.deepEqual(events.filter(e=>e.phase==='download').map(e=>e.received),[0,3,8]);
 await assert.rejects(downloadVerifiedArchive({...update,manifest:{sha256:'0'.repeat(64)}},'private',path.join(dir,'bad.zip'),makeResponse),/SHA-256/);assert.equal(fs.existsSync(path.join(dir,'bad.zip')),false);
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
test('panel restart keeps the Resolve host process and reloads only after cleanup succeeds',async()=>{
 const {restartPlugin}=require('../../plugin/updater'),order=[];const app={relaunch:()=>order.push('relaunch'),quit:()=>order.push('quit')};
 await restartPlugin(app,async()=>order.push('saved'),{execPath:'C:/Resolve/Electron/electron.exe',reload:async()=>order.push('reload')});assert.deepEqual(order,['saved','reload']);
 order.length=0;await assert.rejects(restartPlugin(app,async()=>{throw Error('save failed');},{execPath:'C:/Resolve/Electron/electron.exe'}));assert.deepEqual(order,[]);
 await assert.rejects(restartPlugin(app,async()=>{}, {execPath:'C:/Resolve/Resolve.exe'}),/Electron/);
});

test('installer progress pipe is informational and cannot turn a failed install into success',async()=>{
 const {runUpdateInstaller}=require('../../plugin/updater'),{EventEmitter}=require('node:events'),net=require('node:net');
 const fixture=fs.mkdtempSync(path.join(os.tmpdir(),'premontato-installer-pipe-'));fs.writeFileSync(path.join(fixture,'package.json'),JSON.stringify({version:'1.0.0'}));
 const run=code=>{const events=[];return {events,promise:runUpdateInstaller({script:'update.ps1',pluginRoot:fixture,archivePath:'archive',sha256:'a'.repeat(64),version:'1.0.0',onProgress:event=>events.push(event),spawnImpl:(_exe,args)=>{
 const child=new EventEmitter();setImmediate(()=>{const name=args[args.indexOf('-ProgressPipe')+1],address=process.platform==='win32'?'\\\\.\\pipe\\'+name:path.join(os.tmpdir(),name+'.sock');const socket=net.connect(address,()=>socket.end(JSON.stringify({phase:'extract',current:2,total:4})+'\n'+JSON.stringify({phase:'exec',current:4,total:4})+'\n'+JSON.stringify({phase:'install',current:4,total:4})+'\n'));socket.on('error',error=>child.emit('error',error));socket.on('close',()=>child.emit('exit',code));});return child;}})};};
 try{const ok=run(0);await ok.promise;assert.deepEqual(ok.events.map(e=>[e.phase,e.percent]),[['extract',50],['install',100]]);
 const bad=run(1);await assert.rejects(bad.promise,/installazione precedente/);}finally{fs.rmSync(fixture,{recursive:true,force:true});}
});

test('installer success requires the requested version to be present on disk',async()=>{
 const {runUpdateInstaller}=require('../../plugin/updater'),{EventEmitter}=require('node:events');const dir=fs.mkdtempSync(path.join(os.tmpdir(),'premontato-install-version-'));
 try{fs.writeFileSync(path.join(dir,'package.json'),JSON.stringify({version:'0.7.0'}));
 await assert.rejects(runUpdateInstaller({script:'update.ps1',pluginRoot:dir,archivePath:'x',sha256:'a'.repeat(64),version:'0.9.0',spawnImpl:()=>{const child=new EventEmitter();setImmediate(()=>child.emit('exit',0));return child;}}),/versione|installat/i);
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
test('installer exposes a redacted local failure detail rather than only a generic error',async()=>{
 const {runUpdateInstaller}=require('../../plugin/updater'),{EventEmitter}=require('node:events'),{PassThrough}=require('node:stream');
 await assert.rejects(runUpdateInstaller({script:'update.ps1',pluginRoot:'plugin',archivePath:'x',sha256:'a'.repeat(64),version:'0.9.0',spawnImpl:()=>{const child=new EventEmitter();child.stderr=new PassThrough();setImmediate(()=>{child.stderr.write('File in uso github_pat_'+'s'.repeat(40));child.emit('exit',1);});return child;}}),error=>/File in uso/.test(error.message) && !error.message.includes('s'.repeat(40)));
});
