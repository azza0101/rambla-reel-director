const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path');
const {Session}=require('../../plugin/session');
const {saveCurrentProject}=require('../../plugin/resolve_adapter');
test('named project and autosave roundtrip analysis, drafts and confirmations; changed footage invalidates them',async()=>{
 const dir=await fs.mkdtemp(path.join(os.tmpdir(),'premontato-project-'));
 try{const mediaFile=path.join(dir,'footage.mp4');await fs.writeFile(mediaFile,'old');const file=path.join(dir,'scene.premontato.json');
 const s=new Session(dir,'unused');Object.assign(s.state,{stage:'review',script:{path:'script.pdf',text:'Ciao è così'},media:[{media_id:'m',name:'clip',path:mediaFile,duration_frames:100,fps:25}],transcripts:[{media_id:'m',segments:[]}],projectId:'p',timelineId:'t',analysis:{plan:{decisions:[{beat_id:'a',media_id:'m',take_id:'t',start_frame:0,end_frame:10}]},visualReview:{confirmed:true,intervals:[],faces:[]}},uiDraft:{visual:{person_names:{'person-1':'LUCA'}}}});
 await s.saveProject(file);await s.saveAutosave();
 const restored=new Session(dir,'unused');await restored.loadProject(file);assert.equal(restored.state.script.text,s.state.script.text);assert.equal(restored.state.analysis.visualReview.confirmed,true);assert.deepEqual(restored.state.analysis.plan.unmatched_beats,[]);assert.deepEqual(restored.state.analysis.plan.decisions[0].alternatives,[]);assert.deepEqual(restored.state.uiDraft,s.state.uiDraft);
 const recovered=new Session(dir,'unused');await recovered.restoreAutosave();assert.equal(recovered.state.projectId,'p');assert.equal(recovered.projectFile,file,'automatic recovery restores only the separate local save binding');
 const previous=recovered.state;await fs.writeFile(file,'{broken');await assert.rejects(recovered.loadProject(file));assert.equal(recovered.state,previous,'invalid files must not replace current work');
 await fs.writeFile(mediaFile,'changed file');await recovered.restoreAutosave();assert.equal(recovered.state.analysis,null);assert.deepEqual(recovered.state.transcripts,[]);assert.match(recovered.state.restoreWarning,/modificat|disponibil/i);
 }finally{await fs.rm(dir,{recursive:true,force:true});}
});
test('Resolve save checks expected project identity and treats false as failure',async()=>{
 let saves=0;const project={GetName:async()=>'Scene',GetUniqueId:async()=>'p'};const pm={GetCurrentProject:async()=>project,SaveProject:async()=>{saves++;return true;}};const sdk={GetResolvePromise:async()=>({GetProjectManager:async()=>pm})};
 assert.equal((await saveCurrentProject(sdk,'p')).projectId,'p');assert.equal(saves,1);
 await assert.rejects(saveCurrentProject(sdk,'other'),/progetto/i);assert.equal(saves,1);
 pm.SaveProject=async()=>false;await assert.rejects(saveCurrentProject(sdk,'p'),/salv/i);
});

test('failed replacement preserves the previous project bytes and save binding',async()=>{
 const dir=await fs.mkdtemp(path.join(os.tmpdir(),'premontato-atomic-'));const s=new Session(dir,'unused'),file=path.join(dir,'scene.json');
 try{await s.saveProject(file);const original=await fs.readFile(file,'utf8');const rename=fs.rename;fs.rename=async()=>{throw Error('disk failure');};try{s.state.script={text:'changed',path:'script.txt'};await assert.rejects(s.saveProject(file),/disk failure/);}finally{fs.rename=rename;}
 assert.equal(await fs.readFile(file,'utf8'),original);assert.equal(s.projectFile,file);assert.equal((await fs.readdir(dir)).some(name=>name.endsWith('.tmp')),false);
 }finally{await fs.rm(dir,{recursive:true,force:true});}
});

test('a screenplay-only project is saveable and recoverable before media selection',async()=>{
 const dir=await fs.mkdtemp(path.join(os.tmpdir(),'premontato-empty-'));try{const s=new Session(dir,'unused');s.state.script={path:'script.txt',text:'È una scena'};await s.saveAutosave();const restored=new Session(dir,'unused');await restored.restoreAutosave();assert.equal(restored.state.script.text,'È una scena');assert.deepEqual(restored.state.media,[]);}finally{await fs.rm(dir,{recursive:true,force:true});}
});

test('recovery does not overwrite a named project changed externally',async()=>{
 const dir=await fs.mkdtemp(path.join(os.tmpdir(),'premontato-newer-'));try{const s=new Session(dir,'unused'),file=path.join(dir,'scene.json');await s.saveProject(file);await s.saveAutosave();await fs.writeFile(file,'new external project bytes');const recovered=new Session(dir,'unused');await recovered.restoreAutosave();assert.equal(recovered.projectFile,null);await recovered.saveAutosave();assert.equal(await fs.readFile(file,'utf8'),'new external project bytes');}finally{await fs.rm(dir,{recursive:true,force:true});}
});

test('malformed persisted frame fields are rejected before replacing current work',async()=>{
 const dir=await fs.mkdtemp(path.join(os.tmpdir(),'premontato-schema-'));try{const s=new Session(dir,'unused'),file=path.join(dir,'bad.json'),before=s.state;
 await fs.writeFile(file,JSON.stringify({format:'premontato-project',schema_version:1,state:{media:[{media_id:'m',duration_frames:100,path:'clip.mp4'}],analysis:{plan:{decisions:[{beat_id:'a',media_id:'m',take_id:'t',start_frame:'0"><img src=x onerror=alert(1)>',end_frame:10}]}}}}));
 await assert.rejects(s.loadProject(file),/progetto|campo|intervallo/i);assert.equal(s.state,before);
 }finally{await fs.rm(dir,{recursive:true,force:true});}
});

test('background autosave detaches instead of overwriting an externally edited named file',async()=>{
 const dir=await fs.mkdtemp(path.join(os.tmpdir(),'premontato-live-external-'));try{const s=new Session(dir,'unused'),file=path.join(dir,'scene.json');await s.saveProject(file);await fs.writeFile(file,'external work');await s.saveAutosave();assert.equal(await fs.readFile(file,'utf8'),'external work');assert.equal(s.projectFile,null);assert.match(s.state.restoreWarning,/modificat/i);}finally{await fs.rm(dir,{recursive:true,force:true});}
});
