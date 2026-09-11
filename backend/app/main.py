from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict

from .resolve_live import LiveResolveService


class ApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str


_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>RAMBLA Live Resolve</title></head>
<body><h1>RAMBLA Live Resolve</h1>
<button onclick="run('probe')">Probe Resolve</button>
<button onclick="run('dry-run')">Dry Run PUNCH_IN</button>
<button onclick="applyPlan()">Apply to Duplicate</button>
<pre id="output">Ready.</pre>
<script>
let planId = null;
async function request(path, options={}) {
  const response = await fetch(path, options);
  const body = await response.json();
  if (!response.ok) throw new Error(JSON.stringify(body));
  return body;
}
async function run(action) {
  try {
    const body = await request('/v1/resolve/' + action, {method: 'POST'});
    if (body.plan) planId = body.plan.id;
    output.textContent = JSON.stringify(body, null, 2);
  } catch (error) { output.textContent = String(error); }
}
async function applyPlan() {
  if (!planId) { output.textContent = 'Run Dry Run PUNCH_IN first.'; return; }
  try {
    const body = await request('/v1/resolve/apply', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({plan_id: planId})
    });
    output.textContent = JSON.stringify(body, null, 2);
  } catch (error) { output.textContent = String(error); }
}
</script></body></html>"""


def create_app() -> FastAPI:
    app = FastAPI(title="RAMBLA Reel Director", version="0.1.0")
    live_service: LiveResolveService | None = None

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def live_page() -> str:
        return _PAGE

    def service() -> LiveResolveService:
        nonlocal live_service
        try:
            if live_service is None:
                live_service = LiveResolveService()
            return live_service
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/v1/resolve/probe")
    def resolve_probe() -> dict[str, object]:
        try:
            return service().probe()
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/v1/resolve/dry-run")
    def resolve_dry_run() -> dict[str, object]:
        try:
            return service().dry_run()
        except Exception as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/resolve/apply")
    def resolve_apply(request: ApplyRequest) -> dict[str, object]:
        try:
            return service().apply(request.plan_id)
        except Exception as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return app


app = create_app()
