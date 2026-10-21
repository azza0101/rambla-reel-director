'use strict';
const {contextBridge,ipcRenderer}=require('electron/renderer');
const call=name=>async(...args)=>{try{return await ipcRenderer.invoke('srt:'+name,...args)}catch(e){throw new Error(String(e.message||e).replace(/^Error invoking remote method '[^']+': (?:Error: )?/,''))}};
contextBridge.exposeInMainWorld('ramblaSrt',Object.freeze(Object.fromEntries(['refresh','save','add','remove','folder','export','copy','open','version','check','update'].map(name=>[name,call(name)]))));
