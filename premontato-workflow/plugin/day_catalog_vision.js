'use strict';
const fs=require('node:fs/promises'),path=require('node:path'),{Session}=require('./session');
class CatalogVision{
 constructor(root,session){this.root=root;this.session=session;this.worker=null;}
 async config(){const configFile=path.join(this.root,'catalog-vision.json');try{const c=JSON.parse(await fs.readFile(configFile,'utf8'));for(const k of ['python','deps','code','model'])if(typeof c[k]!=='string')throw Error('Configurazione visiva non valida');await Promise.all([fs.access(c.python),fs.access(path.join(c.model,'config.json')),fs.access(path.join(c.code,'src','models','qwen3_vl_embedding.py'))]);return c;}catch(e){if(e.code!=='ENOENT')throw e;}
 const candidates=[process.env.OMNICUT_VISION_HOME,path.resolve(__dirname,'../../..','qwen-embedding-smoke'),'Z:/APP REEL TEST/qwen-embedding-smoke'].filter(Boolean);for(const home of candidates){const c={python:path.join(home,'venv','Scripts','python.exe'),deps:path.join(home,'director-deps'),code:path.join(home,'official-code'),model:path.join(home,'models','Qwen3-VL-Embedding-2B')};try{await Promise.all([fs.access(c.python),fs.access(path.join(c.model,'config.json')),fs.access(path.join(c.code,'src','models','qwen3_vl_embedding.py'))]);return c;}catch{}}
 return null;}
 async analyze(source,scenes,report){const config=await this.config();if(!config)return {scene_id:null,basis:'unavailable',reason:'Modello visivo locale non configurato'};
 report({label:'Estraggo frame ridotti ogni 5 secondi'});const sampled=await this.session.request('catalog_frames',{source},180000);report({label:sampled.frames.length+' frame pronti'+(sampled.cache_hit?' · cache':'' )});
 const workerPath=[path.join(__dirname,'worker','visual_catalog_worker.py'),path.join(__dirname,'..','worker','visual_catalog_worker.py')];let script;for(const p of workerPath)try{await fs.access(p);script=p;break;}catch{}if(!script)throw Error('Worker visivo mancante');this.worker ||= new Session(this.root,script,config.python);
 return this.worker.request('catalog_visual',{config,frames:sampled.frames,scenes,cache_root:path.join(this.root,'cache','catalog-visual')},600000,report);
 }
 async close(){await this.worker?.shutdownWorker();this.worker=null;}
}
module.exports={CatalogVision};
