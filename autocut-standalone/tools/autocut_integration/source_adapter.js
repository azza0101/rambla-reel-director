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
 const context={path:String(path),project_name:String(await project.GetName()),timeline_id:String(await timeline.GetUniqueId()),timeline_name:String(await timeline.GetName())};
 const marks=await timeline.GetMarkInOut()||{},v=marks.video||{},a=marks.audio||{};
 const marked=r=>r.in!=null||r.out!=null;
 if(marked(v)&&marked(a)&&(v.in!==a.in||v.out!==a.out))throw Error('IN e OUT audio/video diversi: allineali prima di importare');
 if(marked(v)||marked(a)){
  const range=marked(v)?v:a,base=Number(await timeline.GetStartFrame()),start=Number(await clip.GetStart()),end=Number(await clip.GetEnd());
  const lo=Math.max(0,(range.in==null?start-base:Number(range.in))+base-start);
  const hi=Math.min(end-start,(range.out==null?end-base:Number(range.out)+1)+base-start);
  if(!Number.isInteger(lo)||!Number.isInteger(hi)||hi<=lo)throw Error('IN OUT non interseca il video sorgente');
  context.source_range={in_frame:lo,out_frame:hi,fps:String(await timeline.GetSetting('timelineFrameRate'))};
 }
 return context;
}
module.exports={snapshot};
