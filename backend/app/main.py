from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict

from .panel_service import ApplyFrozenError, PanelService


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: dict[str, Any]


class ApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: dict[str, Any]
    actor: str


class ApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: dict[str, Any]
    approval: dict[str, Any]


class FrozenApplyTransport:
    """Default transport: a second fail-closed barrier behind PanelService."""

    def apply_approved_plan(self, plan: dict[str, Any], approval: dict[str, Any]) -> dict[str, Any]:
        raise ApplyFrozenError("Resolve Apply transport is frozen")


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RAMBLA Reel Director</title>
<style>
:root { color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
* { box-sizing: border-box; }
body { margin: 0; background: #111214; color: #f4f4f2; }
main { max-width: 980px; margin: 0 auto; padding: 28px; }
header { display:flex; justify-content:space-between; align-items:center; gap:16px; margin-bottom:24px; }
h1 { font-size: 24px; margin:0; }
.badge { border:1px solid #6d4141; background:#2a1717; color:#ffb3b3; border-radius:999px; padding:7px 11px; font-size:12px; font-weight:700; letter-spacing:.06em; }
.card { background:#191b1f; border:1px solid #2d3036; border-radius:14px; padding:18px; margin-bottom:14px; }
.row { display:flex; flex-wrap:wrap; gap:10px; align-items:center; }
button, .file-label { border:0; border-radius:9px; background:#ecebe7; color:#111214; padding:10px 14px; font-weight:650; cursor:pointer; }
button.secondary { background:#2a2d32; color:#f4f4f2; border:1px solid #3a3e45; }
button:disabled { opacity:.38; cursor:not-allowed; }
input[type=file] { display:none; }
input[type=text] { background:#111214; color:#f4f4f2; border:1px solid #3a3e45; border-radius:8px; padding:10px; min-width:180px; }
.metrics { display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:10px; margin-top:14px; }
.metric { background:#121316; border-radius:9px; padding:12px; }
.metric b { display:block; font-size:21px; margin-top:3px; }
.muted { color:#a6a9b0; font-size:13px; }
pre { white-space:pre-wrap; overflow-wrap:anywhere; background:#0d0e10; border-radius:9px; padding:12px; max-height:360px; overflow:auto; }
#status.good { color:#9ee6b1; }
#status.bad { color:#ffb3b3; }
</style>
</head>
<body><main>
<header><div><h1>RAMBLA Reel Director</h1><div class="muted">Offline plan review and approval panel</div></div><div id="applyBadge" class="badge">APPLY FROZEN</div></header>
<section class="card">
  <div class="row">
    <label class="file-label" for="planFile">Load Edit Plan</label>
    <input id="planFile" type="file" accept="application/json,.json">
    <button id="reviewButton" class="secondary" disabled>Review</button>
  </div>
  <div id="filename" class="muted" style="margin-top:10px">No plan loaded.</div>
  <div class="metrics" id="metrics" hidden>
    <div class="metric"><span class="muted">Beats</span><b id="beats">—</b></div>
    <div class="metric"><span class="muted">Coverage slots</span><b id="slots">—</b></div>
    <div class="metric"><span class="muted">Selected</span><b id="selected">—</b></div>
    <div class="metric"><span class="muted">Needs review</span><b id="needsReview">—</b></div>
  </div>
</section>
<section class="card">
  <div class="row">
    <input id="actor" type="text" value="editor" aria-label="Approval actor">
    <button id="approveButton" disabled>Approve frozen plan</button>
    <button id="applyButton" disabled>Apply to Resolve</button>
  </div>
  <p class="muted">Approval freezes the current content hash. Apply is disabled unless the backend transport is explicitly enabled and the hash still matches.</p>
  <div id="status" class="muted">Ready. No Resolve connection has been made.</div>
</section>
<section class="card"><div class="muted">Evidence / API output</div><pre id="output">{}</pre></section>
<script>
let plan = null;
let approval = null;
let backendApplyEnabled = false;
const output = document.getElementById('output');
const statusNode = document.getElementById('status');

async function request(path, body) {
  const response = await fetch(path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? {} : {'Content-Type': 'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || JSON.stringify(data));
  return data;
}
function show(data) { output.textContent = JSON.stringify(data, null, 2); }
function setStatus(text, good=true) { statusNode.textContent=text; statusNode.className=good?'good':'bad'; }
async function refreshBackendState() {
  try {
    const state = await request('/v1/panel/status');
    backendApplyEnabled = !!state.apply_enabled;
    document.getElementById('applyBadge').textContent = backendApplyEnabled ? 'APPLY ENABLED' : 'APPLY FROZEN';
    document.getElementById('applyButton').disabled = !(backendApplyEnabled && approval && plan);
  } catch (_) { backendApplyEnabled = false; }
}
document.getElementById('planFile').addEventListener('change', async (event) => {
  const file = event.target.files[0]; if (!file) return;
  try {
    plan = JSON.parse(await file.text()); approval = null;
    document.getElementById('filename').textContent = file.name;
    document.getElementById('reviewButton').disabled = false;
    document.getElementById('approveButton').disabled = true;
    document.getElementById('applyButton').disabled = true;
    setStatus('Plan loaded locally. Review has not contacted Resolve.');
  } catch (error) { plan=null; setStatus('Invalid JSON: '+error, false); }
});
document.getElementById('reviewButton').addEventListener('click', async () => {
  try {
    const review = await request('/v1/panel/review', {plan}); show(review);
    document.getElementById('metrics').hidden = false;
    beats.textContent=review.beat_count; slots.textContent=review.coverage_slot_count;
    selected.textContent=review.selected_slot_count; needsReview.textContent=review.review_required_count;
    document.getElementById('approveButton').disabled=false;
    setStatus('Review complete offline. Resolve calls: '+review.resolve_calls+'.');
  } catch(error) { setStatus(String(error), false); }
});
document.getElementById('approveButton').addEventListener('click', async () => {
  try {
    approval = await request('/v1/panel/approve', {plan, actor: document.getElementById('actor').value});
    show(approval); setStatus('Plan approved and hash frozen.');
    document.getElementById('applyButton').disabled = !(backendApplyEnabled && approval && plan);
  } catch(error) { setStatus(String(error), false); }
});
document.getElementById('applyButton').addEventListener('click', async () => {
  try { const result=await request('/v1/panel/apply',{plan,approval}); show(result); setStatus('Apply completed.'); }
  catch(error) { setStatus(String(error), false); }
});
refreshBackendState();
</script>
</main></body></html>"""


def _default_panel_service() -> PanelService:
    root = Path(os.environ.get("RAMBLA_PANEL_DATA_ROOT", "work/panel")) / "approvals"
    return PanelService(
        transport=FrozenApplyTransport(),
        approval_root=root,
        apply_enabled=False,
    )


def create_app(*, panel_service: PanelService | None = None) -> FastAPI:
    app = FastAPI(title="RAMBLA Reel Director", version="0.2.0")
    service = panel_service or _default_panel_service()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def panel_page() -> str:
        return _PAGE

    @app.get("/v1/panel/status")
    def panel_status() -> dict[str, Any]:
        return {
            "apply_enabled": service.apply_enabled,
            "apply_state": "ENABLED" if service.apply_enabled else "FROZEN",
            "resolve_calls": 0,
        }

    @app.post("/v1/panel/review")
    def panel_review(request: ReviewRequest) -> dict[str, Any]:
        try:
            return service.review(request.plan)
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/v1/panel/approve")
    def panel_approve(request: ApproveRequest) -> dict[str, Any]:
        try:
            return service.approve(request.plan, actor=request.actor)
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/v1/panel/apply")
    def panel_apply(request: ApplyRequest) -> dict[str, Any]:
        try:
            return service.apply(request.plan, request.approval)
        except ApplyFrozenError as exc:
            raise HTTPException(status_code=423, detail=str(exc)) from exc
        except (KeyError, TypeError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return app


app = create_app()
