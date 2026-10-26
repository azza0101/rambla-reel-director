// Native current-project test: only creates generated test timelines and imports synthetic sources.
const {spawn}=require('node:child_process'),readline=require('node:readline'),fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const version=require('../plugin/package.json').version;
const pluginRoot=path.resolve(__dirname,'../plugin'),fixtureRoot=path.resolve(process.argv[2]),{Session}=require('../plugin/session'),adapter=require('../plugin/resolve_adapter');
(async()=>{
 const child=spawn(process.env.PREMONTATO_SDK_PYTHON||'C:/Program Files/Python310/python.exe',['-B',path.join(__dirname,'day_catalog_native_bridge.py')],{windowsHide:true,stdio:['pipe','pipe','pipe']});const pending=new Map();let counter=0,stderr='';child.stderr.on('data',b=>stderr+=b);
 const proxy=id=>new Proxy({__handle__:id},{get:(target,key)=>key==='__handle__'?id:key==='then'||key==='toJSON'?undefined:(...args)=>new Promise((resolve,reject)=>{const request=++counter;pending.set(request,{resolve,reject});child.stdin.write(JSON.stringify({id:request,object:id,method:key,args})+'\n');})});
 const decode=v=>v&&typeof v==='object'?(Object.hasOwn(v,'__handle__')?proxy(v.__handle__):Array.isArray(v)?v.map(decode):Object.fromEntries(Object.entries(v).map(([k,x])=>[k,decode(x)]))):v;
 readline.createInterface({input:child.stdout}).on('line',line=>{const row=JSON.parse(line),p=pending.get(row.id);pending.delete(row.id);row.error?p.reject(Error(row.error)):p.resolve(decode(row.result));});
 child.on('exit',()=>{for(const p of pending.values())p.reject(Error(stderr||'Bridge exited'));});
 const resolve=proxy(0),sdk={GetResolvePromise:async()=>resolve};

 let session;const pm=await resolve.GetProjectManager(),project=await pm.GetCurrentProject(),pool=await project.GetMediaPool(),original=await project.GetCurrentTimeline(),originalFolder=await pool.GetCurrentFolder();
 const signature=async timeline=>{const rows=[];for(const type of ['video','audio'])for(let n=1;n<=await timeline.GetTrackCount(type);n++)for(const i of await timeline.GetItemListInTrack(type,n)||[])rows.push([type,n,await i.GetUniqueId(),await i.GetStart(),await i.GetEnd()]);return rows;};
 const before={settings:await project.GetSetting(),timelines:[]};for(let i=1;i<=await project.GetTimelineCount();i++){const t=await project.GetTimelineByIndex(i);before.timelines.push({id:await t.GetUniqueId(),signature:await signature(t)});}await fs.mkdir(fixtureRoot,{recursive:true});
 try{
  assert(await pm.SaveProject());const root=await pool.GetRootFolder();let testFolder=null;for(const f of await root.GetSubFolderList()||[])if(await f.GetName()==='Premontato - Test gap e numeri scena')testFolder=f;
  testFolder ||= await pool.AddSubFolder(root,'Premontato - Test gap e numeri scena');assert(await pool.SetCurrentFolder(testFolder));
  const inputs=await pool.ImportMedia(['catalog-mixed.mp4','catalog-takes.mp4'].map(n=>path.join(fixtureRoot,'..','catalog-repro-fixtures',n)));assert.equal(inputs.length,2);
  const media=[];for(const item of inputs){const p=await item.GetClipProperty();media.push({media_id:String(await item.GetMediaId()),name:await item.GetName(),path:p['File Path'],fps:Number(p.FPS),duration_frames:Number(p.Frames),start_tc:p['Start TC']});}assert(media.every(m=>m.duration_frames>=230&&m.fps===25));
  const decisions=[{beat_id:'b1',media_id:media[0].media_id,start_frame:0,end_frame:130,shot_size:'wide'},{beat_id:'b2',media_id:media[0].media_id,start_frame:150,end_frame:230,shot_size:'wide',reaction_overlay:{kind:'reaction',basis:'verified_listener',media_id:media[1].media_id,take_id:'t',start_frame:0,end_frame:40,offset_frames:20,shot_size:'close',speaker_coverage:'visible',enabled:true,evidence:{verified:true}}}];
  session=new Session(path.join(fixtureRoot,'user'),path.resolve(__dirname,'../worker/protocol.py'),process.env.PREMONTATO_PYTHON);session.state.analysis={script:{scenes:[{scene_id:'s1',heading:'SINTETICA UNO',beats:[{beat_id:'b1'}]},{scene_id:'s2',heading:'SINTETICA DUE',beats:[{beat_id:'b2'}]}]}};
  const started=Date.now(),debug=await session.prepareTimelineDebug(decisions,true,{fps:25,width:1920,height:1080});
  const result=await adapter.createTimeline(sdk,'PREMONTATO v'+version+' - DEBUG GAP E SCENE '+Date.now(),debug.decisions,{purpose:'test',media,projectId:String(await project.GetUniqueId()),timelineId:String(await original.GetUniqueId()),sceneDebug:debug.sceneDebug});
  assert.equal(result.sceneLabels,2);assert.equal(result.sceneGaps,1);let timeline;for(let n=1;n<=await project.GetTimelineCount();n++){const t=await project.GetTimelineByIndex(n);if(String(await t.GetUniqueId())===result.timelineId)timeline=t;}assert(timeline);
  const start=Number(await timeline.GetStartFrame()),picture=await timeline.GetItemListInTrack('video',2),sound=await timeline.GetItemListInTrack('audio',2),titles=await timeline.GetItemListInTrack('video',4),reactions=await timeline.GetItemListInTrack('video',3);
  const ranges=async items=>Promise.all(items.map(async i=>[Number(await i.GetStart())-start,Number(await i.GetEnd())-start]));assert.deepEqual(await ranges(picture),[[0,130],[180,260]]);assert.deepEqual(await ranges(sound),[[0,130],[180,260]]);assert.deepEqual(await ranges(titles),[[0,130],[180,260]]);assert.deepEqual(await ranges(reactions),[[200,240]]);
  const again=await session.prepareTimelineDebug(decisions,true,{fps:25,width:1920,height:1080});assert.deepEqual(again.sceneDebug.assets,debug.sceneDebug.assets);
  await fs.writeFile(path.join(fixtureRoot,'scene-debug-native.json'),JSON.stringify({...result,elapsed_ms:Date.now()-started,ranges:await ranges(titles),base:await ranges(picture),reactions:await ranges(reactions),original_preserved:true},null,2));console.log(JSON.stringify(result));
 }finally{
  session?.child?.kill();assert(await project.SetCurrentTimeline(original));assert(await pool.SetCurrentFolder(originalFolder));assert.deepEqual(await project.GetSetting(),before.settings);
  for(let n=1;n<=before.timelines.length;n++){const t=await project.GetTimelineByIndex(n);assert.equal(await t.GetUniqueId(),before.timelines[n-1].id);assert.deepEqual(await signature(t),before.timelines[n-1].signature);}assert(await pm.SaveProject());child.stdin.end();child.kill();
 }
})().catch(error=>{console.error(error);process.exit(1);});
