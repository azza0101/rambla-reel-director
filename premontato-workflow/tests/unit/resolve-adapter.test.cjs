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
  assert.deepEqual(await transcribeSelected(sdk), [
    { media_id: 'cached', ok: true, reused: true }, { media_id: 'new', ok: true, reused: false }
  ]);
  assert.equal(detected, true);
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

test('converts camera timecodes to clip-relative frame ranges', async () => {
  const item = {
    GetMediaId: async () => 'm1', GetName: async () => 'clip', GetClipProperty: async key => key === 'Start TC' ? '02:56:57:15' : ({ FPS: '25', Frames: '2500', Duration: '00:01:40:00' }),
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

function timelineSdk({ appendResultCount = 3 } = {}) {
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
        GetSourceStartFrame: async () => clip.startFrame,
        GetSourceEndFrame: async () => clip.endFrame,
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
  const edits = [100, 250, 400].map(start_frame => ({ media_id: 'm1', start_frame, end_frame: start_frame + 50 }));
  const created = await createTimeline(sdk, 'PREMONTATO TEST', edits, { projectId: 'project', timelineId: 'source-timeline', media: [{ media_id: 'm1' }] });
  assert.equal(created.included, 3);
  assert.deepEqual(await Promise.all(reviewTimeline.items.map(item => item.GetSourceStartFrame())), [100, 250, 400]);
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
