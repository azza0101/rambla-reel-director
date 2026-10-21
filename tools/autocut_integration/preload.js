const {contextBridge,ipcRenderer}=require('electron/renderer');
contextBridge.exposeInMainWorld('rmblAutoCut',Object.freeze({snapshot:()=>ipcRenderer.invoke('autocut:snapshot'),update:()=>ipcRenderer.invoke('autocut:update')}));
