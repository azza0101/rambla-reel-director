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

function timelineSdk({ appendResultCount = 3, sourceBase = 0, inheritedColor = '' } = {}) {
 const media={GetMediaId:async()=> 'm1',GetName:async()=> 'master.mp4',GetAudioMapping:async()=>JSON.stringify({embedded_audio_channels:2,track_mapping:{'1':{type:'Stereo',channel_idx:[1,2],mute:false}}}),SetAudioMapping:async()=>{reviewTimeline.sourceMutations++;throw Error('Source mutation forbidden');},SetClipColor:async()=>{reviewTimeline.sourceMutations++;throw Error('Source mutation forbidden');}};
 const sourceTimeline={GetUniqueId:async()=> 'source-timeline',GetName:async()=> 'SOURCE',GetSetting:async()=> '25'};
 const makeFolder=name=>{const f={name,children:[],clips:[],GetName:async()=>name,GetSubFolderList:async()=>f.children,GetClipList:async()=>f.clips};return f;};
 const rootFolder=makeFolder('Master'),sourceFolder=makeFolder('Rushes');rootFolder.children.push(sourceFolder);sourceFolder.clips.push(media);let currentFolder=sourceFolder;
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
 const item={clip,color:inheritedColor,GetMediaPoolItem:async()=>clip.mediaPoolItem,GetSourceStartFrame:async()=>clip.startFrame%2?clip.startFrame-1:clip.startFrame,GetSourceEndFrame:async()=>clip.endFrame,GetSourceStartTime:async()=>sourceBase+clip.startFrame/25,GetSourceEndTime:async()=>sourceBase+clip.endFrame/25,GetStart:async()=>record,GetEnd:async()=>record+clip.endFrame-clip.startFrame,GetDuration:async()=>clip.endFrame-clip.startFrame,GetTrackTypeAndIndex:async()=>[type,clip.trackIndex || 1],SetClipColor:async color=>{if(!['Blue','Green','Orange','Purple','Yellow','Teal','Pink','Lime','Apricot','Olive','Navy','Violet','Tan','Beige','Brown','Chocolate'].includes(color))return false;item.color=color;return true;},GetClipColor:async()=>item.color,ClearClipColor:async()=>{item.color='';return true;},GetLinkedItems:async()=>item.linked || []};list.push(item);output.push(item);
 }return output;
 },DeleteTimelines:async timelines=>{assert.deepEqual(timelines,[reviewTimeline]);reviewTimeline.deleted=true;return true;}};
 const sdk={GetResolvePromise:async()=>({GetProjectManager:async()=>({GetCurrentProject:async()=>project})})};
 return {sdk,project,pool,sourceTimeline,reviewTimeline,media,rootFolder,sourceFolder};
}

test('appends every repeated source edit and restores the original timeline', async () => {
  const { sdk, project, reviewTimeline, sourceTimeline } = timelineSdk();
  const edits = [179, 250, 400].map(start_frame => ({ media_id: 'm1', start_frame, end_frame: start_frame + 50,shot_size:start_frame===250?'close':'wide' }));
  const created = await createTimeline(sdk, 'PREMONTATO TEST', edits, { projectId: 'project', timelineId: 'source-timeline', media: [{ media_id: 'm1' }] });
  assert.equal(created.included, 3);
  assert.deepEqual(await Promise.all(reviewTimeline.items.map(item => item.GetSourceStartTime())), [179 / 25, 250 / 25, 400 / 25]);
  assert.equal(project.active, sourceTimeline);
});

test('rejects and removes a review timeline when Resolve appends only part of the edit list', async () => {
  const context = timelineSdk({ appendResultCount: 1 });
  const edits = [100, 250, 400].map(start_frame => ({ media_id: 'm1', start_frame, end_frame: start_frame + 50,shot_size:start_frame===250?'close':'wide' }));
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

test('rejects legacy silence source ranges that jump on the same angle',async()=>{
 const context=timelineSdk();
 await assert.rejects(createTimeline(context.sdk,'PACED',[{media_id:'m1',start_frame:100,end_frame:300,source_ranges:[{start_frame:100,end_frame:150},{start_frame:250,end_frame:300}]}],{media:[{media_id:'m1',fps:25}]}),/Jump cut/);
});
test('rejects paced ranges outside the reviewed source interval before creation',async()=>{
 const context=timelineSdk();
 await assert.rejects(createTimeline(context.sdk,'BAD',[{media_id:'m1',start_frame:100,end_frame:300,source_ranges:[{start_frame:80,end_frame:150}]}]),/Intervalli/);
});

test('groups shot sizes on three video/mono audio tracks, colors and links each paced range without source mutations',async()=>{
 const c=timelineSdk({appendResultCount:100});
 const edits=[{media_id:'m1',start_frame:10,end_frame:60,shot_size:'wide'},{media_id:'m1',start_frame:100,end_frame:200,shot_size:'close',source_ranges:[{start_frame:100,end_frame:150},{start_frame:150,end_frame:200}]},{media_id:'m1',start_frame:210,end_frame:240,shot_size:'medium'},{media_id:'m1',start_frame:250,end_frame:270,shot_size:'detail'},{media_id:'m1',start_frame:280,end_frame:300,shot_size:'unknown'}];
 const result=await createTimeline(c.sdk,'LAYOUT',edits,{media:[{media_id:'m1',fps:25,duration_frames:500}]});
 assert.equal(await c.reviewTimeline.GetTrackCount('video'),3);assert.equal(await c.reviewTimeline.GetTrackCount('audio'),3);
 for(let n=1;n<=3;n++)assert.equal(await c.reviewTimeline.GetTrackSubType('audio',n),'mono');
 assert.deepEqual(c.reviewTimeline.items.map(i=>[i.clip.trackIndex,i.clip.recordFrame]),[[2,90000],[2,90050],[2,90150],[2,90180],[2,90200]]);
 assert.equal(new Set(c.reviewTimeline.items.map(i=>i.color)).size,5);
 assert.deepEqual(c.reviewTimeline.audio.map(i=>i.color),c.reviewTimeline.items.map(i=>i.color));
 assert.deepEqual(c.reviewTimeline.audio.map(i=>[i.clip.trackIndex,i.clip.recordFrame]),[[2,90000],[2,90050],[2,90150],[2,90180],[2,90200]]);
 assert.equal(c.reviewTimeline.links.length,5);assert.equal(c.reviewTimeline.sourceMutations,0);assert.equal(result.audioSegments,5);assert.equal(c.project.active,c.sourceTimeline);
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

test('inserts a reviewed reaction before the dialogue on synchronized mono audio and close video tracks',async()=>{
 const {sdk,reviewTimeline,project,sourceTimeline}=timelineSdk({appendResultCount:2});const reaction={kind:'reaction',media_id:'m1',take_id:'t',start_frame:150,end_frame:190,shot_size:'close',character:'LUCA',enabled:true,basis:'verified_silent_preroll',speaker_coverage:'visible'};
 const result=await createTimeline(sdk,'REACTION',[{media_id:'m1',start_frame:200,end_frame:240,shot_size:'wide',reaction_before:reaction}],{media:[{media_id:'m1',duration_frames:500}]});
 assert.equal(result.included,1);assert.equal(result.segments,2);assert.equal(result.audioSegments,2);assert.deepEqual(reviewTimeline.items.map(x=>[x.clip.startFrame,x.clip.trackIndex]),[[150,3],[200,2]]);assert.equal(project.active,sourceTimeline);
 const broken=timelineSdk();await assert.rejects(createTimeline(broken.sdk,'BAD',[{media_id:'m1',start_frame:200,end_frame:240,reaction_before:{...reaction,end_frame:900}}],{media:[{media_id:'m1',duration_frames:500}]}),/reazione/i);
});

test('connection snapshot remains healthy when selected items cannot be read',async()=>{
 const project={GetName:async()=>'P',GetUniqueId:async()=>'p',GetCurrentTimeline:async()=>({GetName:async()=>'T',GetUniqueId:async()=>'t',GetSetting:async()=>'25'}),GetMediaPool:async()=>({GetSelectedClips:async()=>{throw Error('invalid selection');}})};
 const sdk={GetResolvePromise:async()=>({GetProjectManager:async()=>({GetCurrentProject:async()=>project})})};
 const status=await require('../../plugin/resolve_adapter').snapshot(sdk,{includeSelection:false});assert.equal(status.project,'P');assert.deepEqual(status.selected,[]);await assert.rejects(require('../../plugin/resolve_adapter').snapshot(sdk),/invalid selection/);
});

test('creates from analyzed Media Pool IDs after selection and current bin change',async()=>{const c=timelineSdk();c.sourceFolder.clips.push(c.media);c.pool.GetSelectedClips=async()=>{throw Error('Selection must not be consulted');};await c.pool.SetCurrentFolder(c.rootFolder);const result=await createTimeline(c.sdk,'SAVED SOURCES',[{media_id:'m1',start_frame:10,end_frame:40}],{media:[{media_id:'m1'}]});assert.equal(result.included,1);assert.equal(await c.pool.GetCurrentFolder(),c.rootFolder);assert.equal(c.project.active,c.sourceTimeline);});
test('missing analyzed sources fail before timeline or folders are created',async()=>{const c=timelineSdk();c.sourceFolder.clips=[];c.pool.GetSelectedClips=async()=>[c.media];await assert.rejects(createTimeline(c.sdk,'MISSING',[{media_id:'m1',start_frame:10,end_frame:40}],{media:[{media_id:'m1'}]}),/non.*trovat|mancant/i);assert.equal(c.reviewTimeline.requestedName,undefined);assert.equal(c.rootFolder.children.length,1);});
test('relinked analyzed media fail before creating a timeline',async()=>{const c=timelineSdk();c.sourceFolder.clips.push(c.media);c.media.GetClipProperty=async()=>({'File Path':'E:/replacement.mp4',Frames:'100',FPS:'25'});await assert.rejects(createTimeline(c.sdk,'RELINKED',[{media_id:'m1',start_frame:10,end_frame:40}],{media:[{media_id:'m1',path:'E:/original.mp4',fps:25,duration_frames:100}]}),/sorgente.*cambiat|media.*cambiat/i);assert.equal(c.reviewTimeline.requestedName,undefined);});

test('user creation activates the new timeline when explicitly requested',async()=>{const c=timelineSdk();await createTimeline(c.sdk,'OPEN GENERATED',[{media_id:'m1',start_frame:10,end_frame:40}],{media:[{media_id:'m1'}],activateCreated:true});assert.equal(c.project.active,c.reviewTimeline);assert.equal(c.reviewTimeline.sourceMutations,0);});

test('listening cutaway uses its video and preserves preceding dialogue audio',async()=>{
 const c=timelineSdk({appendResultCount:10});const other={...c.media,GetMediaId:async()=>'m2'};c.sourceFolder.clips.push(other);
 const overlay={kind:'reaction',basis:'verified_listener',media_id:'m2',take_id:'t2',start_frame:200,end_frame:240,offset_frames:60,shot_size:'close',speaker_coverage:'visible',enabled:true,character:'BOY',evidence:{verified:true}};
 await createTimeline(c.sdk,'LISTEN',[{media_id:'m1',start_frame:0,end_frame:100,shot_size:'close',reaction_overlay:overlay}],{media:[{media_id:'m1',duration_frames:500},{media_id:'m2',duration_frames:500}]});
 assert.deepEqual(c.reviewTimeline.items.map(i=>[i.clip.mediaPoolItem===other?'m2':'m1',i.clip.startFrame,i.clip.endFrame]),[['m1',0,100],['m2',200,240]]);
 assert.deepEqual(c.reviewTimeline.audio.map(i=>[i.clip.mediaPoolItem===other?'m2':'m1',i.clip.startFrame,i.clip.endFrame]),[['m1',0,100]]);
 assert.deepEqual(c.reviewTimeline.items.map(i=>[i.clip.trackIndex,i.clip.recordFrame]),[[2,90000],[3,90060]]);assert.equal(c.reviewTimeline.audio[0].clip.trackIndex,2);
});
test('contiguous source angles become one physical clip without an edit point',async()=>{
 const c=timelineSdk({appendResultCount:10});await createTimeline(c.sdk,'CONTINUOUS',[{media_id:'m1',start_frame:0,end_frame:50,shot_size:'wide'},{media_id:'m1',start_frame:50,end_frame:100,shot_size:'wide'}]);assert.equal(c.reviewTimeline.items.length,1);assert.equal(c.reviewTimeline.audio.length,1);assert.equal(c.reviewTimeline.items[0].clip.endFrame,100);
});
test('discontinuous same-angle ranges fail before creating a timeline',async()=>{
 const c=timelineSdk();await assert.rejects(createTimeline(c.sdk,'JUMP',[{media_id:'m1',start_frame:0,end_frame:100,shot_size:'wide',source_ranges:[{start_frame:0,end_frame:40},{start_frame:60,end_frame:100}]}]),/jump|continuit/i);assert.equal(c.reviewTimeline.requestedName,undefined);
});
test('script action coverage is appended with original synchronized audio',async()=>{
 const c=timelineSdk({appendResultCount:10});await createTimeline(c.sdk,'ACTION',[{media_id:'m1',start_frame:0,end_frame:50,shot_size:'wide',action_after:[{kind:'action',beat_id:'exit',take_id:'t',media_id:'m1',start_frame:50,end_frame:150,shot_size:'wide',basis:'script_between_anchors'}]}],{media:[{media_id:'m1',duration_frames:500}]});assert.equal(c.reviewTimeline.items.length,1);assert.equal(c.reviewTimeline.items[0].clip.endFrame,150);assert.equal(c.reviewTimeline.audio[0].clip.endFrame,150);
});

test('invalid listening overlay duration is rejected before timeline creation',async()=>{
 const c=timelineSdk();const overlay={kind:'reaction',basis:'verified_listener',media_id:'m1',take_id:'t',start_frame:200,end_frame:230,offset_frames:80,shot_size:'close',speaker_coverage:'visible',enabled:true,evidence:{verified:true}};
 await assert.rejects(createTimeline(c.sdk,'BAD OVERLAY',[{media_id:'m1',start_frame:0,end_frame:100,reaction_overlay:overlay}],{media:[{media_id:'m1',duration_frames:500}]}),/ascolto non valida/);assert.equal(c.reviewTimeline.requestedName,undefined);
});

test('field colors separate source angles, while remaining stable across speakers and alternative takes',()=>{
 const {assignFieldColors}=require('../../plugin/resolve_adapter');
 const edits=[
 {media_id:'angle-a',shot_size:'close',dialogue_character:'ALICE',take_id:'take-1'},
 {media_id:'angle-a',shot_size:'close',dialogue_character:'ALICE',take_id:'take-2'},
 {media_id:'angle-b',shot_size:'close',dialogue_character:'BOB'},
 {media_id:'angle-a',shot_size:'medium',dialogue_character:'ALICE'},
 {media_id:'angle-a',shot_size:'close',dialogue_character:'BOB'}];
 const colors=assignFieldColors(edits);
 assert.equal(colors[0],colors[1]);assert.equal(colors[0],colors[4]);assert.equal(new Set([colors[0],...colors.slice(2)]).size,3);
 const reversed=assignFieldColors([...edits].reverse()).reverse();assert.deepEqual(reversed,colors);
});
test('changing the speaking or visible person does not recolor an unchanged source field',()=>{
 const {assignFieldColors}=require('../../plugin/resolve_adapter');
 const colors=assignFieldColors([
 {media_id:'two-shot',shot_size:'close',visible_subjects:['BOB','ALICE'],dialogue_character:'ALICE'},
 {media_id:'two-shot',shot_size:'close',visible_subjects:['ALICE','BOB'],dialogue_character:'BOB'},
 {media_id:'two-shot',shot_size:'close',visible_subjects:['ALICE'],dialogue_character:'ALICE'}]);
 assert.equal(colors[0],colors[1]);assert.equal(colors[0],colors[2]);
});
test('color palette exhaustion leaves excess fields neutral without reusing assigned colors',()=>{
 const {assignFieldColors}=require('../../plugin/resolve_adapter');
 const edits=Array.from({length:20},(_,i)=>({media_id:'angle-'+i,shot_size:'wide'})); const colors=assignFieldColors(edits); assert.equal(colors.length,20);assert.equal(new Set(colors.filter(Boolean)).size,16);assert.equal(colors.filter(c=>!c).length,4);assert.deepEqual(assignFieldColors([...edits].reverse()).reverse(),colors);
});

test('wide field color remains stable when people enter or leave',()=>{ const {assignFieldColors}=require('../../plugin/resolve_adapter'); const colors=assignFieldColors([{media_id:'wide',shot_size:'wide',visible_subjects:['ALICE']},{media_id:'wide',shot_size:'wide',visible_subjects:['BOB']}]);assert.equal(colors[0],colors[1]); });

test('analysis retrieves loaded media by identity and reuses cached transcripts without current selection',async()=>{
 let transcribes=0,cached=false;const media={media_id:'loaded',name:'rush',fps:25,start_tc:'00:00:00:00',duration_frames:100};
 const item={GetMediaId:async()=>media.media_id,GetTranscription:async()=>cached?{segments:[{start:'00:00:00:00',end:'00:00:01:00',text:'ciao'}]}:{},TranscribeAudio:async()=>{transcribes++;cached=true;return true;}};
 const pool={GetRootFolder:async()=>({GetClipList:async()=>[item],GetSubFolderList:async()=>[]}),GetSelectedClips:async()=>{throw Error('must not read selection');}};
 const sdk={GetResolvePromise:async()=>({GetProjectManager:async()=>({GetCurrentProject:async()=>({GetCurrentTimeline:async()=>({}),GetMediaPool:async()=>pool})})})};
 const events=[];let sources=await getSelectedTranscriptions(sdk,{media:[media],transcribeMissing:true,onProgress:e=>events.push(e)});
 assert.equal(sources[0].segments[0].end_frame,25);assert.equal(transcribes,1);assert.equal(events.at(-1).current,1);
 await getSelectedTranscriptions(sdk,{media:[media],transcribeMissing:true});assert.equal(transcribes,1);
});

test('scripted close hold requires verified listening and measured silence',()=>{
 const {validateAction}=require('../../plugin/ipc_security');const hold={kind:'action',basis:'script_measured_hold',beat_id:'pause',media_id:'m',take_id:'m',start_frame:50,end_frame:70,shot_size:'close',evidence:{verified:true,silence_measured:true}};assert.equal(validateAction(hold,{media_id:'m',duration_frames:100}),hold);assert.throws(()=>validateAction({...hold,evidence:{verified:true}},{media_id:'m',duration_frames:100}),/non valido/);
});

test('refuses a listening overlay shorter than 1.5 seconds before creating a timeline',async()=>{const c=timelineSdk();const other={...c.media,GetMediaId:async()=>'m2'};c.sourceFolder.clips.push(other);const o={kind:'reaction',basis:'verified_listener',media_id:'m2',take_id:'t',start_frame:200,end_frame:230,offset_frames:70,shot_size:'close',speaker_coverage:'visible',enabled:true,evidence:{verified:true}};await assert.rejects(createTimeline(c.sdk,'SHORT',[{media_id:'m1',start_frame:0,end_frame:100,reaction_overlay:o}],{media:[{media_id:'m1',duration_frames:500,fps:25},{media_id:'m2',duration_frames:500,fps:25}]}),/1[,.]5|breve/);assert.equal(c.reviewTimeline.requestedName,undefined);});

test('saved standalone reactions also respect the hard 1.5-second floor',async()=>{const c=timelineSdk();const reaction={kind:'reaction',media_id:'m1',take_id:'t',start_frame:150,end_frame:180,shot_size:'close',character:'L',enabled:true,basis:'verified_silent_preroll',speaker_coverage:'visible'};await assert.rejects(createTimeline(c.sdk,'SHORT OLD',[{media_id:'m1',start_frame:200,end_frame:250,reaction_before:reaction}],{media:[{media_id:'m1',duration_frames:500}]}),/1[,.]5|breve/);assert.equal(c.reviewTimeline.requestedName,undefined);});

test('an internal V3 reaction returns to intact V2 picture before dialogue ends',async()=>{const c=timelineSdk({appendResultCount:10});const other={...c.media,GetMediaId:async()=>'m2'};c.sourceFolder.clips.push(other);const o={kind:'reaction',basis:'verified_listener',media_id:'m2',take_id:'t',start_frame:200,end_frame:240,offset_frames:35,shot_size:'close',speaker_coverage:'visible',enabled:true,evidence:{verified:true}};await createTimeline(c.sdk,'RETURN',[{media_id:'m1',start_frame:0,end_frame:120,shot_size:'close',reaction_overlay:o}],{media:[{media_id:'m1',duration_frames:500},{media_id:'m2',duration_frames:500}]});assert.deepEqual(c.reviewTimeline.items.map(i=>[i.clip.trackIndex,i.clip.recordFrame,i.clip.endFrame-i.clip.startFrame]),[[2,90000,120],[3,90035,40]]);assert.equal(c.reviewTimeline.audio.length,1);assert.equal(c.reviewTimeline.audio[0].clip.endFrame,120);});


test('debug scene gaps shift dialogue, mono audio and V3 overlays together; V4 labels span each full scene',async()=>{
 const c=timelineSdk({appendResultCount:20,inheritedColor:'Pink'});let imports=0;const other={...c.media,GetMediaId:async()=>'m2'};c.sourceFolder.clips.push(other);
 c.pool.ImportMedia=async paths=>{imports++;return paths.map(p=>({GetMediaId:async()=>p,GetClipProperty:async()=>p}));};
 const s1={id:'s1',number:1,heading:'CASA'},s2={id:'s2',number:2,heading:'STRADA'};
 const edits=[{media_id:'m1',beat_id:'a',start_frame:0,end_frame:100,shot_size:'wide',scene_debug:s1},{media_id:'m1',beat_id:'b',start_frame:200,end_frame:300,shot_size:'wide',scene_debug:s2,reaction_overlay:{kind:'reaction',basis:'verified_listener',media_id:'m2',take_id:'t',start_frame:350,end_frame:390,offset_frames:20,shot_size:'close',speaker_coverage:'visible',enabled:true,evidence:{verified:true}}}];
 const result=await createTimeline(c.sdk,'DEBUG',edits,{media:[{media_id:'m1',fps:25,duration_frames:500},{media_id:'m2',fps:25,duration_frames:500}],sceneDebug:{enabled:true,gap_frames:50,assets:{1:'C:/debug/scene-01.png',2:'C:/debug/scene-02.png'}}});
 assert.deepEqual(c.reviewTimeline.items.filter(x=>x.clip.trackIndex===2).map(x=>x.clip.recordFrame),[90000,90150]);assert.deepEqual(c.reviewTimeline.audio.map(x=>x.clip.recordFrame),[90000,90150]);
 const overlay=c.reviewTimeline.items.find(x=>x.clip.trackIndex===3);assert.equal(overlay.clip.recordFrame,90170);
 const labels=c.reviewTimeline.items.filter(x=>x.clip.trackIndex===4);assert.deepEqual(labels.map(x=>[x.clip.recordFrame,x.clip.endFrame-x.clip.startFrame]),[[90000,100],[90150,100]]);assert.equal(await c.reviewTimeline.GetTrackName('video',4),'DEBUG scene');assert.equal(result.sceneGaps,1);assert.equal(result.sceneLabels,2);assert.equal(result.videoTracks,4);assert.equal(imports,1);
});

test('scene debug keeps identical framing on either side of a scene boundary separate',async()=>{
 const c=timelineSdk({appendResultCount:20,inheritedColor:'Pink'});c.pool.ImportMedia=async paths=>paths.map(p=>({GetMediaId:async()=>p,GetClipProperty:async()=>p}));
 const edits=[{media_id:'m1',start_frame:0,end_frame:50,shot_size:'wide',scene_debug:{id:'a',number:1}},{media_id:'m1',start_frame:50,end_frame:100,shot_size:'wide',scene_debug:{id:'b',number:2}}];
 await createTimeline(c.sdk,'DEBUG',edits,{sceneDebug:{enabled:true,gap_frames:50,assets:{1:'C:/one.png',2:'C:/two.png'}}});assert.equal(c.reviewTimeline.items.filter(x=>x.clip.trackIndex===2).length,2);
});

test('unverified debug title insertion removes only the generated timeline and restores source',async()=>{
 const c=timelineSdk();c.pool.ImportMedia=async()=>[];
 await assert.rejects(createTimeline(c.sdk,'DEBUG',[{media_id:'m1',start_frame:0,end_frame:50,scene_debug:{id:'s',number:1}}],{sceneDebug:{enabled:true,gap_frames:50,assets:{1:'C:/one.png'}}}),/etichett|titol/i);assert.equal(c.reviewTimeline.deleted,true);assert.equal(c.project.active,c.sourceTimeline);
});

test('cataloged coverage can read an empty transcription without starting another GPU job',async()=>{
 let transcribes=0;const media={media_id:'known-cover',name:'cover',fps:25,start_tc:'00:00:00:00',duration_frames:100};const item={GetMediaId:async()=>media.media_id,GetTranscription:async()=>({}),TranscribeAudio:async()=>{transcribes++;return true;}};const pool={GetRootFolder:async()=>({GetClipList:async()=>[item],GetSubFolderList:async()=>[]})};const sdk={GetResolvePromise:async()=>({GetProjectManager:async()=>({GetCurrentProject:async()=>({GetCurrentTimeline:async()=>({}),GetMediaPool:async()=>pool})})})};const rows=await getSelectedTranscriptions(sdk,{media:[media],transcribeMissing:true,skipTranscribeIds:[media.media_id]});assert.equal(rows[0].segments.length,0);assert.equal(transcribes,0);
});

test('timeline creation succeeds with 17 fields and reports neutral overflow without source changes',async()=>{
 const c=timelineSdk({appendResultCount:20,inheritedColor:'Pink'});
 const edits=Array.from({length:17},(_,i)=>({media_id:'m1',framing_group_id:'field-'+i,shot_size:'wide',start_frame:i*20,end_frame:i*20+20}));
 const r=await createTimeline(c.sdk,'COLOR OVERFLOW',edits,{media:[{media_id:'m1',fps:25}],activateCreated:true});
 assert.equal(r.included,17);assert.equal(r.neutralFields,1);assert.equal(c.reviewTimeline.items.filter(i=>!i.color).length,1);assert.equal(c.reviewTimeline.audio.filter(i=>!i.color).length,1);assert.equal(r.warnings.length,1);assert.equal(c.reviewTimeline.items.length,17);assert.equal(c.reviewTimeline.sourceMutations,0);assert.equal(c.reviewTimeline.deleted,false);assert.equal(c.project.active,c.reviewTimeline);
});