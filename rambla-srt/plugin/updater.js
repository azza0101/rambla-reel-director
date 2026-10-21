'use strict';
// AutoCut safety architecture, isolated to this exact plugin. JSON/base64 bundles
// avoid ZIP extractors, path normalization ambiguity, symlinks and zip bombs.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {atomicJson}=require('./session');
const ID='com.rambla.srt',REPO='azza0101/rambla-reel-director';
const FILES=['main.js','preload.js','resolve_adapter.js','core.js','session.js','updater.js','index.html','style.css','renderer.js','package.json','manifest.xml'];
const MAX=8*1024*1024;
function version(v){if(typeof v!=='string'||!/^\d+\.\d+\.\d+$/.test(v)||v.split('.').some(x=>!Number.isSafeInteger(+x)))throw Error('Versione non valida');return v.split('.').map(Number)}
function compare(a,b){a=version(a);b=version(b);return a[0]-b[0]||a[1]-b[1]||a[2]-b[2]}
function selectRelease(releases){return releases.filter(r=>!r.draft&&!r.prerelease&&/^srt-\d+\.\d+\.\d+$/.test(r.tag_name)).sort((a,b)=>compare(b.tag_name.slice(4),a.tag_name.slice(4)))[0]||null}
function safeRoot(root){let p=path.resolve(root);while(true){if(fs.existsSync(p)&&fs.lstatSync(p).isSymbolicLink())throw Error('Percorso con link simbolico non consentito');const parent=path.dirname(p);if(parent===p)break;p=parent}}
function safeTargets(plugin){safeRoot(plugin);if(path.basename(plugin)!==ID)throw Error('Destinazione plugin non valida');for(const name of FILES){const p=path.join(plugin,name);if(fs.existsSync(p)&&(fs.lstatSync(p).isSymbolicLink()||!fs.statSync(p).isFile()))throw Error('File con link simbolico o tipo non valido')}}
function writeAtomic(target,bytes){const tmp=target+'.srt-'+crypto.randomUUID()+'.tmp';try{fs.writeFileSync(tmp,bytes,{flag:'wx',mode:0o600});fs.renameSync(tmp,target)}finally{if(fs.existsSync(tmp))fs.unlinkSync(tmp)}}
function validateManifest(m){if(m?.schema!==1||m.id!==ID||m.asset!==`RAMBLA-SRT-${m.version}.json`||! /^[a-f0-9]{64}$/.test(m.sha256))throw Error('Manifest SRT non valido');version(m.version)}
function decodeBundle(raw,m,current){validateManifest(m);if(raw.length>MAX||crypto.createHash('sha256').update(raw).digest('hex')!==m.sha256)throw Error('Dimensione o SHA256 pacchetto non valido');if(compare(m.version,current.version)<=0)throw Error('Versione non più recente');
 const b=JSON.parse(raw.toString('utf8'));if(b.schema!==1||b.id!==ID||b.version!==m.version||!b.files||Object.keys(b.files).length!==FILES.length)throw Error('Pacchetto SRT non valido');
 const files={};let total=0;for(const [name,encoded] of Object.entries(b.files)){if(!FILES.includes(name)||typeof encoded!=='string'||! /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(encoded))throw Error('File non consentito');const content=Buffer.from(encoded,'base64');total+=content.length;if(content.length>2*1024*1024||total>MAX)throw Error('Pacchetto troppo grande');files[name]=content}
 const pkg=JSON.parse(files['package.json']);if(pkg.name!=='rambla-srt'||pkg.version!==m.version||pkg.main!=='main.js'||pkg.dependencies||pkg.optionalDependencies||pkg.scripts)throw Error('Dipendenze o struttura cambiate: usa il nuovo installer');
 const manifest=files['manifest.xml'].toString();if(!manifest.includes('<Id>'+ID+'</Id>')||!manifest.includes('<Version>'+m.version+'</Version>'))throw Error('Identità manifest non valida');return files;
}
function rollback(plugin,data,backup){safeTargets(plugin);safeRoot(data);const backupRoot=path.resolve(data,'update-backups');backup=path.resolve(backup);if(path.dirname(backup)!==backupRoot)throw Error('Backup non valido');safeRoot(backup);const journal=JSON.parse(fs.readFileSync(path.join(backup,'journal.json')));if(journal.id!==ID||journal.plugin!==path.resolve(plugin))throw Error('Backup di altro plugin');
 for(const item of [...journal.files].reverse()){if(!FILES.includes(item.name)||!/^\d+$/.test(item.copy))throw Error('Backup non valido');const target=path.join(plugin,item.name);if(item.exists){const content=fs.readFileSync(path.join(backup,item.copy));if(crypto.createHash('sha256').update(content).digest('hex')!==item.sha256)throw Error('Backup corrotto');writeAtomic(target,content)}else if(fs.existsSync(target))fs.unlinkSync(target)}
 journal.status='rolled-back';atomicJson(path.join(backup,'journal.json'),journal);return {status:'rolled-back'};
}
function recover(plugin,data){const dir=path.join(data,'update-backups');if(!fs.existsSync(dir))return;for(const item of fs.readdirSync(dir)){const backup=path.join(dir,item),j=path.join(backup,'journal.json');if(fs.existsSync(j)&&JSON.parse(fs.readFileSync(j)).status==='applying')rollback(plugin,data,backup)}}
function applyBundle(plugin,data,raw,m){safeTargets(plugin);safeRoot(data);const current=JSON.parse(fs.readFileSync(path.join(plugin,'package.json'))),files=decodeBundle(raw,m,current);
 const backup=path.join(data,'update-backups',Date.now()+'-'+crypto.randomUUID());fs.mkdirSync(backup,{recursive:true});const journal={id:ID,plugin:path.resolve(plugin),status:'preparing',files:[]};
 for(const [index,name] of FILES.entries()){const target=path.join(plugin,name),exists=fs.existsSync(target),content=exists?fs.readFileSync(target):null;if(exists)fs.writeFileSync(path.join(backup,String(index)),content,{flag:'wx',mode:0o600});journal.files.push({name,exists,copy:String(index),sha256:exists?crypto.createHash('sha256').update(content).digest('hex'):null})}
 journal.status='applying';atomicJson(path.join(backup,'journal.json'),journal);
 try{for(const name of FILES)writeAtomic(path.join(plugin,name),files[name]);journal.status='applied';atomicJson(path.join(backup,'journal.json'),journal)}catch(e){try{rollback(plugin,data,backup)}catch(r){throw Error(e.message+'; ripristino incompleto: '+r.message+'; backup '+backup)}throw e}
 return {status:'updated',version:m.version,backup};
}
async function accessToken(env=process.env,run=require('node:util').promisify(require('node:child_process').execFile)){
 if(env.RAMBLA_SRT_GITHUB_TOKEN)return env.RAMBLA_SRT_GITHUB_TOKEN;
 try{const result=await run('gh',['auth','token','--hostname','github.com'],{windowsHide:true,timeout:5000,maxBuffer:16384});return result.stdout.trim()||null}catch{return null}
}
async function download(url,limit,accept='application/vnd.github+json'){
 const u=new URL(url);if(u.protocol!=='https:'||u.hostname!=='api.github.com'||!u.pathname.startsWith('/repos/'+REPO+'/'))throw Error('URL aggiornamento non consentito');
 const headers={Accept:accept,'User-Agent':'RAMBLA-SRT'};const token=await accessToken();if(token)headers.Authorization='Bearer '+token;
 const response=await fetch(url,{headers,signal:AbortSignal.timeout(20000),redirect:'manual'});
 let r=response;
 // GitHub release assets redirect to a signed public URL. Never forward a token.
 if([301,302,303,307,308].includes(r.status)){const location=new URL(r.headers.get('location'));if(location.protocol!=='https:'||!['release-assets.githubusercontent.com','objects.githubusercontent.com'].includes(location.hostname))throw Error('Redirect non consentito');r=await fetch(location,{signal:AbortSignal.timeout(20000),redirect:'error'})}
 if(!r.ok)throw Error(r.status===404?'Accesso GitHub richiesto: accedi con GitHub CLI (gh auth login) oppure configura RAMBLA_SRT_GITHUB_TOKEN.':'Controllo aggiornamento non riuscito ('+r.status+')');
 if(Number(r.headers.get('content-length'))>limit)throw Error('Download troppo grande');const chunks=[];let size=0;for await(const chunk of r.body){size+=chunk.length;if(size>limit){await r.body.cancel?.().catch(()=>{});throw Error('Download troppo grande')}chunks.push(Buffer.from(chunk))}return Buffer.concat(chunks);
}
async function check(current){const releases=JSON.parse(await download(`https://api.github.com/repos/${REPO}/releases?per_page=100`,MAX));const release=selectRelease(releases);if(!release)return {status:'unpublished'};if(compare(release.tag_name.slice(4),current)<=0)return {status:'current'};
 const asset=release.assets?.find(a=>a.name==='srt-update.json');if(!asset)throw Error('Manifest SRT mancante');const manifest=JSON.parse(await download(asset.url,65536,'application/octet-stream'));validateManifest(manifest);if(release.tag_name!=='srt-'+manifest.version)throw Error('Release e manifest non concordano');const bundle=release.assets.find(a=>a.name===manifest.asset);if(!bundle||bundle.size>MAX)throw Error('Pacchetto SRT mancante o troppo grande');return {status:'available',version:manifest.version,manifest,url:bundle.url};}
async function update(plugin,data){const current=JSON.parse(fs.readFileSync(path.join(plugin,'package.json'))).version,available=await check(current);if(available.status!=='available')return available;return applyBundle(plugin,data,await download(available.url,MAX,'application/octet-stream'),available.manifest)}
module.exports={accessToken,FILES,compare,selectRelease,applyBundle,rollback,recover,check,update,decodeBundle};
