'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { timecodeToFrames, analyzeIntellisearchSelected, transcribeSelected, parsePeopleMetadata, getSelectedTranscriptions, createTimeline } = require('../../plugin/resolve_adapter');

test('parses Resolve IntelliSearch People tags into unique clip-level face labels', () => {
  assert.deepEqual(parsePeopleMetadata('Face 5,Face 1,Face 2, Face 1'), ['Face 5', 'Face 1', 'Face 2']);
  assert.deepEqual(parsePeopleMetadata(''), []);
});

test('transcribes only selected clips without cached text and enables speaker detection', async () => {
  let detected = false;
  const items = [
    { GetMediaId: async () => 'cached', GetTranscription: async () => ({ segments: [{ text: 'already done' }] }), TranscribeAudio: async () => { throw new Error('must reuse'); } },
    { GetMediaId: async () => 'new', GetTranscription: async () => ({}), TranscribeAudio: async value => { detected = value === true; return true; } }
  ];
  const sdk = { GetResolvePromise: async () => ({ GetProjectManager: async () => ({ GetCurrentProject: async () => ({
    GetCurrentTimeline: async () => ({}), GetMediaPool: async () => ({ GetSelectedClips: async () => items })
  }) }) }) };
  const events=[];
  assert.deepEqual(await transcribeSelected(sdk, event=>events.push(event)), [
    { media_id: 'cached', ok: true, reused: true }, { media_id: 'new', ok: true, reused: false }
  ]);
  assert.equal(detected, true);
  assert.deepEqual(events.map(e=>e.current),[0,1,1,2]);
  assert.equal(events.at(-1).total,2);
});

test('IntelliSearch is explicitly scoped to selected clips and enables face identification', async () => {
  const items = ['a', 'b'].map(id => ({ GetMediaId: async () => id, AnalyzeForIntellisearch: async (faces, better) => faces && !better }));
  const sdk = { GetResolvePromise: async () => ({ GetProjectManager: async () => ({ GetCurrentProject: async () => ({
    GetCurrentTimeline: async () => ({}), GetMediaPool: async () => ({ GetSelectedClips: async () => items })
  }) }) }) };
  assert.deepEqual(await analyzeIntellisearchSelected(sdk), [{ media_id: 'a', ok: true }, { media_id: 'b', ok: true }]);
});

test('IntelliSearch does nothing when no clips are selected', async () => {
  const sdk = { GetResolvePromise: async () => ({ GetProjectManager: async () => ({ GetCurrentProject: async () => ({
    GetCurrentTimeline: async () => ({}), GetMediaPool: async () => ({ GetSelectedClips: async () => [] })
  }) }) }) };
  await assert.rejects(analyzeIntellisearchSelected(sdk), /Seleziona i media/);
});

test('maps fractional-rate timecode by nominal frame labels', () => {
  assert.equal(timecodeToFrames('00:00:01:00', 23.976), 24);
});

test('removes skipped drop-frame labels', () => {
  assert.equal(timecodeToFrames('00:01:00;02', 29.97), 1800);
  assert.equal(timecodeToFrames('00:10:00;00', 29.97), 17982);
});

test('rejects malformed or unconfigured timecodes', () => {
  assert.throws(() => timecodeToFrames('bad', 25), /non valido/);
  assert.throws(() => timecodeToFrames('00:00:00:00', 0), /non valido/);
});

test('explains when Resolve selection is a timeline rather than source footage', async () => {
  const item = { GetMediaId: async () => 'timeline', GetName: async () => 'TEST-AUTO-EDIT',
    GetClipProperty: async () => ({ Type: 'Timeline', Frames: '0', 'File Path': '' }), GetMetadata: async () => '' };
  const sdk = { GetResolvePromise: async () => ({ GetProjectManager: async () => ({ GetCurrentProject: async () => ({
    GetName: async () => 'p', GetUniqueId: async () => 'p1', GetCurrentTimeline: async () => ({ GetName: async () => 't', GetUniqueId: async () => 't1', GetSetting: async () => '25' }),
    GetMediaPool: async () => ({ GetSelectedClips: async () => [item] })
  }) }) }) };
  await assert.rejects(getSelectedTranscriptions(sdk), /non è un file video valido/);
});

test('converts camera timecodes to clip-relative frame ranges', async () => {
  const item = {
    GetMediaId: async () => 'm1', GetName: async () => 'clip', GetClipProperty: async key => key === 'Start TC' ? '02:56:57:15' : ({ FPS: '25', Frames: '2500', Duration: '00:01:40:00', 'File Path': 'C:/clip.mp4' }),
    GetMetadata: async () => '', GetTranscription: async () => ({ segments: [{ start: '02:56:58:00', end: '02:56:59:00', text: 'ciao' }] })
  };
  const sdk = { GetResolvePromise: async () => ({ GetProjectManager: async () => ({ GetCurrentProject: async () => ({
    GetName: async () => 'p', GetUniqueId: async () => 'p1', GetCurrentTimeline: async () => ({ GetName: async () => 't', GetUniqueId: async () => 't1', GetSetting: async () => '25' }),
    GetMediaPool: async () => ({ GetSelectedClips: async () => [item] })
  }) }) }) };
  const [source] = await getSelectedTranscriptions(sdk);
  assert.equal(source.start_tc, '02:56:57:15');
  assert.equal(source.segments[0].start_frame, 10);
  assert.equal(source.segments[0].end_frame, 35);
});

test('preserves Resolve word-level timestamps as clip-relative phrase timings', async () => {
  const item = {
    GetMediaId: async () => 'm1', GetName: async () => 'clip', GetClipProperty: async key => key === 'Start TC' ? '02:56:57:15' : ({ FPS: '25', Frames: '2500', 'File Path': 'C:/clip.mp4' }),
    GetMetadata: async () => '', GetTranscription: async () => ({ segments: [{
      start: '02:56:58:00', end: '02:56:59:00', text: 'grazie mi avete salvata',
      words: [
        { start: '02:56:58:00', end: '02:56:58:05', text: 'grazie' },
        { start: '02:56:58:06', end: '02:56:58:09', text: 'mi' },
        { start: '02:56:58:09', end: '02:56:58:16', text: 'avete' },
        { start: '02:56:58:16', end: '02:56:59:00', text: 'salvata.' }
      ]
    }] })
  };
  const sdk = { GetResolvePromise: async () => ({ GetProjectManager: async () => ({ GetCurrentProject: async () => ({
    GetName: async () => 'p', GetUniqueId: async () => 'p1', GetCurrentTimeline: async () => ({ GetName: async () => 't', GetUniqueId: async () => 't1', GetSetting: async () => '25' }),
    GetMediaPool: async () => ({ GetSelectedClips: async () => [item] })
  }) }) }) };
  const [source] = await getSelectedTranscriptions(sdk);
  assert.deepEqual(source.segments[0].words.map(({ start_frame, end_frame, text }) => ({ start_frame, end_frame, text })), [
    { start_frame: 10, end_frame: 15, text: 'grazie' },
    { start_frame: 16, end_frame: 19, text: 'mi' },
    { start_frame: 19, end_frame: 26, text: 'avete' },
    { start_frame: 26, end_frame: 35, text: 'salvata.' }
  ]);
});

function timelineSdk({ appendResultCount = 3, sourceBase = 0 } = {}) {
 const media={GetMediaId:async()=> 'm1',GetName:async()=> 'master.mp4',GetAudioMapping:async()=>JSON.stringify({embedded_audio_channels:2,track_mapping:{'1':{type:'Stereo',channel_idx:[1,2],mute:false}}}),SetAudioMapping:async()=>{reviewTimeline.sourceMutations++;throw Error('Source mutation forbidden');},SetClipColor:async()=>{reviewTimeline.sourceMutations++;throw Error('Source mutation forbidden');}};
 const sourceTimeline={GetUniqueId:async()=> 'source-timeline',GetName:async()=> 'SOURCE',GetSetting:async()=> '25'};
 const makeFolder=name=>{const f={name,children:[],clips:[],GetName:async()=>name,GetSubFolderList:async()=>f.children,GetClipList:async()=>f.clips};return f;};
 const rootFolder=makeFolder('Master'),sourceFolder=makeFolder('Rushes');rootFolder.children.push(sourceFolder);let currentFolder=sourceFolder;
 const timelineMedia={GetMediaId:async()=> 'review-media'};
 const tracks={video:[{}],audio:[{type:'stereo'}]};
 const reviewTimeline={items:[],audio:[],links:[],sourceMutations:0,deleted:false,
 GetMediaPoolItem:async()=>timelineMedia,GetUniqueId:async()=> 'review-timeline',GetName:async()=> 'REVIEW',GetSetting:async()=> '25',GetStartFrame:async()=>90000,
 GetTrackCount:async type=>tracks[type].length,GetTrackSubType:async(type,index)=>tracks[type][index-1]?.type || '',
 AddTrack:async(type,subtype)=>{tracks[type].push({type:subtype});return true;},DeleteTrack:async(type,index)=>{tracks[type].splice(index-1,1);return true;},
 SetTrackName:async(type,index,name)=>{tracks[type][index-1].name=name;return true;},GetTrackName:async(type,index)=>tracks[type][index-1].name,
 GetItemListInTrack:async(type,index)=>(type==='video'?reviewTimeline.items:reviewTimeline.audio).filter(item=>(item.clip.trackIndex || 1)===index),
 SetClipsLinked:async(items,linked)=>{reviewTimeline.links.push(items);for(const item of items)item.linked=items.filter(i=>i!==item);return linked;}
 };
 const project={active:sourceTimeline,GetUniqueId:async()=> 'project',GetCurrentTimeline:async()=>project.active,GetMediaPool:async()=>pool,SetCurrentTimeline:async timeline=>{project.active=timeline;return true;}};
 const pool={GetRootFolder:async()=>rootFolder,GetCurrentFolder:async()=>currentFolder,SetCurrentFolder:async f=>{currentFolder=f;return true;},AddSubFolder:async(parent,name)=>{const f=makeFolder(name);parent.children.push(f);return f;},GetSelectedClips:async()=>[media],CreateEmptyTimeline:async name=>{reviewTimeline.requestedName=name;currentFolder.clips.push(timelineMedia);return reviewTimeline;},
 AppendToTimeline:async clips=>{
 const output=[];
 for(const clip of clips){const type=clip.mediaType===2?'audio':'video',list=type==='video'?reviewTimeline.items:reviewTimeline.audio;if(list.length>=appendResultCount)continue;
 const record=clip.recordFrame ?? (list.length?await list[list.length-1].GetEnd():90000);
 const item={clip,color:'',GetMediaPoolItem:async()=>clip.mediaPoolItem,GetSourceStartFrame:async()=>clip.startFrame%2?clip.startFrame-1:clip.startFrame,GetSourceEndFrame:async()=>clip.endFrame,GetSourceStartTime:async()=>sourceBase+clip.startFrame/25,GetSourceEndTime:async()=>sourceBase+clip.endFrame/25,GetStart:async()=>record,GetEnd:async()=>record+clip.endFrame-clip.startFrame,GetDuration:async()=>clip.endFrame-clip.startFrame,GetTrackTypeAndIndex:async()=>[type,clip.trackIndex || 1],SetClipColor:async color=>{item.color=color;return true;},GetClipColor:async()=>item.color,GetLinkedItems:async()=>item.linked || []};list.push(item);output.push(item);
 }return output;
 },DeleteTimelines:async timelines=>{assert.deepEqual(timelines,[reviewTimeline]);reviewTimeline.deleted=true;return true;}};
 const sdk={GetResolvePromise:async()=>({GetProjectManager:async()=>({GetCurrentProject:async()=>project})})};
 return {sdk,project,pool,sourceTimeline,reviewTimeline,media,rootFolder,sourceFolder};
}

test('appends every repeated source edit and restores the original timeline', async () => {
  const { sdk, project, reviewTimeline, sourceTimeline } = timelineSdk();
  const edits = [179, 250, 400].map(start_frame => ({ media_id: 'm1', start_frame, end_frame: start_frame + 50 }));
  const created = await createTimeline(sdk, 'PREMONTATO TEST', edits, { projectId: 'project', timelineId: 'source-timeline', media: [{ media_id: 'm1' }] });
  assert.equal(created.included, 3);
  assert.deepEqual(await Promise.all(reviewTimeline.items.map(item => item.GetSourceStartTime())), [179 / 25, 250 / 25, 400 / 25]);
  assert.equal(project.active, sourceTimeline);
});

test('rejects and removes a review timeline when Resolve appends only part of the edit list', async () => {
  const context = timelineSdk({ appendResultCount: 1 });
  const edits = [100, 250, 400].map(start_frame => ({ media_id: 'm1', start_frame, end_frame: start_frame + 50 }));
  await assert.rejects(createTimeline(context.sdk, 'PREMONTATO TEST', edits, {
    projectId: 'project', timelineId: 'source-timeline', media: [{ media_id: 'm1' }]
  }), /inserito 1 di 3/);
  assert.equal(context.project.active, context.sourceTimeline);
});

test('verifies absolute camera source timecodes against the media base', async () => {
 const context = timelineSdk({sourceBase:7200});
 const result = await createTimeline(context.sdk,'CAMERA TC',[{media_id:'m1',start_frame:100,end_frame:150}],{media:[{media_id:'m1',fps:25,start_tc:'02:00:00:00'}]});
 assert.equal(result.included,1);
});

test('applies silence source ranges as separate synchronized timeline inserts',async()=>{
 const context=timelineSdk();
 const result=await createTimeline(context.sdk,'PACED',[{media_id:'m1',start_frame:100,end_frame:300,source_ranges:[{start_frame:100,end_frame:150},{start_frame:250,end_frame:300}]},{media_id:'m1',start_frame:400,end_frame:450}],{media:[{media_id:'m1',fps:25}]});
 assert.equal(context.reviewTimeline.items.length,3);
 assert.deepEqual(await Promise.all(context.reviewTimeline.items.map(i=>i.GetSourceStartTime())),[4,10,16]);
 assert.equal(result.included,2);
 assert.equal(result.segments,3);
});
test('rejects paced ranges outside the reviewed source interval before creation',async()=>{
 const context=timelineSdk();
 await assert.rejects(createTimeline(context.sdk,'BAD',[{media_id:'m1',start_frame:100,end_frame:300,source_ranges:[{start_frame:80,end_frame:150}]}]),/Intervalli/);
});

test('groups shot sizes on three video/mono audio tracks, colors and links each paced range without source mutations',async()=>{
 const c=timelineSdk({appendResultCount:100});
 const edits=[{media_id:'m1',start_frame:10,end_frame:60,shot_size:'wide'},{media_id:'m1',start_frame:100,end_frame:200,shot_size:'close',source_ranges:[{start_frame:100,end_frame:125},{start_frame:175,end_frame:200}]},{media_id:'m1',start_frame:210,end_frame:240,shot_size:'medium'},{media_id:'m1',start_frame:250,end_frame:270,shot_size:'detail'},{media_id:'m1',start_frame:280,end_frame:300,shot_size:'unknown'}];
 const result=await createTimeline(c.sdk,'LAYOUT',edits,{media:[{media_id:'m1',fps:25,duration_frames:500}]});
 assert.equal(await c.reviewTimeline.GetTrackCount('video'),3);assert.equal(await c.reviewTimeline.GetTrackCount('audio'),3);
 for(let n=1;n<=3;n++)assert.equal(await c.reviewTimeline.GetTrackSubType('audio',n),'mono');
 assert.deepEqual(c.reviewTimeline.items.map(i=>[i.clip.trackIndex,i.clip.recordFrame,i.color]),[[1,90000,'Blue'],[3,90050,'Orange'],[3,90075,'Orange'],[2,90100,'Green'],[3,90130,'Orange'],[1,90150,'Tan']]);
 assert.deepEqual(c.reviewTimeline.audio.map(i=>[i.clip.trackIndex,i.clip.recordFrame]),[[1,90000],[3,90050],[3,90075],[2,90100],[3,90130],[1,90150]]);
 assert.equal(c.reviewTimeline.links.length,6);assert.equal(c.reviewTimeline.sourceMutations,0);assert.equal(result.audioSegments,6);assert.equal(c.project.active,c.sourceTimeline);
});
test('rejects and removes a layout whose audio format changes to stereo during insertion',async()=>{
 const c=timelineSdk({appendResultCount:100});c.reviewTimeline.GetTrackSubType=async()=> 'stereo';
 await assert.rejects(createTimeline(c.sdk,'BAD MONO',[{media_id:'m1',start_frame:10,end_frame:30,shot_size:'wide'}]),/mono/i);assert.equal(c.reviewTimeline.deleted,true);assert.equal(c.project.active,c.sourceTimeline);
});

test('creates mono replacement tracks before deleting the last default audio track',async()=>{
 const c=timelineSdk();const remove=c.reviewTimeline.DeleteTrack;c.reviewTimeline.DeleteTrack=async(type,index)=>type==='audio' && await c.reviewTimeline.GetTrackCount(type)===1 ? false : remove(type,index);
 const result=await createTimeline(c.sdk,'NATIVE MONO',[{media_id:'m1',start_frame:10,end_frame:30,shot_size:'wide'}]);assert.equal(result.audioFormat,'mono');
});

test('versions generated timelines and places them in dedicated Media Pool folders while restoring the original bin',async()=>{
 const c=timelineSdk();await createTimeline(c.sdk,'REVISIONE',[{media_id:'m1',start_frame:10,end_frame:40,shot_size:'wide'}],{purpose:'test'});
 const version=require('../../plugin/package.json').version;assert.match(c.reviewTimeline.requestedName,new RegExp(version.replaceAll('.','\\.')));const folder=c.rootFolder.children.find(f=>f.name==='Premontato').children.find(f=>f.name==='v'+version).children.find(f=>f.name==='Test');assert.equal(folder.clips.length,1);assert.equal(await c.pool.GetCurrentFolder(),c.sourceFolder);
});

test('normalizes camera-edge timestamps and excludes nonspoken Resolve placeholder segments',async()=>{
 const item={GetMediaId:async()=>'m1',GetName:async()=>'clip',GetMetadata:async()=>'',GetClipProperty:async key=>key==='Start TC'?'01:00:00:01':{FPS:'25',Frames:'100','File Path':'C:/clip.mp4'},GetTranscription:async()=>({segments:[{start:'01:00:00:00',end:'01:00:00:05',text:'(...)'},{start:'01:00:00:00',end:'01:00:00:20',text:'Ciao',words:[{start:'01:00:00:00',end:'01:00:00:20',text:'Ciao'}]}]})};
 const sdk={GetResolvePromise:async()=>({GetProjectManager:async()=>({GetCurrentProject:async()=>({GetCurrentTimeline:async()=>({GetName:async()=>'T',GetUniqueId:async()=>'t',GetSetting:async()=>'25'}),GetName:async()=>'P',GetUniqueId:async()=>'p',GetMediaPool:async()=>({GetSelectedClips:async()=>[item]})})})})};
 const [source]=await getSelectedTranscriptions(sdk);assert.equal(source.segments.length,1);assert.equal(source.segments[0].start_frame,0);assert.equal(source.segments[0].words[0].start_frame,0);
});

 test('empty selection from the native Workflow SDK still returns a connected project snapshot',async()=>{
 const project={GetName:async()=>'P',GetUniqueId:async()=>'p',GetCurrentTimeline:async()=>({GetName:async()=>'T',GetUniqueId:async()=>'t',GetSetting:async()=>'25'}),GetMediaPool:async()=>({GetSelectedClips:async()=>{throw Error('GetSelectedClips: Error response (errorStr:No media item is selected.) (errorCode:2)');}})};
 const sdk={GetResolvePromise:async()=>({GetProjectManager:async()=>({GetCurrentProject:async()=>project})})};
 const result=await require('../../plugin/resolve_adapter').snapshot(sdk);assert.equal(result.project,'P');assert.deepEqual(result.selected,[]);
 project.GetMediaPool=async()=>({GetSelectedClips:async()=>{throw Error('connection lost');}});await assert.rejects(require('../../plugin/resolve_adapter').snapshot(sdk),/connection lost/);
 });
