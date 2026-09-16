from __future__ import annotations

"""Product UI augmentation for project/media lifecycle controls.

The established Curation V1 page owns the editor state and media rendering. This
module injects the management controls into the same closure, so project library,
media cleanup and beat-scoped research reuse the proven state/hydration logic.
"""

from .curation_ui import render_curation_page


_MANAGEMENT_CSS = r"""
<style id="management-v2-style">
.managementV2{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:10px 0}.managementV2 button{font-size:12px}.dangerV2{border-color:#75383f!important;color:#ffb4bc!important;background:#28151a!important}.libraryV2{width:min(980px,92vw);max-height:82vh;overflow:auto}.projectRowsV2{display:grid;gap:8px;margin:12px 0}.projectRowV2{display:grid;grid-template-columns:minmax(180px,1.6fr) minmax(120px,.8fr) minmax(100px,.5fr) auto;gap:10px;align-items:center;border:1px solid var(--line);background:#0d131b;border-radius:10px;padding:10px}.projectRowV2 strong,.projectRowV2 small{display:block}.projectRowV2 .actionsV2{display:flex;gap:6px;flex-wrap:wrap}.showMoreV2{margin:8px 0 0}.beatResearchStateV2{color:var(--muted);font-size:12px}.storageV2{font-variant-numeric:tabular-nums}@media(max-width:850px){.projectRowV2{grid-template-columns:1fr}.projectRowV2 .actionsV2{justify-content:flex-start}}
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
const shelfLimitsV2={verticalVideos:3,videos:3,stockVideos:3,images:4};
function formatBytesV2(value){let n=Number(value||0);if(n<1024)return `${n} B`;const units=['KB','MB','GB','TB'];let i=-1;do{n/=1024;i++}while(n>=1024&&i<units.length-1);return `${n.toFixed(n>=100?0:n>=10?1:2)} ${units[i]}`}
function activeChunkV2(){return (state.data.chunks||[]).find(c=>c.id===state.active)||null}
function shelfAssetsV2(chunk,id){if(!chunk)return[];if(id==='verticalVideos')return chunk.assets.filter(a=>a.kind==='video'&&VERTICAL.has(a.provider));if(id==='videos')return chunk.assets.filter(a=>a.kind==='video'&&a.provider!=='pexels'&&!VERTICAL.has(a.provider));if(id==='stockVideos')return chunk.assets.filter(a=>a.kind==='video'&&a.provider==='pexels');return chunk.assets.filter(a=>a.kind==='image')}
function bindCardsV2(chunk){document.querySelectorAll('.card').forEach(node=>{const media=node.querySelector('video,img'),select=node.querySelector('.select');if(media)media.onclick=()=>inspectMedia(media);if(select)select.onclick=()=>pick(chunk.id,node.dataset.a)})}
function installShelfExpansionV2(chunk,id){const container=$(id),assets=shelfAssetsV2(chunk,id),limit=shelfLimitsV2[id],key=`${chunk.id}:${id}`;let button=document.getElementById(`moreV2-${id}`);if(assets.length<=limit){if(button)button.remove();return}if(!button){button=document.createElement('button');button.id=`moreV2-${id}`;button.className='ghost showMoreV2';container.insertAdjacentElement('afterend',button)}const expanded=expandedShelvesV2.has(key);button.textContent=expanded?'SHOW LESS':`SHOW MORE (${assets.length-limit})`;button.onclick=()=>{expanded?expandedShelvesV2.delete(key):expandedShelvesV2.add(key);draw()};if(expanded){container.innerHTML=assets.map(card).join('');bindCardsV2(chunk)}}
async function refreshProjectsV2(){const payload=await api('/projects'),rows=payload.projects||[],box=$('projectRowsV2');$('libraryTotalV2').textContent=`${rows.length} projects · ${formatBytesV2(rows.reduce((n,r)=>n+Number(r.size_bytes||0),0))}`;box.innerHTML=rows.length?rows.map(r=>`<article class="projectRowV2" data-project-v2="${esc(r.project_id)}"><div><strong>${esc(r.name||'Untitled project')}</strong><small>${esc(r.project_id)} · ${esc(r.source_filename||'No source')}</small></div><div><small>${r.has_transcript?'Transcript ready':'No transcript'} · ${r.has_editorial_plan?'Plan ready':'No plan'}</small><small>${esc(r.modified_at||'')}</small></div><div class="storageV2"><b>${formatBytesV2(r.size_bytes)}</b><small>${esc(r.retrieved_media_count||0)} media</small></div><div class="actionsV2"><button data-open-v2="${esc(r.project_id)}">OPEN</button><button data-rename-v2="${esc(r.project_id)}">RENAME</button><button class="dangerV2" data-delete-v2="${esc(r.project_id)}">DELETE</button></div></article>`).join(''):'<p class="muted">No saved projects.</p>';box.querySelectorAll('[data-open-v2]').forEach(b=>b.onclick=()=>openProjectV2(b.dataset.openV2));box.querySelectorAll('[data-rename-v2]').forEach(b=>b.onclick=()=>renameProjectV2(b.dataset.renameV2));box.querySelectorAll('[data-delete-v2]').forEach(b=>b.onclick=()=>deleteProjectV2(b.dataset.deleteV2))}
async function openProjectV2(pid){const p=await api(`/projects/${pid}`);state.pid=pid;localStorage.setItem('rambla-project',pid);show(p,p.source_video?.path?.split(/[\\/]/).pop()||p.name||'Reel',`/api/curation/projects/${pid}/media/source-video/source`);await hydrate();$('projectLibraryV2').close()}
async function renameProjectV2(pid){const row=(await api('/projects')).projects.find(x=>x.project_id===pid),name=prompt('Rename project',row?.name||'');if(name==null)return;const p=await api(`/projects/${pid}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});if(state.pid===pid){state.project=p;$('projectStatus').textContent=`Project ${pid} · ${p.name} · autosaved locally`}await refreshProjectsV2()}
async function deleteProjectV2(pid){const listing=await api('/projects'),row=listing.projects.find(x=>x.project_id===pid);if(!confirm(`This will permanently delete “${row?.name||pid}” and free about ${formatBytesV2(row?.size_bytes||0)}. Continue?`))return;await api(`/projects/${pid}`,{method:'DELETE'});if(state.pid===pid){localStorage.removeItem('rambla-project');state.pid=null;state.project=null;resetProjectView();$('projectStatus').textContent='Project deleted. Choose or create another project.'}await refreshProjectsV2()}
async function cleanMediaV2(){if(!state.pid)return;if(!confirm('Delete downloaded/search B-roll, images and previews for this project? Transcript and editorial plan stay safe.'))return;$('cleanMediaV2').disabled=true;try{const result=await api(`/projects/${state.pid}/media/clean`,{method:'POST'});expandedShelvesV2.clear();await hydrate();const c=result.cleanup||{};$('runStatus').textContent=`Media cleaned · ${c.deleted_files||0} files · ${formatBytesV2(c.deleted_bytes||0)} freed`}finally{$('cleanMediaV2').disabled=false}}
async function researchBeatV2(mode){const chunk=activeChunkV2();if(!chunk||chunk.action!=='BROLL'||state.run)return;const replace=mode==='replace';if(replace&&!confirm('Replace the current B-roll and image results for this beat with a new search? Existing selections for this beat will be cleared.'))return;const buttons=$('beatActionsV2').querySelectorAll('button');buttons.forEach(b=>b.disabled=true);$('beatResearchStateV2').textContent=replace?'Starting new search…':'Searching for additional unique results…';try{const r=await api(`/projects/${state.pid}/beats/${encodeURIComponent(chunk.id)}/research`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:replace?'replace':'append'})});if(r.status==='started')await watch(r.run_id);else await hydrate()}catch(e){buttons.forEach(b=>b.disabled=false);$('beatResearchStateV2').textContent=e.message||String(e);throw e}}
function installManagementV2(){const chunk=activeChunkV2();$('cleanMediaV2').disabled=!state.pid||!state.data.editorial_plan_ready||!!state.run;const actions=$('beatActionsV2');if(chunk?.action==='BROLL'){actions.innerHTML=`<button id="newSearchV2" ${state.run?'disabled':''}>NEW SEARCH</button><button id="addResultsV2" ${state.run?'disabled':''}>ADD RESULTS</button><span id="beatResearchStateV2" class="beatResearchStateV2"></span>`;$('newSearchV2').onclick=()=>researchBeatV2('replace');$('addResultsV2').onclick=()=>researchBeatV2('append');for(const id of Object.keys(shelfLimitsV2))installShelfExpansionV2(chunk,id)}else{actions.innerHTML='';for(const id of Object.keys(shelfLimitsV2)){const b=document.getElementById(`moreV2-${id}`);if(b)b.remove()}}}
const drawBaseV2=draw;draw=()=>{drawBaseV2();installManagementV2()};
$('projectsV2').onclick=async()=>{$('projectLibraryV2').showModal();await refreshProjectsV2()};$('closeProjectsV2').onclick=()=>$('projectLibraryV2').close();$('refreshProjectsV2').onclick=refreshProjectsV2;$('cleanMediaV2').onclick=cleanMediaV2;
"""


def render_curation_page_v2(build_token: str | None = None) -> str:
    html = render_curation_page(build_token)
    html = html.replace(
        '<button id="saveProject" class="ghost" disabled>SAVE PROJECT FILE</button>',
        '<button id="saveProject" class="ghost" disabled>SAVE PROJECT FILE</button><button id="projectsV2" class="ghost">PROJECTS</button>',
        1,
    )
    html = html.replace(
        '<button id="findImages" disabled>FIND IMAGES</button>',
        '<button id="findImages" disabled>FIND IMAGES</button><button id="cleanMediaV2" class="ghost" disabled>CLEAN MEDIA</button>',
        1,
    )
    html = html.replace(
        '<section class="stage"><div id="active" class="muted">No project artifacts loaded.</div>',
        '<section class="stage"><div id="active" class="muted">No project artifacts loaded.</div><div id="beatActionsV2" class="managementV2"></div>',
        1,
    )
    html = html.replace('</style>', '</style>' + _MANAGEMENT_CSS, 1)
    html = html.replace('</main><dialog id="lightbox">', _PROJECT_DIALOG + '</main><dialog id="lightbox">', 1)
    needle = 'draw();restore()})();</script></html>'
    if needle not in html:
        raise RuntimeError('curation V1 bootstrap marker changed; management UI injection aborted')
    return html.replace(needle, _MANAGEMENT_JS + needle, 1)
