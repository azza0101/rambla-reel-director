"""End-of-workflow live theme controls."""

PANEL = r'''
<section class="panel themeSettingsV45" id="themeSettingsV45">
  <details>
    <summary>⚙ IMPOSTAZIONI GRAFICHE</summary>
    <p class="muted">Cambia lo sfondo generale e il colore di ogni sezione. L'anteprima è immediata; salva per mantenerla dopo il riavvio.</p>
    <div id="themeSettingsRowsV45" class="themeSettingsRowsV45"></div>
    <div class="themeSettingsActionsV45"><button id="saveThemeSettingsV45" class="primary">SALVA IMPOSTAZIONI</button><button id="resetThemeSettingsV45" class="ghost">RIPRISTINA COLORI</button><span id="themeSettingsStatusV45" role="status" class="muted"></span></div>
  </details>
</section>
'''

CSS = r'''<style id="theme-settings-v45-style">
.themeSettingsV45{margin-bottom:28px}.themeSettingsV45>details>summary{display:flex;align-items:center;gap:9px;cursor:pointer;font-size:14px;font-weight:850;letter-spacing:.06em}.themeSettingsV45>details[open]>summary{margin-bottom:12px}.themeSettingsRowsV45{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:10px;margin-top:13px}.themePaintV45{display:grid;grid-template-columns:minmax(110px,1fr) auto auto auto;gap:8px;align-items:center;padding:10px 11px;border:1px solid #4c5275;border-radius:12px;background:#1c2038}.themePaintV45 b{font-size:11px}.themePaintV45 select{min-width:92px;padding:7px 8px;border:1px solid #555d83;border-radius:8px;background:#202541;color:#f2f2ff}.themePaintV45 input[type=color]{width:34px;height:30px;padding:2px;border:1px solid #626b96;border-radius:8px;background:#171b31;cursor:pointer}.themePaintV45 input[type=color]:disabled{opacity:.25;cursor:not-allowed}.themeSettingsActionsV45{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-top:14px}.themeSettingsActionsV45 span{font-size:11px}@media(max-width:700px){.themePaintV45{grid-template-columns:1fr auto auto}.themePaintV45 b{grid-column:1/-1}}
</style>'''

JS = r'''
const themeDefaultsV45={canvas:{mode:'solid',color_a:'#0b0e10',color_b:'#0b0e10'},sections:Object.fromEntries(Array.from({length:7},(_,i)=>[String(i+1),{mode:'solid',color_a:'#13171b',color_b:'#171c21'}]))};
let themePreferencesV45=JSON.parse(JSON.stringify(themeDefaultsV45));
function themeBackgroundV45(paint){return paint.mode==='gradient'?`linear-gradient(145deg,${paint.color_a},${paint.color_b})`:paint.color_a}
function applyThemePreferencesV45(theme){
 document.body.style.setProperty('background',themeBackgroundV45(theme.canvas),'important');
 for(const [step,paint] of Object.entries(theme.sections||{})){const node=document.querySelector(`[data-workflow-step-v42="${step}"]`);if(node)node.style.setProperty('background',themeBackgroundV45(paint),'important')}
}
function themeRowV45(key,label,paint){
 const row=document.createElement('article');row.className='themePaintV45';row.dataset.themeKey=key;
 row.innerHTML=`<b>${label}</b><select aria-label="Tipo sfondo ${label}"><option value="solid">SOLIDO</option><option value="gradient">GRADIENTE</option></select><input type="color" aria-label="Colore principale ${label}"><input type="color" aria-label="Secondo colore ${label}">`;
 const select=row.querySelector('select'),colors=row.querySelectorAll('input');select.value=paint.mode;colors[0].value=paint.color_a;colors[1].value=paint.color_b;colors[1].disabled=paint.mode==='solid';
 const update=()=>{const target=key==='canvas'?themePreferencesV45.canvas:themePreferencesV45.sections[key];target.mode=select.value;target.color_a=colors[0].value;target.color_b=colors[1].value;colors[1].disabled=select.value==='solid';applyThemePreferencesV45(themePreferencesV45);$('themeSettingsStatusV45').textContent='Anteprima attiva · modifiche non ancora salvate'};
 select.onchange=update;colors[0].oninput=update;colors[1].oninput=update;return row;
}
function renderThemeSettingsV45(){
 const root=$('themeSettingsRowsV45');if(!root)return;root.innerHTML='';root.append(themeRowV45('canvas','SFONDO GENERALE',themePreferencesV45.canvas));
 for(let step=1;step<=7;step++)root.append(themeRowV45(String(step),`SEZIONE ${step}`,themePreferencesV45.sections[String(step)]));
 applyThemePreferencesV45(themePreferencesV45);
}
async function loadThemePreferencesV45(){try{const result=await api('/theme-preferences');themePreferencesV45=result.theme;renderThemeSettingsV45()}catch(error){renderThemeSettingsV45();$('themeSettingsStatusV45').textContent=error.message||String(error)}}
async function saveThemePreferencesV45(){const button=$('saveThemeSettingsV45');button.disabled=true;try{const result=await api('/theme-preferences',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(themePreferencesV45)});themePreferencesV45=result.theme;applyThemePreferencesV45(themePreferencesV45);$('themeSettingsStatusV45').textContent='✓ Impostazioni salvate'}catch(error){$('themeSettingsStatusV45').textContent=error.message||String(error)}finally{button.disabled=false}}
$('saveThemeSettingsV45').onclick=saveThemePreferencesV45;
$('resetThemeSettingsV45').onclick=async()=>{themePreferencesV45=JSON.parse(JSON.stringify(themeDefaultsV45));renderThemeSettingsV45();await saveThemePreferencesV45()};
loadThemePreferencesV45();
'''
