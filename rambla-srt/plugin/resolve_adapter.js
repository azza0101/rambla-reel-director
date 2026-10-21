'use strict';
const {createHash}=require('node:crypto');
const hash=value=>createHash('sha256').update(JSON.stringify(value)).digest('hex');
async function identity(resolve){const manager=await resolve.GetProjectManager(),project=manager&&await manager.GetCurrentProject();if(!project)throw Error('Apri un progetto Resolve Studio');const timeline=await project.GetCurrentTimeline();if(!timeline)throw Error('Apri una timeline');const projectId=await project.GetUniqueId(),timelineId=await timeline.GetUniqueId();if(!projectId||!timelineId)throw Error('Identità progetto/timeline non disponibile');return {project,timeline,projectId:String(projectId),timelineId:String(timelineId)}}
async function snapshot(resolve){
 const first=await identity(resolve),tl=first.timeline;
 const timeline={name:String(await tl.GetName()),fps:Number(await tl.GetSetting('timelineFrameRate')),start:Number(await tl.GetStartFrame()),finish:Number(await tl.GetEndFrame()),startTC:String(await tl.GetStartTimecode())};
 if(!Number.isFinite(timeline.fps)||timeline.fps<=0||!Number.isFinite(timeline.start)||!Number.isFinite(timeline.finish))throw Error('Dati temporali timeline non leggibili');
 const marks=await tl.GetMarkInOut();let range=null;
 for(const kind of ['video','audio']){const m=marks?.[kind];if(m?.in==null||m?.out==null)continue;let a=Number(m.in),b=Number(m.out);if(!Number.isFinite(a)||!Number.isFinite(b)||b<=a)continue;
  // Deliberately matches V3.1; do not silently adopt AutoCut's inclusive OUT.
  if(timeline.start>0&&a<timeline.start&&(b<=timeline.finish-timeline.start||timeline.finish===0)){a+=timeline.start;b+=timeline.start}range={a,b};break;
 }
 const captions=[],tracks=Number(await tl.GetTrackCount('subtitle'));
 if(!Number.isInteger(tracks)||tracks<0)throw Error('Tracce sottotitoli non leggibili');
 for(let track=1;track<=tracks;track++){
  const items=await tl.GetItemListInTrack('subtitle',track);if(!items||typeof items!=='object')throw Error('Lista sottotitoli non leggibile');
  for(const [key,item] of Object.entries(items)){if(!/^\d+$/.test(key))continue;
   if(!item||typeof item.GetStart!=='function'||typeof item.GetEnd!=='function'||typeof item.GetName!=='function')throw Error(`Traccia ${track}: elemento non leggibile`);
   const a=Number(await item.GetStart()),b=Number(await item.GetEnd()),content=await item.GetName();
   if(!Number.isFinite(a)||!Number.isFinite(b)||typeof content!=='string')throw Error(`Traccia ${track}: sottotitolo non leggibile`);
   captions.push({a,b,content,track,idx:Number(key)});
  }
 }
 const last=await identity(resolve);if(first.projectId!==last.projectId||first.timelineId!==last.timelineId)throw Error('Timeline cambiata durante la lettura; aggiorna IN / OUT');
 const geometry=hash([first.projectId,first.timelineId,timeline.fps,timeline.start,timeline.startTC]);
 return {projectId:first.projectId,timelineId:first.timelineId,projectName:String(await first.project.GetName()),timeline,range,captions,geometry,fingerprint:hash([geometry,timeline,captions])};
}
module.exports={snapshot,identity};
