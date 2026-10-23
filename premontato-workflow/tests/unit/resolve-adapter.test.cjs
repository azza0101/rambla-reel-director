'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { timecodeToFrames, analyzeIntellisearchSelected, transcribeSelected, parsePeopleMetadata, getSelectedTranscriptions } = require('../../plugin/resolve_adapter');

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
