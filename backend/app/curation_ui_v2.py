from __future__ import annotations

"""Product UI augmentation for project/media lifecycle and social controls.

The established Curation V1 page owns the editor state and media rendering. This
module injects project management, beat research and authenticated social source
controls into the same closure so all additions reuse proven state/hydration.
"""

from .curation_ui import render_curation_page


_MANAGEMENT_CSS = r"""
<style id="management-v2-style">
.managementV2{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:10px 0}.managementV2 button{font-size:12px}.dangerV2{border-color:#75383f!important;color:#ffb4bc!important;background:#28151a!important}.libraryV2{width:min(980px,92vw);max-height:82vh;overflow:auto}.projectRowsV2{display:grid;gap:8px;margin:12px 0}.projectRowV2{display:grid;grid-template-columns:minmax(180px,1.6fr) minmax(120px,.8fr) minmax(100px,.5fr) auto;gap:10px;align-items:center;border:1px solid var(--line);background:#0d131b;border-radius:10px;padding:10px}.projectRowV2 strong,.projectRowV2 small{display:block}.projectRowV2 .actionsV2{display:flex;gap:6px;flex-wrap:wrap}.showMoreV2{margin:8px 0 0}.beatResearchStateV2{color:var(--muted);font-size:12px}.storageV2{font-variant-numeric:tabular-nums}.socialStateV2{display:inline-block;margin-left:4px;padding:2px 6px;border-radius:999px;border:1px solid #596879;font-size:10px;font-weight:800}.socialStateV2.ready{border-color:#86e89f;color:#86e89f}.socialStateV2.preview{border-color:#ffd166;color:#ffd166}.socialStateV2.manual{border-color:#ff9f9f;color:#ff9f9f}.socialLoginStateV2{font-size:11px;color:var(--muted)}@media(max-width:850px){.projectRowV2{grid-template-columns:1fr}.projectRowV2 .actionsV2{justify-content:flex-start}}
</style>
"""

_PROJECT_DIALOG = r"""
<dialog id="projectLibraryV2" class="libraryV2">
  <div class="top"><div><h2 style="margin:0">Project Library</h2><div class="muted">Open, rename or remove local RAMBLA projects. Disk usage is calculated from the actual project folder.</div></div><button id="closeProjectsV2">CLOSE</button></div>
  <div class="row" style="margin-top:10px"><b>Disk usage</b><span id="libraryTotalV2" class="muted storageV2"></span><button id="refreshProjectsV2" class="ghost">REFRESH</button></div>
  <div id="projectRowsV2" class="projectRowsV2"><p class="muted">Loading projects…</p></div>
</dialog>
"""

_MANAGEMENT_JS = r"""
const expandedShelvesV2=new Set();
const shelfLimitsV2={verticalVideos:3,tiktokVideosV2:3,instagramVideosV2:3,webNewsVideosV2:3,videos:3,stockVideos:3,images:4};
function formatBytesV2(value){let n=Number(value||0);if(n<1024)return `${n} B`;const units=['KB','MB','GB','TB'];let i=-1;do{n/=1024;i++}while(n>=1024&&i<units.length-1);return `${n.toFixed(n>=100?0:n>=10?1:2)} ${units[i]}`}
function activeChunkV2(){return (state.data.chunks||[]).find(c=>c.id===state.active)||null}
function shelfAssetsV2(chunk,id){if(!chunk)return[];if(id==='verticalVideos')return chunk.assets.filter(a=>a.kind==='video'&&a.provider==='youtube_shorts');if(id==='tiktokVideosV2')return chunk.assets.filter(a=>a.kind==='video'&&a.provider==='tiktok');if(id==='instagramVideosV2')return chunk.assets.filter(a=>a.kind==='video'&&a.provider==='instagram');if(id==='webNewsVideosV2')return chunk.assets.filter(a=>a.kind==='video'&&a.provider==='web_video');if(id==='videos')return chunk.assets.filter(a=>a.kind==='video'&&a.provider!=='pexels'&&!VERTICAL.has(a.provider)&&a.provider!=='web_video');if(id==='stockVideos')return chunk.assets.filter(a=>a.kind==='video'&&a.provider==='pexels');return chunk.assets.filter(a=>a.kind==='image')}
function bindCardsV2(chunk){document.querySelectorAll('.card').forEach(node=>{const media=node.querySelector('video,img'),select=node.querySelector('.select');if(media)media.onclick=()=>inspectMedia(media);if(select)select.onclick=()=>pick(chunk.id,node.dataset.a)})}
function installShelfExpansionV2(chunk,id){const container=$(id),assets=shelfAssetsV2(chunk,id),limit=shelfLimitsV2[id],key=`${chunk.id}:${id}`;if(!container)return;let button=document.getElementById(`moreV2-${id}`);if(assets.length<=limit){if(button)button.remove();return}if(!button){button=document.createElement('button');button.id=`moreV2-${id}`;button.className='ghost showMoreV2';container.insertAdjacentElement('afterend',button)}const expanded=expandedShelvesV2.has(key);button.textContent=expanded?'SHOW LESS':`SHOW MORE (${assets.length-limit})`;button.onclick=()=>{expanded?expandedShelvesV2.delete(key):expandedShelvesV2.add(key);draw()};if(expanded){container.innerHTML=assets.map(card).join('');bindCardsV2(chunk)}}
async function refreshProjectsV2(){const payload=await api('/projects'),rows=payload.projects||[],box=$('projectRowsV2');$('libraryTotalV2').textContent=`${rows.length} projects · ${formatBytesV2(rows.reduce((n,r)=>n+Number(r.size_bytes||0),0))}`;box.innerHTML=rows.length?rows.map(r=>`<article class="projectRowV2" data-project-v2="${esc(r.project_id)}"><div><strong>${esc(r.name||'Untitled project')}</strong><small>${esc(r.project_id)} · ${esc(r.source_filename||'No source')}</small></div><div><small>${r.has_transcript?'Transcript ready':'No transcript'} · ${r.has_editorial_plan?'Plan ready':'No plan'}</small><small>${esc(r.modified_at||'')}</small></div><div class="storageV2"><b>${formatBytesV2(r.size_bytes)}</b><small>${esc(r.retrieved_media_count||0)} media</small></div><div class="actionsV2"><button data-open-v2="${esc(r.project_id)}">OPEN</button><button data-rename-v2="${esc(r.project_id)}">RENAME</button><button class="dangerV2" data-delete-v2="${esc(r.project_id)}">DELETE</button></div></article>`).join(''):'<p class="muted">No saved projects.</p>';box.querySelectorAll('[data-open-v2]').forEach(b=>b.onclick=()=>openProjectV2(b.dataset.openV2));box.querySelectorAll('[data-rename-v2]').forEach(b=>b.onclick=()=>renameProjectV2(b.dataset.renameV2));box.querySelectorAll('[data-delete-v2]').forEach(b=>b.onclick=()=>deleteProjectV2(b.dataset.deleteV2))}
async function openProjectV2(pid){const p=await api(`/projects/${pid}`);state.pid=pid;localStorage.setItem('rambla-project',pid);show(p,p.source_video?.path?.split(/[\\/]/).pop()||p.name||'Reel',`/api/curation/projects/${pid}/media/source-video/source`);await hydrate();$('projectLibraryV2').close()}
async function renameProjectV2(pid){const row=(await api('/projects')).projects.find(x=>x.project_id===pid),name=prompt('Rename project',row?.name||'');if(name==null)return;const p=await api(`/projects/${pid}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});if(state.pid===pid){state.project=p;$('projectStatus').textContent=`Project ${pid} · ${p.name} · autosaved locally`}await refreshProjectsV2()}
async function deleteProjectV2(pid){const listing=await api('/projects'),row=listing.projects.find(x=>x.project_id===pid);if(!confirm(`This will permanently delete “${row?.name||pid}” and free about ${formatBytesV2(row?.size_bytes||0)}. Continue?`))return;await api(`/projects/${pid}`,{method:'DELETE'});if(state.pid===pid){localStorage.removeItem('rambla-project');state.pid=null;state.project=null;resetProjectView();$('projectStatus').textContent='Project deleted. Choose or create another project.'}await refreshProjectsV2()}
async function cleanMediaV2(){if(!state.pid)return;if(!confirm('Delete downloaded/search B-roll, images and previews for this project? Transcript and editorial plan stay safe.'))return;$('cleanMediaV2').disabled=true;try{const result=await api(`/projects/${state.pid}/media/clean`,{method:'POST'});expandedShelvesV2.clear();await hydrate();const c=result.cleanup||{};$('runStatus').textContent=`Media cleaned · ${c.deleted_files||0} files · ${formatBytesV2(c.deleted_bytes||0)} freed`}finally{$('cleanMediaV2').disabled=false}}
async function researchBeatV2(mode){const chunk=activeChunkV2();if(!chunk||chunk.action!=='BROLL'||state.run)return;const replace=mode==='replace';if(replace&&!confirm('Replace the current B-roll and image results for this beat with a new search? Existing selections for this beat will be cleared.'))return;const buttons=$('beatActionsV2').querySelectorAll('button');buttons.forEach(b=>b.disabled=true);$('beatResearchStateV2').textContent=replace?'Starting new search…':'Searching for additional unique results…';const payload=replace?{mode:'replace'}:{mode:'append'};try{const r=await api(`/projects/${state.pid}/beats/${encodeURIComponent(chunk.id)}/research`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if(r.status==='started')await watch(r.run_id);else await hydrate()}catch(e){buttons.forEach(b=>b.disabled=false);$('beatResearchStateV2').textContent=e.message||String(e);throw e}}
function socialBackendLabelV2(value){return value==='playwright'?'Playwright':value==='chromium_dom'?'Edge/Chrome headless':'unavailable'}
function socialProviderStateV2(name,row){const profile=row?.profile_ready?'PROFILE SAVED':'NO PROFILE',ready=row?.search_ready?`search ready via ${socialBackendLabelV2(row.search_backend)}`:'search unavailable';return `${name}: ${profile} · ${ready}`}
async function socialStatusV2(){try{const s=await api('/social/status'),p=s.providers||{};$('tiktokLoginV2').textContent=`TIKTOK LOGIN${p.tiktok?.profile_ready?' · PROFILE SAVED':''}`;$('instagramLoginV2').textContent=`INSTAGRAM LOGIN${p.instagram?.profile_ready?' · PROFILE SAVED':''}`;$('socialLoginStateV2').textContent=`${socialProviderStateV2('TikTok',p.tiktok)} · ${socialProviderStateV2('Instagram',p.instagram)} · PROFILE SAVED means the local browser profile exists; it does not verify login.`}catch(e){$('socialLoginStateV2').textContent=e.message||String(e)}}
async function socialLoginV2(provider){const button=provider==='tiktok'?$('tiktokLoginV2'):$('instagramLoginV2');button.disabled=true;try{await api(`/social/${provider}/login`,{method:'POST'});$('socialLoginStateV2').textContent=`${provider} browser opened · log in normally, then CLOSE that browser window before searching. After that use NEW SEARCH or ADD RESULTS on a B-roll beat.`;setTimeout(()=>socialStatusV2(),1800)}catch(e){$('socialLoginStateV2').textContent=e.message||String(e)}finally{button.disabled=false}}
function latestSocialAttemptV2(chunk,provider){const rows=(chunk?.retrieval_diagnostics?.video_attempts||[]).filter(a=>String(a.provider||'').toLowerCase()===provider);return rows.length?rows[rows.length-1]:null}
function socialEmptyMessageV2(chunk,provider){const a=latestSocialAttemptV2(chunk,provider);const label=provider==='youtube_shorts'?'YouTube Shorts':provider==='web_video'?'Web / News':provider[0].toUpperCase()+provider.slice(1);if(!a)return `No ${label} search attempt recorded for this beat yet.`;const hits=Number(a.hits||0),query=a.query?` · query: ${a.query}`:'';if(a.browser_error)return `${label} authenticated search failed: ${a.browser_error}${a.fallback_used?' · public fallback used':''} · ${hits} results${query}`;if(a.error)return `${label} search failed: ${a.error} · ${hits} results${query}`;return `${label} searched · ${hits} results${a.fallback_used?' · public fallback used':''}${query}`}
function socialStateV2(a){if(a.preview_status==='manual'||(!a.preview_url&&a.selectable===false))return 'MANUAL';if(a.preview_status==='ready'&&a.selectable!==false)return 'CLIP READY';return 'PREVIEW'}
function decorateSocialCardsV2(chunk){for(const id of ['verticalVideos','tiktokVideosV2','instagramVideosV2','webNewsVideosV2']){const container=$(id);if(!container)continue;container.querySelectorAll('.card').forEach(node=>{const a=(chunk.assets||[]).find(x=>x.asset_id===node.dataset.a);if(!a)return;const stateLabel=socialStateV2(a),copy=node.querySelector('.copy'),badge=document.createElement('span');badge.className=`socialStateV2 ${stateLabel==='CLIP READY'?'ready':stateLabel==='MANUAL'?'manual':'preview'}`;badge.textContent=stateLabel;const head=copy?.querySelector('div');if(head&&!head.querySelector('.socialStateV2'))head.appendChild(badge);const link=copy?.querySelector('a');if(link)link.textContent='OPEN SOURCE';if(stateLabel==='MANUAL'){const img=node.querySelector('img');if(img)img.src='data:image/svg+xml;charset=utf-8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22640%22 height=%22360%22%3E%3Crect width=%22100%25%22 height=%22100%25%22 fill=%22%23202b37%22/%3E%3Ctext x=%2250%25%22 y=%2250%25%22 fill=%22%2394a3b8%22 font-size=%2226%22 text-anchor=%22middle%22 dominant-baseline=%22middle%22%3EOPEN SOURCE%3C/text%3E%3C/svg%3E'}})}}
function installSocialShelvesV2(){const chunk=activeChunkV2();if(!chunk)return;const providers={verticalVideos:'youtube_shorts',tiktokVideosV2:'tiktok',instagramVideosV2:'instagram',webNewsVideosV2:'web_video'};for(const [id,provider] of Object.entries(providers)){const box=$(id),assets=(chunk.assets||[]).filter(a=>a.kind==='video'&&a.provider===provider),limit=shelfLimitsV2[id]||3,key=`${chunk.id}:${id}`,shown=expandedShelvesV2.has(key)?assets:assets.slice(0,limit);if(box)box.innerHTML=shown.length?shown.map(card).join(''):`<p class="muted">${esc(socialEmptyMessageV2(chunk,provider))}</p>`;installShelfExpansionV2(chunk,id)}bindCardsV2(chunk);decorateSocialCardsV2(chunk)}
function installManagementV2(){const chunk=activeChunkV2();$('cleanMediaV2').disabled=!state.pid||!state.data.editorial_plan_ready||!!state.run;const actions=$('beatActionsV2');if(chunk?.action==='BROLL'){actions.innerHTML=`<button id="newSearchV2" ${state.run?'disabled':''}>NEW SEARCH</button><button id="addResultsV2" ${state.run?'disabled':''}>ADD RESULTS</button><span id="beatResearchStateV2" class="beatResearchStateV2"></span>`;$('newSearchV2').onclick=()=>researchBeatV2('replace');$('addResultsV2').onclick=()=>researchBeatV2('append');for(const id of ['videos','stockVideos','images'])installShelfExpansionV2(chunk,id)}else{actions.innerHTML='';for(const id of Object.keys(shelfLimitsV2)){const b=document.getElementById(`moreV2-${id}`);if(b)b.remove()}}installSocialShelvesV2()}
const drawBaseV2=draw;draw=()=>{drawBaseV2();installManagementV2()};
$('projectsV2').onclick=async()=>{$('projectLibraryV2').showModal();await refreshProjectsV2()};$('closeProjectsV2').onclick=()=>$('projectLibraryV2').close();$('refreshProjectsV2').onclick=refreshProjectsV2;$('cleanMediaV2').onclick=cleanMediaV2;$('tiktokLoginV2').onclick=()=>socialLoginV2('tiktok');$('instagramLoginV2').onclick=()=>socialLoginV2('instagram');socialStatusV2();
"""


def render_curation_page_v2(build_token: str | None = None) -> str:
    html = render_curation_page(build_token)
    html = html.replace('<h1>RAMBLA Curation</h1>', '<h1>RAMBLA Curation V2</h1>', 1)
    html = html.replace('CURATION V1 · build', 'CURATION V2 · build', 1)
    html = html.replace(
        '<button id="saveProject" class="ghost" disabled>SAVE PROJECT FILE</button>',
        '<button id="saveProject" class="ghost" disabled>SAVE PROJECT FILE</button><button id="projectsV2" class="ghost">PROJECTS</button>',
        1,
    )
    html = html.replace(
        '<button id="findImages" disabled>FIND IMAGES</button>',
        '<button id="findImages" disabled>FIND IMAGES</button><button id="cleanMediaV2" class="ghost" disabled>CLEAN MEDIA</button><button id="tiktokLoginV2" class="ghost">TIKTOK LOGIN</button><button id="instagramLoginV2" class="ghost">INSTAGRAM LOGIN</button><span id="socialLoginStateV2" class="socialLoginStateV2"></span>',
        1,
    )
    html = html.replace(
        '<section class="stage"><div id="active" class="muted">No project artifacts loaded.</div>',
        '<section class="stage"><div id="active" class="muted">No project artifacts loaded.</div><div id="beatActionsV2" class="managementV2"></div>',
        1,
    )
    html = html.replace('<h3>SOCIAL / SHORTS / REELS</h3>', '<h3>YOUTUBE SHORTS</h3>', 1)
    html = html.replace(
        '<div id="verticalVideos" class="cards"></div>',
        '<div id="verticalVideos" class="cards"></div><div class="shelfHead"><h3>TIKTOK</h3><small>Authenticated TikTok search first; automatic clip when possible, otherwise preview/link.</small></div><div id="tiktokVideosV2" class="cards"></div><div class="shelfHead"><h3>INSTAGRAM REELS</h3><small>Authenticated Reels discovery with public-web fallback.</small></div><div id="instagramVideosV2" class="cards"></div><div class="shelfHead"><h3>WEB / NEWS VIDEO</h3><small>Current-event video sources can remain clickable even when automatic download is unavailable.</small></div><div id="webNewsVideosV2" class="cards"></div>',
        1,
    )
    html = html.replace('</style>', '</style>' + _MANAGEMENT_CSS, 1)
    html = html.replace('</main><dialog id="lightbox">', _PROJECT_DIALOG + '</main><dialog id="lightbox">', 1)
    needle = 'draw();restore()})();</script></html>'
    if needle not in html:
        raise RuntimeError('curation V1 bootstrap marker changed; management UI injection aborted')
    return html.replace(needle, _MANAGEMENT_JS + needle, 1)
