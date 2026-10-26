'use strict';
const { contextBridge, ipcRenderer } = require('electron/renderer');
const methods = ['catalogPreviewFrames','catalogInventory','catalogAnalyze','catalogResume','catalogPreviewPublish','catalogApplyPublish','catalogEditMembership','cancelCatalog','configureGroq', 'resolveSnapshot', 'selectScript', 'selectMedia', 'transcribeSelected', 'analyzeIntellisearch', 'analyze', 'cancelAnalysis', 'getReviewState', 'saveDraft', 'saveProject', 'openProject', 'confirmTakes', 'selectScenes', 'setScriptPages', 'updateDecision', 'setPacing', 'setDirections', 'confirmVisualReview', 'loadVisualReview', 'createReviewTimeline', 'update', 'prepareSupportReport', 'submitSupportReport'];
const api = Object.fromEntries(methods.map(name => [name, (...args) => ipcRenderer.invoke(`premontato:${name}`, ...args)]));
// Sandboxed preloads cannot import local JSON. The main process supplies this value.
api.version = process.argv.find(arg => /^--premontato-version=\d+\.\d+\.\d+$/.test(arg))?.split('=')[1] || null;
api.onProgress = callback => {
  if (typeof callback !== 'function') throw new TypeError('callback non valida');
  const listener = (_event, value) => callback(value);
  ipcRenderer.on('premontato:progress', listener);
  return () => ipcRenderer.removeListener('premontato:progress', listener);
};
for(const [name,channel] of [['onCatalogProgress','catalogProgress'],['onUpdateProgress','updateProgress'],['onProjectStatus','projectStatus']])api[name]=callback=>{if(typeof callback!=='function')throw new TypeError('callback non valida');const listener=(_event,value)=>callback(value);ipcRenderer.on('premontato:'+channel,listener);return ()=>ipcRenderer.removeListener('premontato:'+channel,listener);};
contextBridge.exposeInMainWorld('premontato', Object.freeze(api));
