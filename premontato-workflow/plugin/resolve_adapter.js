'use strict';

async function getResolve(sdk) {
  const resolve = await sdk.GetResolvePromise();
  if (!resolve) throw new Error('DaVinci Resolve non disponibile');
  const pm = await resolve.GetProjectManager();
  const project = pm && await pm.GetCurrentProject();
  if (!project) throw new Error('Apri un progetto in Resolve');
  const timeline = await project.GetCurrentTimeline();
  if (!timeline) throw new Error('Apri una timeline di riferimento');
  return { resolve, pm, project, timeline, pool: await project.GetMediaPool() };
}

async function snapshot(sdk) {
  const { project, timeline, pool } = await getResolve(sdk);
  const clips = await pool.GetSelectedClips() || [];
  return { project: String(await project.GetName()), projectId: String(await project.GetUniqueId()),
    timeline: String(await timeline.GetName()), timelineId: String(await timeline.GetUniqueId()),
    fps: Number(await timeline.GetSetting('timelineFrameRate')),
    selected: await Promise.all(clips.map(async item => {
      const props = await item.GetClipProperty() || {};
      const fpsValue = props.FPS || props['Frame Rate'] || await timeline.GetSetting('timelineFrameRate') || 25;
      const fps = Number(String(fpsValue).match(/[0-9]+(?:\.[0-9]+)?/)?.[0] || 25);
      const durationValue = props.Duration || '';
      const startTc = String(await item.GetClipProperty('Start TC') || props['Start TC'] || '');
      const framesValue = Number(props.Frames);
      let durationFrames = Number.isFinite(framesValue) && framesValue > 0 ? framesValue : NaN;
      if (!Number.isFinite(durationFrames) && /^\d{2}:\d{2}:\d{2}[:;]\d{2}$/.test(String(durationValue))) durationFrames = timecodeToFrames(durationValue, fps);
      if (!Number.isFinite(durationFrames)) { const seconds = Number(durationValue); if (Number.isFinite(seconds) && seconds > 0) durationFrames = Math.round(seconds * fps); }
      const mediaPath = String(props['File Path'] || props['File Name'] || '');
      return { media_id: String(await item.GetMediaId()), name: String(await item.GetName()), duration_frames: Math.max(0, Math.round(Number.isFinite(durationFrames) ? durationFrames : 0)), fps, start_tc: startTc, path: mediaPath,
        people: parsePeopleMetadata(await item.GetMetadata('People')), item };
    })) };
}

async function getTranscript(sdk, mediaId) {
  const { pool } = await getResolve(sdk);
  const item = (await pool.GetSelectedClips() || []).find(clip => String(clip.GetMediaId()) === mediaId);
  if (!item) throw new Error('Seleziona il media nel Media Pool prima di leggere la trascrizione');
  const transcription = await item.GetTranscription();
  if (!transcription || !Array.isArray(transcription.segments)) return { status: 'missing', segments: [] };
  return { status: 'ok', language: transcription.language || null, segments: transcription.segments };
}

async function transcribeSelected(sdk) {
  const { pool } = await getResolve(sdk), clips = await pool.GetSelectedClips() || [];
  if (!clips.length) throw new Error('Seleziona i media nel Media Pool');
  return Promise.all(clips.map(async item => {
    const existing = await item.GetTranscription();
    if (Array.isArray(existing?.segments) && existing.segments.length) return { media_id: String(await item.GetMediaId()), ok: true, reused: true };
    return { media_id: String(await item.GetMediaId()), ok: Boolean(await item.TranscribeAudio(true)), reused: false };
  }));
}

// IntelliSearch is opt-in; face clusters are read separately through GetMetadata('People').
async function analyzeIntellisearchSelected(sdk, options = {}) {
  const { pool } = await getResolve(sdk), clips = await pool.GetSelectedClips() || [];
  if (!clips.length) throw new Error('Seleziona i media nel Media Pool');
  const identifyFaces = options.identifyFaces !== false;
  const isBetterMode = options.isBetterMode === true;
  return Promise.all(clips.map(async item => ({
    media_id: String(await item.GetMediaId()),
    ok: Boolean(await item.AnalyzeForIntellisearch(identifyFaces, isBetterMode))
  })));
}

function timecodeToFrames(timecode, fps) {
  const match = String(timecode).match(/^(\d{2}):(\d{2}):(\d{2})[:;](\d{2})$/);
  if (!match || !Number.isFinite(fps) || fps <= 0) throw new Error(`Timecode Resolve non valido: ${timecode}`);
  const [, hh, mm, ss, ff] = match, nominal = Math.round(fps);
  let frames = ((Number(hh) * 3600 + Number(mm) * 60 + Number(ss)) * nominal) + Number(ff);
  if (timecode.includes(';') && nominal >= 30) { const drop = nominal >= 60 ? 4 : 2; const totalMinutes = Number(hh) * 60 + Number(mm); frames -= drop * (totalMinutes - Math.floor(totalMinutes / 10)); }
  return Math.max(0, frames);
}

function parsePeopleMetadata(value) {
  const raw = Array.isArray(value) ? value : String(value || '').split(/[;,]/);
  return [...new Set(raw.map(item => String(item).trim()).filter(Boolean))];
}

async function getSelectedTranscriptions(sdk) {
  const snapshotData = await snapshot(sdk);
  return Promise.all(snapshotData.selected.map(async source => {
    const transcription = await source.item.GetTranscription();
    const segments = Array.isArray(transcription?.segments) ? transcription.segments.map((segment, index) => ({
      segment_id: `${source.media_id}:${index}`, media_id: source.media_id,
      start_frame: timecodeToFrames(segment.start, source.fps) - timecodeToFrames(source.start_tc, source.fps),
      end_frame: timecodeToFrames(segment.end, source.fps) - timecodeToFrames(source.start_tc, source.fps),
      text: String(segment.text || ''), speaker_name: segment.speaker || null
    })).filter(segment => segment.end_frame > segment.start_frame && segment.text.trim()) : [];
    return { ...source, item: undefined, take_id: `${source.media_id}:take:1`, take_index: snapshotData.selected.indexOf(source) + 1,
      camera_id: 'camera_1', segments };
  }));
}

async function createTimeline(sdk, name, edits, expected = {}) {
  const { pm, project, pool, timeline: sourceTimeline } = await getResolve(sdk);
  const beforeProject = String(await project.GetUniqueId()), beforeTimeline = String(await sourceTimeline.GetUniqueId());
  if ((expected.projectId && expected.projectId !== beforeProject) || (expected.timelineId && expected.timelineId !== beforeTimeline)) throw new Error('Progetto o timeline cambiati: crea una nuova analisi');
  const items = await pool.GetSelectedClips() || [];
  const selectedIds = await Promise.all(items.map(async item => String(await item.GetMediaId())));
  const expectedIds = expected.mediaIds || expected.media?.map(item => item.media_id);
  if (expectedIds && (expectedIds.length !== selectedIds.length || expectedIds.some((id, index) => id !== selectedIds[index]))) throw new Error('La selezione dei media è cambiata: riseleziona le clip e ricalcola');
  const byId = new Map(await Promise.all(items.map(async item => [String(await item.GetMediaId()), item])));
  if (!edits.length || edits.some(edit => !byId.has(edit.media_id) || edit.end_frame <= edit.start_frame)) throw new Error('Piano incompleto o media non selezionato; timeline non creata');
  const clips = edits.map(edit => ({ mediaPoolItem: byId.get(edit.media_id), startFrame: edit.start_frame,
    endFrame: edit.end_frame - 1 }));
  const newTimeline = await pool.CreateTimelineFromClips(name, clips);
  if (!newTimeline) throw new Error('Resolve non ha creato la nuova timeline');
  if (String(await project.GetUniqueId()) !== beforeProject || String(await sourceTimeline.GetUniqueId()) !== beforeTimeline) throw new Error('Progetto o timeline di partenza cambiati durante la creazione');
  // Do not save the project or switch the user's active timeline.
  return { timelineId: String(await newTimeline.GetUniqueId()), timelineName: String(await newTimeline.GetName()), sourceTimelineId: beforeTimeline };
}

module.exports = { getResolve, snapshot, getTranscript, getSelectedTranscriptions, transcribeSelected, analyzeIntellisearchSelected, parsePeopleMetadata, timecodeToFrames, createTimeline };
