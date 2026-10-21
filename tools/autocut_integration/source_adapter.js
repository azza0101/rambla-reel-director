// Read-only native SDK adapter. No timeline mutation is exposed to the renderer.
async function snapshot(resolve){
 const manager=await resolve.GetProjectManager();
 const project=manager&&await manager.GetCurrentProject();
 if(!project)throw Error('Apri un progetto Resolve Studio');
 const timeline=await project.GetCurrentTimeline();
 if(!timeline)throw Error('Apri la timeline con il video completo');
 const clips=[];
 for(let track=1;track<=Number(await timeline.GetTrackCount('video'));track++){
  const items=await timeline.GetItemListInTrack('video',track)||[];
  clips.push(...items);
 }
 if(clips.length!==1)throw Error('Questa prima versione richiede una sola clip video integrale nella timeline');
 const clip=clips[0];
 if(Number(await clip.GetLeftOffset())>1||Number(await clip.GetRightOffset())>1)throw Error('Usa il video integrale: la clip nella timeline ha già dei tagli');
 const media=await clip.GetMediaPoolItem();
 const path=media&&await media.GetClipProperty('File Path');
 if(!path)throw Error('Il video deve avere un file originale disponibile, non una compound clip');
 return {path:String(path),project_name:String(await project.GetName()),timeline_id:String(await timeline.GetUniqueId()),timeline_name:String(await timeline.GetName())};
}
module.exports={snapshot};
