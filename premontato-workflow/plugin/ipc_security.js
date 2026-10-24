'use strict';

function assertTrusted(event, window, pageUrl) {
  if (!window || event.sender !== window.webContents || event.senderFrame !== window.webContents.mainFrame || event.senderFrame.url !== pageUrl) {
    throw new Error('Pagina non autorizzata');
  }
}

function validateMediaRecords(records) {
  if (!Array.isArray(records) || records.length === 0) throw new Error('Seleziona almeno un media dal Media Pool');
  return records.map(record => {
    if (!record || typeof record.media_id !== 'string' || !record.media_id || !Number.isInteger(record.duration_frames) || record.duration_frames <= 0) {
      throw new Error('Record media Resolve non valido');
    }
    return Object.freeze({ ...record, path: typeof record.path === 'string' ? record.path : '', camera_id: record.camera_id || 'camera_1' });
  });
}

function validateReaction(value, media) {
  const valid=value && typeof value==='object' && !Array.isArray(value) && media && value.media_id===media.media_id && value.kind==='reaction' && value.basis==='verified_silent_preroll' && value.shot_size==='close' && value.speaker_coverage==='visible' && typeof value.take_id==='string' && typeof value.character==='string' && typeof value.enabled==='boolean' && Number.isSafeInteger(value.start_frame) && Number.isSafeInteger(value.end_frame) && value.start_frame>=0 && value.end_frame>value.start_frame && value.end_frame<=media.duration_frames && value.source_ranges===undefined && value.reaction_before===undefined;
  if(!valid)throw new Error('Reazione non valida: intervallo o copertura non verificati');
  if(value.still!==undefined && (!value.still || !Number.isSafeInteger(value.still.frame) || value.still.frame<value.start_frame || value.still.frame>=value.end_frame || typeof value.still.image!=='string' || value.still.image.length>500000 || !/^data:image\/jpeg;base64,[A-Za-z0-9+/=]+$/.test(value.still.image)))throw new Error('Still di reazione non valida');
  return value;
}
module.exports = { assertTrusted, validateMediaRecords, validateReaction };
