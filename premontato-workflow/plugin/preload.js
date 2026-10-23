'use strict';
const { contextBridge, ipcRenderer } = require('electron/renderer');
const methods = ['resolveSnapshot', 'selectScript', 'selectMedia', 'transcribeSelected', 'analyzeIntellisearch', 'analyze', 'cancelAnalysis', 'getReviewState', 'confirmTakes', 'createReviewTimeline'];
const api = Object.fromEntries(methods.map(name => [name, (...args) => ipcRenderer.invoke(`premontato:${name}`, ...args)]));
api.onProgress = callback => {
  if (typeof callback !== 'function') throw new TypeError('callback non valida');
  const listener = (_event, value) => callback(value);
  ipcRenderer.on('premontato:progress', listener);
  return () => ipcRenderer.removeListener('premontato:progress', listener);
};
contextBridge.exposeInMainWorld('premontato', Object.freeze(api));
