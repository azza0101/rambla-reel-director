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
  const media = { GetMediaId: async () => 'm1', GetName: async () => 'master.mp4' };
  const sourceTimeline = { GetUniqueId: async () => 'source-timeline', GetName: async () => 'SOURCE' };
  const reviewTimeline = {
    items: [], GetUniqueId: async () => 'review-timeline', GetName: async () => 'REVIEW',
    GetItemListInTrack: async (type, index) => type === 'video' && index === 1 ? reviewTimeline.items : []
  };
  const project = {
    active: sourceTimeline,
    GetUniqueId: async () => 'project', GetCurrentTimeline: async () => project.active,
    GetMediaPool: async () => pool,
    SetCurrentTimeline: async timeline => { project.active = timeline; return true; }
  };
  const pool = {
    GetSelectedClips: async () => [media],
    CreateEmptyTimeline: async () => reviewTimeline,
    AppendToTimeline: async clips => {
      reviewTimeline.items = clips.slice(0, appendResultCount).map(clip => ({
        GetMediaPoolItem: async () => clip.mediaPoolItem,
        // Resolve can round GetSourceStartFrame down at some clip-relative positions;
        // the underlying source time remains exact.
        GetSourceStartFrame: async () => clip.startFrame % 2 ? clip.startFrame - 1 : clip.startFrame,
        GetSourceEndFrame: async () => clip.endFrame,
        GetSourceStartTime: async () => sourceBase + clip.startFrame / 25,
        GetSourceEndTime: async () => sourceBase + clip.endFrame / 25,
        GetDuration: async () => clip.endFrame - clip.startFrame
      }));
      return reviewTimeline.items;
    },
    DeleteTimelines: async timelines => { assert.deepEqual(timelines, [reviewTimeline]); return true; }
  };
  const sdk = { GetResolvePromise: async () => ({ GetProjectManager: async () => ({ GetCurrentProject: async () => project }) }) };
  return { sdk, project, pool, sourceTimeline, reviewTimeline };
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
