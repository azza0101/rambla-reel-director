"""MAGICO API, installed with explicit services rather than HTTP loopbacks."""
from fastapi import HTTPException
from .magic_models import MagicOptions


def install_magic_routes(app, runner, load_project):
    app.state.magic_runner = runner

    def checked(operation, *args):
        try:
            return operation(*args)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post('/api/curation/projects/{pid}/magic')
    async def start_magic(pid: str, options: MagicOptions | None = None):
        load_project(pid)
        return checked(runner.start, pid, options or MagicOptions())

    @app.get('/api/curation/projects/{pid}/magic/latest')
    async def latest_magic(pid: str):
        load_project(pid)
        row = runner.store.latest(pid)
        return runner.status(row['run_id']) if row else {}

    @app.get('/api/curation/magic/{run_id}')
    async def magic_status(run_id: str):
        return checked(runner.status, run_id)

    @app.post('/api/curation/magic/{run_id}/cancel')
    async def cancel_magic(run_id: str):
        return checked(runner.cancel, run_id)

    @app.post('/api/curation/magic/{run_id}/resume')
    async def resume_magic(run_id: str):
        return checked(runner.resume, run_id)
