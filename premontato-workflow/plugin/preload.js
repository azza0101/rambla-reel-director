'use strict';
const { contextBridge, ipcRenderer } = require('electron/renderer');
const methods = ['resolveSnapshot', 'selectScript', 'selectMedia', 'transcribeSelected', 'analyzeIntellisearch', 'analyze', 'cancelAnalysis', 'getReviewState', 'saveDraft', 'saveProject', 'openProject', 'confirmTakes', 'updateDecision', 'setPacing', 'setDirections', 'confirmVisualReview', 'createReviewTimeline', 'update', 'prepareSupportReport', 'submitSupportReport'];
const api = Object.fromEntries(methods.map(name => [name, (...args) => ipcRenderer.invoke(`premontato:${name}`, ...args)]));
api.version = require('./package.json').version;
api.onProgress = callback => {
  if (typeof callback !== 'function') throw new TypeError('callback non valida');
  const listener = (_event, value) => callback(value);
  ipcRenderer.on('premontato:progress', listener);
  return () => ipcRenderer.removeListener('premontato:progress', listener);
};
for(const [name,channel] of [['onUpdateProgress','updateProgress'],['onProjectStatus','projectStatus']])api[name]=callback=>{if(typeof callback!=='function')throw new TypeError('callback non valida');const listener=(_event,value)=>callback(value);ipcRenderer.on('premontato:'+channel,listener);return ()=>ipcRenderer.removeListener('premontato:'+channel,listener);};
contextBridge.exposeInMainWorld('premontato', Object.freeze(api));
