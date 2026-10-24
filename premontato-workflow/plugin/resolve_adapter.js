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

async function snapshot(sdk) {
  const { project, timeline, pool } = await getResolve(sdk);
  const clips = await selectedClips(pool);
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

async function createTimeline(sdk, name, edits, expected = {}) {
  const { pm, project, pool, timeline: sourceTimeline } = await getResolve(sdk);
  const beforeProject = String(await project.GetUniqueId()), beforeTimeline = String(await sourceTimeline.GetUniqueId());
  if ((expected.projectId && expected.projectId !== beforeProject) || (expected.timelineId && expected.timelineId !== beforeTimeline)) throw new Error('Progetto o timeline cambiati: crea una nuova analisi');
  const items = await selectedClips(pool);
  const selectedIds = await Promise.all(items.map(async item => String(await item.GetMediaId())));
  const expectedIds = expected.mediaIds || expected.media?.map(item => item.media_id);
  if (expectedIds && (expectedIds.length !== selectedIds.length || expectedIds.some((id, index) => id !== selectedIds[index]))) throw new Error('La selezione dei media è cambiata: riseleziona le clip e ricalcola');
  const byId = new Map(await Promise.all(items.map(async item => [String(await item.GetMediaId()), item])));
  if (!edits.length || edits.some(edit => !byId.has(edit.media_id) || edit.end_frame <= edit.start_frame)) throw new Error('Piano incompleto o media non selezionato; timeline non creata');
  const expanded = edits.flatMap(edit => {
    const ranges=edit.source_ranges ?? [{start_frame:edit.start_frame,end_frame:edit.end_frame}];
    if (!Array.isArray(ranges) || !ranges.length || ranges.some((range,index)=>!Number.isInteger(range.start_frame)||!Number.isInteger(range.end_frame)||range.end_frame<=range.start_frame||range.start_frame<edit.start_frame||range.end_frame>edit.end_frame||(index>0 && range.start_frame<ranges[index-1].end_frame))) throw new Error('Intervalli ritmo non validi');
    return ranges.map(range=>({...edit,...range}));
  });
  // Only the new timeline is changed. Source audio mapping and Media Pool colors stay intact.
  const layout = size => size === 'medium' ? {track:2,color:'Green'} : ['close','detail'].includes(size) ? {track:3,color:'Orange'} : {track:1,color:size==='wide'?'Blue':'Tan'};
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
      const edit=expanded[i],{track,color}=layout(edit.shot_size),media=byId.get(edit.media_id);
      const clip={mediaPoolItem:media,startFrame:edit.start_frame,endFrame:edit.end_frame,trackIndex:track,recordFrame:cursor};
      const video=await pool.AppendToTimeline([{...clip,mediaType:1}]) || [];
      if(video.length!==1)throw new Error('Resolve ha inserito '+i+' di '+expanded.length+' tagli; timeline di prova annullata');
      const item=video[0],nativeStart=Number(await item.GetStart()),nativeEnd=Number(await item.GetEnd());
      if(nativeStart!==cursor || !Number.isFinite(nativeEnd) || nativeEnd<=cursor)throw new Error('Resolve ha alterato la posizione del taglio '+(i+1));
      const sourceMedia=await item.GetMediaPoolItem(),mediaId=sourceMedia && String(await sourceMedia.GetMediaId());
      const sourceFps=Number(expected.media?.find(m=>m.media_id===edit.media_id)?.fps) || Number(await sourceTimeline.GetSetting?.('timelineFrameRate')) || 25;
      const record=expected.media?.find(m=>m.media_id===edit.media_id);
      const sourceTc=record?.start_tc || (typeof media.GetClipProperty==='function' ? await media.GetClipProperty('Start TC') : null);
      const sourceBase=sourceTc ? timecodeToFrames(sourceTc,sourceFps)/sourceFps : 0;
      const verifySource=async target=>{
        const start=Number(await target.GetSourceStartTime()),end=Number(await target.GetSourceEndTime());
        if(!Number.isFinite(start)||!Number.isFinite(end)||Math.abs(start-sourceBase-edit.start_frame/sourceFps)>.5/sourceFps||Math.abs(end-sourceBase-edit.end_frame/sourceFps)>.5/sourceFps)throw new Error('Resolve ha alterato il taglio '+(i+1)+'; timeline di prova annullata');
      };
      if(mediaId!==String(edit.media_id))throw new Error('Sorgente del taglio non corretta');
      const videoTrack=await item.GetTrackTypeAndIndex();if(videoTrack[0]!=='video' || Number(videoTrack[1])!==track)throw new Error('Resolve ha inserito il video sulla traccia errata');
      await verifySource(item);
      const setColor=async target=>{if(!await target.SetClipColor(color) || await target.GetClipColor()!==color)throw new Error('Resolve non ha applicato il colore del campo');};
      await setColor(item);
      // A video-only source may legitimately have no audio mapping.
      let hasAudio=true;
      if(mappingBefore.has(edit.media_id)) {
        let mapping=mappingBefore.get(edit.media_id);if(typeof mapping==='string'){try{mapping=JSON.parse(mapping);}catch{throw new Error('Mappatura audio sorgente non leggibile');}}
        if(mapping && Number(mapping.embedded_audio_channels)===0 && !Number(mapping.linked_audio_channels) && !Object.keys(mapping.track_mapping || {}).length)hasAudio=false;
      }
      if(hasAudio){
        const audio=await pool.AppendToTimeline([{...clip,mediaType:2}]) || [];
        if(audio.length!==1)throw new Error('Resolve non ha inserito una sola clip audio sulla traccia mono; timeline di prova annullata');
        const sound=audio[0];
        if(Number(await sound.GetStart())!==nativeStart || Number(await sound.GetEnd())!==nativeEnd || String(await (await sound.GetMediaPoolItem()).GetMediaId())!==mediaId)throw new Error('Audio e video non sincronizzati');
        const audioTrack=await sound.GetTrackTypeAndIndex();if(audioTrack[0]!=='audio' || Number(audioTrack[1])!==track)throw new Error('Resolve ha inserito l’audio sulla traccia errata');
        await verifySource(sound);await setColor(sound);
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
  return {timelineId:String(await newTimeline.GetUniqueId()),timelineName:String(await newTimeline.GetName()),sourceTimelineId:beforeTimeline,included:edits.length,segments:expanded.length,audioSegments,videoTracks:3,audioTracks:3,audioFormat:'mono',version,folderPath:folderPath.join(' / ')};
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

module.exports = { saveCurrentProject, getResolve, snapshot, getTranscript, getSelectedTranscriptions, transcribeSelected, analyzeIntellisearchSelected, parsePeopleMetadata, timecodeToFrames, createTimeline };
