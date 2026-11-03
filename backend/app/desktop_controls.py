"""Local desktop provider settings and safe process status for RMBL B ROLL."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

from . import debug_server as debug

PROVIDERS = {
    "groq": "GROQ_API_KEY",
    "pexels": "PEXELS_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "google": "GOOGLE_API_KEY",
}
ACTIVE = {"QUEUED", "RUNNING"}


class SecretUpdate(BaseModel):
    key: str = Field(min_length=8, max_length=512)


def _local_write(request: Request) -> None:
    if not request.client or request.client.host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(403, "Only local desktop settings are supported")
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Origin mismatch")
    if request.headers.get("X-RMBL-Settings") != "1":
        raise HTTPException(403, "Settings request header required")


def _variable(provider: str) -> str:
    if provider not in PROVIDERS:
        raise HTTPException(404, "Unknown provider")
    return PROVIDERS[provider]


def _env_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env.local"


def _save(provider: str, value: str | None) -> None:
    """Updates a single local setting without serializing secrets in responses."""
    var = _variable(provider)
    path = _env_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = path.read_text(encoding="utf-8-sig").splitlines() if path.is_file() else []
    rows = [row for row in rows if row.partition("=")[0].strip() != var]
    if value is not None:
        rows.append(f"{var}={value}")
    # Windows installed app lives beneath the current user's LocalAppData.
    # Use restrictive file permissions where supported; no credentials in logs.
    # Atomic replacement, with os.chmod as a best-effort extra restriction.
    import tempfile
    import os as _os
    handle, tmp = tempfile.mkstemp(prefix=".env-", dir=str(path.parent))
    try:
        with _os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write("\n".join(rows) + "\n")
        _os.replace(tmp, path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    finally:
        if _os.path.exists(tmp):
            _os.unlink(tmp)
    if value is None:
        os.environ.pop(var, None)
    else:
        os.environ[var] = value


async def _verify_groq(value: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=12.0, trust_env=False) as client:
            response = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {value}"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(503, "Impossibile contattare Groq: riprova quando sei online") from exc
    if response.status_code in {401, 403}:
        raise HTTPException(422, "Chiave Groq non valida o non autorizzata")
    if response.status_code != 200:
        raise HTTPException(503, f"Verifica Groq temporaneamente non disponibile (HTTP {response.status_code})")


def _resource_snapshot() -> dict[str, Any]:
    try:
        import psutil
        memory = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=None)
        return {
            "available": True, "cpu_percent": round(cpu, 1),
            "ram_percent": round(memory.percent, 1),
            "ram_used_gb": round(memory.used / 1024**3, 2),
            "ram_total_gb": round(memory.total / 1024**3, 2),
        }
    except (ImportError, OSError, RuntimeError):
        return {"available": False, "message": "Metriche CPU/RAM non disponibili"}


def install_desktop_controls(app, project_root: Path) -> None:
    from .runtime_mode import current_mode
    if current_mode() == "cloud":
        return

    @app.get("/api/curation/desktop-controls")
    async def desktop_controls(project_id: str = ""):
        # Only active jobs: a stale 'FAILED' journal must not appear running.
        running = []
        for run in debug.RUNS.values():
            if run.status not in ACTIVE:
                continue
            if project_id:
                expected = (project_root / project_id / "run").resolve()
                if Path(run.output_dir).resolve() != expected:
                    continue
            running.append(run.snapshot())
        running.sort(key=lambda row: row.get("run_id", ""))
        return {
            "running": running,
            "resources": _resource_snapshot(),
            "providers": {name: {"configured": bool(os.environ.get(var, "").strip())}
                          for name, var in PROVIDERS.items()},
        }

    @app.put("/api/curation/desktop-settings/{provider}")
    async def set_provider(provider: str, payload: SecretUpdate, request: Request):
        _local_write(request)
        _variable(provider)
        value = payload.key.strip()
        if not value or "\n" in value or "\r" in value or "=" in value or '"' in value:
            raise HTTPException(422, "Formato chiave non valido")
        if provider == "groq":
            await _verify_groq(value)
        _save(provider, value)
        return {"provider": provider, "configured": True,
                "verified": provider == "groq", "restart_required": False}

    @app.delete("/api/curation/desktop-settings/{provider}")
    async def delete_provider(provider: str, request: Request):
        _local_write(request)
        _save(provider, None)
        return {"provider": provider, "configured": False}

