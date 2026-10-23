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

module.exports = { assertTrusted, validateMediaRecords };
