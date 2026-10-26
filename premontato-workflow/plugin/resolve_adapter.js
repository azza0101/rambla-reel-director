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

async function selectedClips(pool) {
  try { return await pool.GetSelectedClips() || []; }
  catch (error) {
    if (/errorStr:No media item is selected\./.test(String(error.message)) && /errorCode:2/.test(String(error.message))) return [];
    throw error;
  }
}

async function snapshot(sdk,{includeSelection=true}={}) {
  const { project, timeline, pool } = await getResolve(sdk);
  const clips = includeSelection ? await selectedClips(pool) : [];
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
      const type = String(props.Type || props.type || '');
      if (!mediaPath || !Number.isFinite(durationFrames) || durationFrames <= 0 || /timeline/i.test(type)) {
        throw new Error(`La selezione contiene “${await item.GetName()}”, che non è un file video valido. Seleziona i file video nel Media Pool, non una timeline o una cartella.`);
      }
      return { media_id: String(await item.GetMediaId()), name: String(await item.GetName()), duration_frames: Math.max(0, Math.round(durationFrames)), fps, start_tc: startTc, path: mediaPath,
        people: parsePeopleMetadata(await item.GetMetadata('People')), item };
    })) };
}

async function getTranscript(sdk, mediaId) {
  const { pool } = await getResolve(sdk);
  const item = (await selectedClips(pool)).find(clip => String(clip.GetMediaId()) === mediaId);
  if (!item) throw new Error('Seleziona il media nel Media Pool prima di leggere la trascrizione');
  const transcription = await item.GetTranscription(true);
  if (!transcription || !Array.isArray(transcription.segments)) return { status: 'missing', segments: [] };
  return { status: 'ok', language: transcription.language || null, segments: transcription.segments };
}

async function transcribeSelected(sdk, onProgress) {
  const { pool } = await getResolve(sdk), clips = await selectedClips(pool);
  if (!clips.length) throw new Error('Seleziona i media nel Media Pool');
  const results=[];
  for (let i=0;i<clips.length;i++) {
    const item=clips[i], name=String(await item.GetName?.() || ('Clip '+(i+1)));
    onProgress?.({current:i,total:clips.length,name});
    const existing=await item.GetTranscription(true);
    const reused=Array.isArray(existing?.segments) && existing.segments.length>0;
    const result={media_id:String(await item.GetMediaId()),ok:reused || Boolean(await item.TranscribeAudio(true)),reused};
    results.push(result);onProgress?.({current:i+1,total:clips.length,name,reused,ok:result.ok});
  }
  return results;
}

// IntelliSearch is opt-in; face clusters are read separately through GetMetadata('People').
async function analyzeIntellisearchSelected(sdk, options = {}) {
  const { pool } = await getResolve(sdk), clips = await selectedClips(pool);
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
    const transcription = await source.item.GetTranscription(true);
    const clipFrame=value=>Math.max(0,Math.min(source.duration_frames,timecodeToFrames(value,source.fps)-timecodeToFrames(source.start_tc,source.fps)));
    const segments = Array.isArray(transcription?.segments) ? transcription.segments.map((segment, index) => ({
      segment_id: `${source.media_id}:${index}`, media_id: source.media_id,
      start_frame: clipFrame(segment.start),
      end_frame: clipFrame(segment.end),
      text: String(segment.text || ''), speaker_name: segment.speaker || null,
      words: Array.isArray(segment.words) ? segment.words.map(word => ({
        start_frame: clipFrame(word.start),
        end_frame: clipFrame(word.end),
        text: String(word.text || '')
      })).filter(word => word.end_frame > word.start_frame && /[\p{L}\p{N}]/u.test(word.text)) : []
    })).filter(segment => segment.end_frame > segment.start_frame && /[\p{L}\p{N}]/u.test(segment.text)) : [];
    return { ...source, item: undefined, take_id: `${source.media_id}:take:1`, take_index: snapshotData.selected.indexOf(source) + 1,
      camera_id: 'camera_1', segments };
  }));
}

async function analyzedMediaItems(pool,ids,records=[],timeline){
 if(!Array.isArray(ids) || !ids.length || new Set(ids).size!==ids.length)throw new Error('Elenco sorgenti analizzate non valido');
 const needed=new Set(ids),found=new Map(),folders=[await pool.GetRootFolder()],visited=new Set();
 while(folders.length && needed.size){
  const folder=folders.pop();if(!folder || visited.has(folder))continue;visited.add(folder);
  for(const item of await folder.GetClipList() || []){const id=String(await item.GetMediaId());if(needed.has(id)){found.set(id,item);needed.delete(id);}}
  if(needed.size)folders.push(...await folder.GetSubFolderList() || []);
 }
 if(needed.size)throw new Error('Sorgenti analizzate non trovate nel Media Pool: '+needed.size+'. Ripristina le clip originali nel progetto.');
 for(const record of records){
  const item=found.get(record.media_id);if(!item || !record.path)continue;
  const props=await item.GetClipProperty() || {},norm=value=>{const p=require('node:path').normalize(String(value));return process.platform==='win32'?p.toLowerCase():p;};
  let changed=norm(props['File Path'] || props['File Name'] || '')!==norm(record.path) || /timeline/i.test(String(props.Type || ''));
  const fps=Number(String(props.FPS || props['Frame Rate'] || await timeline.GetSetting('timelineFrameRate')).match(/[0-9]+(?:\.[0-9]+)?/)?.[0]);
  let frames=Number(props.Frames);if(!Number.isFinite(frames) || frames<=0){const duration=String(props.Duration || '');frames=/^\d{2}:\d{2}:\d{2}[:;]\d{2}$/.test(duration)?timecodeToFrames(duration,fps):Math.round(Number(duration)*fps);}
  if(record.fps && (!Number.isFinite(fps) || Math.abs(fps-record.fps)>.001))changed=true;
  if(record.duration_frames && frames!==record.duration_frames)changed=true;
  if(record.start_tc && String(await item.GetClipProperty('Start TC') || props['Start TC'] || '')!==record.start_tc)changed=true;
  if(changed)throw new Error('La sorgente analizzata è cambiata in Resolve: '+(record.name || record.media_id)+'. Ripristina il collegamento originale o rianalizza.');
 }
 return ids.map(id=>found.get(id));
}
const FIELD_COLORS=['Blue','Green','Orange','Purple','Yellow','Teal','Pink','Lime','Apricot','Olive','Navy','Violet','Tan','Beige','Brown','Chocolate'];
function fieldColorKey(edit,index=0){
 const size=edit.shot_size || 'unknown',normalize=value=>String(value).normalize('NFKC').trim().toLocaleUpperCase('it');
 const subjects=[...new Set((edit.visible_subjects || []).filter(Boolean).map(normalize))].sort();
 if(!subjects.length && size!=='wide'){const person=edit.character || edit.dialogue_character;if(person)subjects.push(normalize(person));}
 const field=edit.framing_group_id || edit.media_id;
 const identity=size==='wide'?'context':subjects.length?subjects.join('|'):'unverified:'+(edit.decision_id || edit.beat_id || [edit.start_frame,edit.end_frame,index].join(':'));
 return JSON.stringify([size,field,identity]);
}
function assignFieldColors(edits){
 const keys=edits.map((e,i)=>e.field_color_key || fieldColorKey(e,i));
 const ordered=[...new Set(keys)].sort((a,b)=>(JSON.parse(a)[0]==='wide'?0:1)-(JSON.parse(b)[0]==='wide'?0:1) || a.localeCompare(b));
 if(ordered.length>FIELD_COLORS.length)throw Error('Troppi campi distinti per i '+FIELD_COLORS.length+' colori disponibili in Resolve: i colori non vengono riutilizzati su campi diversi');
 const colors=new Map(ordered.map((key,i)=>[key,FIELD_COLORS[i]]));return keys.map(key=>colors.get(key));
}

async function createTimeline(sdk, name, edits, expected = {}) {
  const { pm, project, pool, timeline: sourceTimeline } = await getResolve(sdk);
  const beforeProject = String(await project.GetUniqueId()), beforeTimeline = String(await sourceTimeline.GetUniqueId());
  if ((expected.projectId && expected.projectId !== beforeProject) || (expected.timelineId && expected.timelineId !== beforeTimeline)) throw new Error('Progetto o timeline cambiati: crea una nuova analisi');
  const expectedIds=expected.mediaIds || expected.media?.map(item=>item.media_id);
  const items=expectedIds ? await analyzedMediaItems(pool,expectedIds,expected.media || [],sourceTimeline) : await selectedClips(pool);
  const byId = new Map(await Promise.all(items.map(async item => [String(await item.GetMediaId()), item])));
  if (!edits.length || edits.some(edit => !byId.has(edit.media_id) || edit.end_frame <= edit.start_frame)) throw new Error('Piano incompleto o sorgente analizzata non disponibile; timeline non creata');
  const security=require('./ipc_security');
  const reviewed=edits.flatMap(edit=>{
    const rows=[];
    if(edit.reaction_before && edit.reaction_enabled!==false){const reaction=security.validateReaction(edit.reaction_before,expected.media?.find(m=>m.media_id===edit.reaction_before.media_id));if(reaction.enabled)rows.push({...reaction,beat_id:edit.beat_id});}
    rows.push(edit);
    if(edit.action_after!==undefined){if(!Array.isArray(edit.action_after))throw Error('Raccordi azione non validi');for(const action of edit.action_after)rows.push(security.validateAction(action,expected.media?.find(m=>m.media_id===action.media_id)));}
    return rows;
  });
  const raw=reviewed.flatMap((value,index)=>{
    const shot=expected.analysis?.shots?.find(s=>s.media_id===value.media_id && s.start_frame<value.end_frame && s.end_frame>value.start_frame && s.visible_subjects?.length);
    const edit={...value,visible_subjects:value.visible_subjects?.length?value.visible_subjects:shot?.visible_subjects};
    edit.field_color_key=fieldColorKey(edit,index);
    if(!byId.has(edit.media_id))throw Error('Sorgente del raccordo non disponibile');
    const ranges=edit.source_ranges ?? [{start_frame:edit.start_frame,end_frame:edit.end_frame}];
    if(!Array.isArray(ranges) || !ranges.length || ranges.some((r,i)=>!Number.isInteger(r.start_frame)||!Number.isInteger(r.end_frame)||r.end_frame<=r.start_frame||r.start_frame<edit.start_frame||r.end_frame>edit.end_frame||(i>0 && r.start_frame<ranges[i-1].end_frame)))throw Error('Intervalli ritmo non validi');
    const overlay=edit.reaction_overlay && security.validateOverlay(edit.reaction_overlay,edit,expected.media?.find(m=>m.media_id===edit.reaction_overlay.media_id));
    if(overlay && !byId.has(overlay.media_id))throw Error('Sorgente della reazione non disponibile');
    let offset=0;const output=[];
    for(const r of ranges){
      const length=r.end_frame-r.start_frame,split=overlay?Math.max(0,Math.min(length,overlay.offset_frames-offset)):length;
      if(split)output.push({...edit,start_frame:r.start_frame,end_frame:r.start_frame+split});
      if(split<length){const delta=offset+split-overlay.offset_frames;output.push({...overlay,field_color_key:fieldColorKey(overlay,index),start_frame:overlay.start_frame+delta,end_frame:overlay.start_frame+delta+length-split,audio_source:{media_id:edit.media_id,start_frame:r.start_frame+split,end_frame:r.end_frame}});}
      offset+=length;
    }return output;
  });
  const expanded=[];
  for(const edit of raw){
    const left=expanded.at(-1),audio=edit.audio_source || edit,priorAudio=left?.audio_source || left;
    if(left && left.media_id===edit.media_id && left.shot_size===edit.shot_size){
      if(left.end_frame!==edit.start_frame)throw Error('Jump cut sulla stessa inquadratura: ricalcola il premontato per ripristinare la continuità');
      if(left.field_color_key===edit.field_color_key && priorAudio.media_id===audio.media_id && priorAudio.end_frame===audio.start_frame){left.end_frame=edit.end_frame;if(left.audio_source)left.audio_source.end_frame=audio.end_frame;continue;}
    }
    expanded.push({...edit,audio_source:edit.audio_source?{...edit.audio_source}:undefined});
  }
  // Only the new timeline is changed. Source audio mapping and Media Pool colors stay intact.
  const layout = size => size === 'medium' ? 2 : ['close','detail'].includes(size) ? 3 : 1;
  const fieldColors=assignFieldColors(expanded);
  const version=require('./package.json').version;
  const originalFolder=await pool.GetCurrentFolder();
  let targetFolder=await pool.GetRootFolder();
  const folderPath=['Premontato','v'+version,expected.purpose==='test'?'Test':'Revisioni'];
  for(const part of folderPath){
    let found=null;for(const folder of await targetFolder.GetSubFolderList() || [])if(await folder.GetName()===part){found=folder;break;}
    targetFolder=found || await pool.AddSubFolder(targetFolder,part);
    if(!targetFolder)throw new Error('Resolve non ha creato la cartella '+part);
  }
  let newTimeline;
  try {
    if(!await pool.SetCurrentFolder(targetFolder))throw new Error('Resolve non ha selezionato la cartella delle timeline');
    const title=name.includes('v'+version)?name:'PREMONTATO v'+version+' - '+name;
    newTimeline=await pool.CreateEmptyTimeline(title);
  } finally {
    if(!await pool.SetCurrentFolder(originalFolder)){
      if(newTimeline)await pool.DeleteTimelines([newTimeline]);
      throw new Error('Resolve non ha ripristinato la cartella Media Pool iniziale');
    }
  }
  if(!newTimeline)throw new Error('Resolve non ha creato la nuova timeline');
  let created = false, failure, audioSegments=0;
  try {
    const timelineMedia=await newTimeline.GetMediaPoolItem();
    const timelineMediaId=timelineMedia && String(await timelineMedia.GetMediaId());
    const inFolder=async()=>{for(const item of await targetFolder.GetClipList() || [])if(String(await item.GetMediaId())===timelineMediaId)return true;return false;};
    if(!timelineMedia || !await inFolder() && (!await pool.MoveClips([timelineMedia],targetFolder) || !await inFolder()))throw new Error('Resolve non ha organizzato la timeline nella cartella prevista');
    if (!await project.SetCurrentTimeline(newTimeline)) throw new Error('Resolve non ha attivato la timeline di prova');
    const defaultAudioTracks=Number(await newTimeline.GetTrackCount('audio'));
    // Resolve refuses deletion of its final audio track: add replacements first.
    for(let i=0;i<3;i++)if(!await newTimeline.AddTrack('audio','mono'))throw new Error('Resolve non ha creato le tracce mono');
    for (let i=defaultAudioTracks;i>=1;i--) {
      if ((await newTimeline.GetItemListInTrack('audio',i) || []).length || !await newTimeline.DeleteTrack('audio',i)) throw new Error('Impossibile preparare le tracce mono');
    }
    for(let i=Number(await newTimeline.GetTrackCount('video'));i>3;i--) {
      if ((await newTimeline.GetItemListInTrack('video',i) || []).length || !await newTimeline.DeleteTrack('video',i)) throw new Error('Impossibile preparare le tracce video');
    }
    for(let i=Number(await newTimeline.GetTrackCount('video'));i<3;i++) if(!await newTimeline.AddTrack('video')) throw new Error('Resolve non ha creato le tracce video');
    const names=['Master e larghe','Medie','Strette e dettagli'];
    for(let i=1;i<=3;i++) {
      if(!await newTimeline.SetTrackName('video',i,names[i-1]) || !await newTimeline.SetTrackName('audio',i,names[i-1])) throw new Error('Resolve non ha nominato le tracce');
    }
    const checkLayout=async()=>{
      if(Number(await newTimeline.GetTrackCount('video'))!==3 || Number(await newTimeline.GetTrackCount('audio'))!==3) throw new Error('Resolve ha modificato il numero delle tracce; timeline di prova annullata');
      for(let i=1;i<=3;i++)if(String(await newTimeline.GetTrackSubType('audio',i)).toLowerCase()!=='mono')throw new Error('Resolve non ha mantenuto le tracce audio mono; timeline di prova annullata');
    };
    await checkLayout();
    let cursor=Number(await newTimeline.GetStartFrame());
    if(!Number.isFinite(cursor))throw new Error('Inizio timeline non disponibile');
    const mappingBefore=new Map();
    for(const [id,media] of byId)if(typeof media.GetAudioMapping==='function')mappingBefore.set(id,await media.GetAudioMapping());
    for (let i=0;i<expanded.length;i++) {
      const edit=expanded[i],track=layout(edit.shot_size),color=fieldColors[i],media=byId.get(edit.media_id);
      const clip={mediaPoolItem:media,startFrame:edit.start_frame,endFrame:edit.end_frame,trackIndex:track,recordFrame:cursor};
      const video=await pool.AppendToTimeline([{...clip,mediaType:1}]) || [];
      if(video.length!==1)throw new Error('Resolve ha inserito '+i+' di '+expanded.length+' tagli; timeline di prova annullata');
      const item=video[0],nativeStart=Number(await item.GetStart()),nativeEnd=Number(await item.GetEnd());
      if(nativeStart!==cursor || !Number.isFinite(nativeEnd) || nativeEnd<=cursor)throw new Error('Resolve ha alterato la posizione del taglio '+(i+1));
      const sourceMedia=await item.GetMediaPoolItem(),mediaId=sourceMedia && String(await sourceMedia.GetMediaId());
      const verifySource=async(target,sourceEdit=edit)=>{
        const record=expected.media?.find(m=>m.media_id===sourceEdit.media_id),sourceMedia=byId.get(sourceEdit.media_id);
        const sourceFps=Number(record?.fps) || Number(await sourceTimeline.GetSetting?.('timelineFrameRate')) || 25;
        const sourceTc=record?.start_tc || (typeof sourceMedia.GetClipProperty==='function' ? await sourceMedia.GetClipProperty('Start TC') : null);
        const sourceBase=sourceTc ? timecodeToFrames(sourceTc,sourceFps)/sourceFps : 0;
        const start=Number(await target.GetSourceStartTime()),end=Number(await target.GetSourceEndTime());
        if(!Number.isFinite(start)||!Number.isFinite(end)||Math.abs(start-sourceBase-sourceEdit.start_frame/sourceFps)>.5/sourceFps||Math.abs(end-sourceBase-sourceEdit.end_frame/sourceFps)>.5/sourceFps)throw Error('Resolve ha alterato il taglio '+(i+1)+'; timeline di prova annullata');
      };
      if(mediaId!==String(edit.media_id))throw new Error('Sorgente del taglio non corretta');
      const videoTrack=await item.GetTrackTypeAndIndex();if(videoTrack[0]!=='video' || Number(videoTrack[1])!==track)throw new Error('Resolve ha inserito il video sulla traccia errata');
      await verifySource(item);
      const setColor=async target=>{if(!await target.SetClipColor(color) || await target.GetClipColor()!==color)throw new Error('Resolve non ha applicato il colore del campo');};
      await setColor(item);
      // A video-only source may legitimately have no audio mapping.
      const audioSource=edit.audio_source || edit,audioMedia=byId.get(audioSource.media_id);
      let hasAudio=true;
      if(mappingBefore.has(audioSource.media_id)) {
        let mapping=mappingBefore.get(audioSource.media_id);if(typeof mapping==='string'){try{mapping=JSON.parse(mapping);}catch{throw new Error('Mappatura audio sorgente non leggibile');}}
        if(mapping && Number(mapping.embedded_audio_channels)===0 && !Number(mapping.linked_audio_channels) && !Object.keys(mapping.track_mapping || {}).length)hasAudio=false;
      }
      if(hasAudio){
        const audio=await pool.AppendToTimeline([{...clip,mediaPoolItem:audioMedia,startFrame:audioSource.start_frame,endFrame:audioSource.end_frame,mediaType:2}]) || [];
        if(audio.length!==1)throw new Error('Resolve non ha inserito una sola clip audio sulla traccia mono; timeline di prova annullata');
        const sound=audio[0];
        if(Number(await sound.GetStart())!==nativeStart || Number(await sound.GetEnd())!==nativeEnd || String(await (await sound.GetMediaPoolItem()).GetMediaId())!==String(audioSource.media_id))throw new Error('Audio e video non sincronizzati');
        const audioTrack=await sound.GetTrackTypeAndIndex();if(audioTrack[0]!=='audio' || Number(audioTrack[1])!==track)throw new Error('Resolve ha inserito l’audio sulla traccia errata');
        await verifySource(sound,audioSource);await setColor(sound);
        if(!await newTimeline.SetClipsLinked([item,sound],true))throw new Error('Resolve non ha collegato audio e video');
        audioSegments++;
      }
      await checkLayout();cursor=nativeEnd;
    }
    let videos=0,audios=0;
    for(let i=1;i<=3;i++){videos+=(await newTimeline.GetItemListInTrack('video',i) || []).length;audios+=(await newTimeline.GetItemListInTrack('audio',i) || []).length;}
    if(videos!==expanded.length || audios!==audioSegments)throw new Error('Numero di clip non coerente; timeline di prova annullata');
    for(const [id,before] of mappingBefore)if(JSON.stringify(await byId.get(id).GetAudioMapping())!==JSON.stringify(before))throw new Error('Resolve ha modificato la mappatura audio sorgente');
    if(String(await project.GetUniqueId())!==beforeProject || String(await sourceTimeline.GetUniqueId())!==beforeTimeline)throw new Error('Progetto o timeline di partenza cambiati durante la creazione');
    created=true;
  } catch(error){failure=error;}
  const restored=await project.SetCurrentTimeline(sourceTimeline);
  if(!created)await pool.DeleteTimelines([newTimeline]);
  if(failure)throw failure;
  const active=await project.GetCurrentTimeline();
  if(!restored || !active || String(await active.GetUniqueId())!==beforeTimeline)throw new Error('Timeline creata, ma Resolve non ha ripristinato quella di partenza');
  if(expected.activateCreated===true){
    if(!await project.SetCurrentTimeline(newTimeline) || String(await (await project.GetCurrentTimeline()).GetUniqueId())!==String(await newTimeline.GetUniqueId()))throw new Error('Timeline creata, ma Resolve non l’ha aperta. Cercala in '+folderPath.join(' / '));
  }
  return {opened:expected.activateCreated===true,timelineId:String(await newTimeline.GetUniqueId()),timelineName:String(await newTimeline.GetName()),sourceTimelineId:beforeTimeline,included:edits.length,segments:expanded.length,audioSegments,videoTracks:3,audioTracks:3,audioFormat:'mono',version,folderPath:folderPath.join(' / ')};
}

async function saveCurrentProject(sdk, expectedProjectId) {
 const resolve=await sdk.GetResolvePromise();if(!resolve)throw new Error('Resolve non disponibile per il salvataggio');
 const pm=await resolve.GetProjectManager(),project=pm && await pm.GetCurrentProject();
 if(!project)throw new Error('Apri un progetto Resolve prima di salvare');
 const projectId=String(await project.GetUniqueId()),name=String(await project.GetName());
 if(expectedProjectId && projectId!==expectedProjectId)throw new Error('Il progetto Resolve è cambiato: salvataggio automatico non eseguito');
 if(await pm.SaveProject()!==true)throw new Error('Resolve non ha salvato il progetto: aggiornamento interrotto');
 const after=await pm.GetCurrentProject();if(!after || String(await after.GetUniqueId())!==projectId)throw new Error('Il progetto Resolve è cambiato durante il salvataggio');
 return {projectId,name,savedAt:new Date().toISOString()};
}

module.exports = { assignFieldColors, saveCurrentProject, getResolve, snapshot, getTranscript, getSelectedTranscriptions, transcribeSelected, analyzeIntellisearchSelected, parsePeopleMetadata, timecodeToFrames, createTimeline };
