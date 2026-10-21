'use strict';
function finite(v,label){if(typeof v!=='number'||!Number.isFinite(v))throw Error(label+' non valido');return v}
function mergeRanges(ranges){
 if(!Array.isArray(ranges)||!ranges.length||ranges.length>10000)throw Error('IN - OUT not found');
 const sorted=ranges.map(r=>{finite(r.a,'IN');finite(r.b,'OUT');if(r.a<0||r.b<=r.a)throw Error('Intervallo non valido');return {a:r.a,b:r.b}}).sort((x,y)=>x.a-y.a);
 const out=[];for(const r of sorted){const last=out.at(-1);if(last&&r.a<=last.b)last.b=Math.max(last.b,r.b);else out.push(r)}return out;
}
const pad=(n,w=2)=>String(n).padStart(w,'0');
function srtTime(ms){ms=Math.max(0,Math.floor(ms+0.5));const sec=Math.floor(ms/1000);return `${pad(Math.floor(sec/3600))}:${pad(Math.floor(sec/60)%60)}:${pad(sec%60)},${pad(ms%1000,3)}`}
function prettyFrame(frame,rate,drop=false){
 frame=Math.max(0,Math.floor(frame+0.5));const n=Math.round(rate);
 if(drop&&(n===30||n===60)){const d=n===30?2:4,f10=n*600-d*9,fmin=n*60-d;frame+=d*9*Math.floor(frame/f10)+d*Math.max(0,Math.floor((frame%f10-d)/fmin))}
 const sec=Math.floor(frame/n);return `${pad(Math.floor(sec/3600))}:${pad(Math.floor(sec/60)%60)}:${pad(sec%60)}${drop?';':':'}${pad(frame%n)}`;
}
function startMs(t){const m=/^(\d+):(\d+):(\d+)[:;](\d+)$/.exec(t.startTC);if(!m||+m[2]>59||+m[3]>59||+m[4]>=Math.round(t.fps))throw Error('Timecode iniziale non valido');return (+m[1]*3600 + +m[2]*60 + +m[3])*1000 + +m[4]*1000/t.fps}
function renderSrt(t,captions,ranges,{original=true,context=false}={}){
 finite(t.fps,'FPS');finite(t.start,'Timeline start');if(t.fps<=0||t.fps>240)throw Error('FPS non valido');
 const merged=mergeRanges(ranges),selected=[],all=[];let elapsed=0;const offsets=merged.map(r=>{const value=elapsed;elapsed+=r.b-r.a;return value});
 for(const row of captions){finite(row.a,'Caption IN');finite(row.b,'Caption OUT');if(typeof row.content!=='string')throw Error('Testo sottotitolo non leggibile');if(row.b<=row.a||row.content==='')continue;all.push(row);
  merged.forEach((r,ri)=>{const a=Math.max(row.a,r.a),b=Math.min(row.b,r.b);if(b>a)selected.push({...row,a,b,ri})});
 }
 if(!selected.length)throw Error('Nessun sottotitolo negli intervalli.');
 const sort=(a,b)=>a.a-b.a||a.track-b.track||a.idx-b.idx;selected.sort(sort);all.sort(sort);
 const base=original?startMs(t):0;
 let output=selected.map((row,i)=>{
  const time=f=>original?base+(f-t.start)*1000/t.fps:(offsets[row.ri]+f-merged[row.ri].a)*1000/t.fps;
  return `${i+1}\r\n${srtTime(time(row.a))} --> ${srtTime(time(row.b))}\r\n${row.content}\r\n\r\n`;
 }).join('');
 if(context){
  const transcript=all.map(row=>row.content.replace(/\s+/g,' ').trim()).filter(Boolean).join(' ');
  output+='\r\n# RAMBLA_CONTEXT_BEGIN\r\n# Contesto completo della timeline: solo per comprendere il discorso.\r\n# '+transcript+'\r\n# RAMBLA_CONTEXT_END\r\n';
 }return output;
}
function fileName(value,timeline,mode){
 let name=String(value||'').trim();if(!name)name=String(timeline||'Timeline').replace(/[\\/:*?"<>|\x00-\x1f]/g,'_').replace(/\s+/g,'_')+'_'+(mode==='MULTI'?'MULTI':'RANGE')+'.srt';
 if(name.length>180||/[\\/:*?"<>|\x00-\x1f]/.test(name)||/[. ]$/.test(name)||/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(name))throw Error('Nome file non valido');
 return /\.srt$/i.test(name)?name:name+'.srt';
}
module.exports={mergeRanges,renderSrt,fileName,srtTime,prettyFrame,startMs};
