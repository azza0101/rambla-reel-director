'use strict';
// Build-time product profile: the editing engine remains shared and unchanged.
const fs=require('node:fs/promises'),path=require('node:path');
const PROFILE=Object.freeze({id:'com.rambla.omnicut.test',name:'RAMBLA Omni-Cut test',packageName:'rambla-omnicut-test',dataFolder:'Omni-Cut test',releasePrefix:'omnicut-test-v',archivePrefix:'OmniCutTest-',manifest:'omnicut-test-update.json'});
const audited=new Set(['plugin/main.js','plugin/preload.js','plugin/manifest.xml','plugin/package.json','plugin/index.html','plugin/renderer.js','plugin/updater.js','plugin/update.ps1','plugin/resolve_adapter.js','plugin/day_catalog_resolve.js','install/Install-Premontato.ps1','tools/build_installer.ps1','tools/build_update.ps1','tools/launcher/Program.cs']);
function transformFile(file,text,version='0.1.0'){
 if(!/^\d+\.\d+\.\d+$/.test(version))throw Error('Invalid product version');
 file=file.replaceAll('\\','/');if(!audited.has(file))return text;
 if(file==='plugin/package.json'){const p=JSON.parse(text);p.name=PROFILE.packageName;p.version=version;p.product='Omni-Cut test';return JSON.stringify(p,null,2)+'\n';}
 let s=text.replaceAll('com.rambla.premontato',PROFILE.id).replaceAll('rambla-premontato',PROFILE.packageName).replaceAll('premontato:', 'omnicut-test:').replaceAll('premontato-v',PROFILE.releasePrefix).replaceAll('premontato-update', 'omnicut-test-update');
 s=s.replaceAll('Premontato-',PROFILE.archivePrefix).replaceAll('RAMBLA Premontato',PROFILE.name);
 if(file==='plugin/main.js')s=s.replace("'RAMBLA', 'Premontato'","'RAMBLA', 'Omni-Cut test'");
 if(file==='plugin/manifest.xml')s=s.replace(/<Version>[^<]+<\/Version>/,'<Version>'+version+'</Version>');
 if(file==='plugin/index.html')s=s.replaceAll('Premontato','Omni-Cut test').replace(/(<title>[^<]* v)\d+\.\d+\.\d+/,'$1'+version).replace(/(id="version"[^>]*>)v[^<]*/,'$1v'+version);
 if(file==='plugin/resolve_adapter.js')s=s.replace("['Premontato',","['Omni-Cut test',");
 if(file==='plugin/day_catalog_resolve.js')s=s.replaceAll('Premontato - Catalogo Giornata','Omni-Cut test - Catalogo Giornata');
 if(file==='plugin/main.js'||file==='plugin/resolve_adapter.js')s=s.replaceAll('PREMONTATO','OMNI-CUT TEST');
 if(file==='plugin/updater.js')s=s.replaceAll('[Premontato debug]','[Omni-Cut test debug]').replaceAll('diagnostica Premontato','diagnostica Omni-Cut test').replaceAll('canale Premontato','canale Omni-Cut test');
 if(file==='plugin/update.ps1'){
  s=s.replace(/\r\n/g,'\n');
  const anchor="\n} catch {\n    Send-UpdateProgress 'rollback' 0 1";
  if(!s.includes(anchor))throw Error('Updater success/rollback boundary missing');
  s=s.replace(anchor,"\n    # OMNICUT_CLEANUP_SUCCESS: keep rollback until all replacements succeed.\n    try { if(Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction Stop } } catch { Write-Warning 'Backup temporaneo non rimosso; cancellalo manualmente.' }"+anchor);
 }
 return s;
}
async function createProductTree(source,destination,version){
 source=path.resolve(source);destination=path.resolve(destination);
 if(destination===source || source.startsWith(destination+path.sep))throw Error('Output must not contain the source tree');
 try{await fs.lstat(destination);throw Error('Product output already exists');}catch(e){if(e.code!=='ENOENT')throw e;}
 const files=[];
 for(const dir of ['plugin','worker','install'])for(const entry of await fs.readdir(path.join(source,dir),{withFileTypes:true}))if(entry.isFile() && (dir==='worker'?/\.(py|txt)$/.test(entry.name):dir==='install'?entry.name==='Install-Premontato.ps1':/\.(js|json|xml|html|css|ps1)$/.test(entry.name)))files.push(dir+'/'+entry.name);
 files.push('tools/build_installer.ps1','tools/build_update.ps1','tools/build_runtime.ps1','tools/prepare_models.ps1','tools/launcher/Program.cs','tools/launcher/app.manifest');
 for(const file of files){const target=path.join(destination,file);await fs.mkdir(path.dirname(target),{recursive:true});await fs.writeFile(target,transformFile(file,await fs.readFile(path.join(source,file),'utf8'),version));}
 return {profile:PROFILE,version,files:files.length,destination};
}
if(require.main===module)createProductTree(process.argv[2],process.argv[3],process.argv[4]||'0.1.0').then(r=>console.log(JSON.stringify(r))).catch(e=>{console.error(e.message);process.exitCode=1;});
module.exports={PROFILE,transformFile,createProductTree};
