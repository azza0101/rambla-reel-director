"""Local-only support controls; no caller-provided error text is accepted."""
from pathlib import Path
from fastapi import HTTPException, Request
from .diagnostics import Diagnostics


def install_diagnostics_routes(app, root, *, app_root):
    try:
        reporter=Diagnostics(Path(root),app_root=app_root)
    except OSError:
        reporter=None
    app.state.diagnostics=reporter
    if reporter:
        app.router.on_startup.append(reporter.start)
        app.router.on_shutdown.append(reporter.close)

    def available():
        if reporter is None:raise HTTPException(503,'Cartella diagnostica non scrivibile.')
        return reporter

    def local(request):
        if request.client.host not in {'127.0.0.1','::1','testclient'} or request.headers.get('X-RMBL-Diagnostics')!='1':
            raise HTTPException(403,'Local diagnostic request required')
        origin=request.headers.get('origin')
        if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
            raise HTTPException(403,'Origin mismatch')

    @app.get('/api/curation/diagnostics')
    async def status():
        return available().view()

    @app.post('/api/curation/diagnostics/settings')
    async def settings(request:Request):
        local(request)
        body=await request.json()
        if not isinstance(body,dict) or set(body)!={'automatic'} or type(body.get('automatic')) is not bool:
            raise HTTPException(422,'automatic must be a boolean')
        return available().set_automatic(body['automatic'])

    @app.post('/api/curation/diagnostics/send')
    async def send(request:Request):
        local(request)
        return available().submit_async()

    @app.post('/api/curation/diagnostics/login')
    async def login(request:Request):
        local(request)
        try:return available().login()
        except RuntimeError as exc:raise HTTPException(409,str(exc)) from exc

    previous=app.exception_handlers.get(Exception)
    async def error_handler(request:Request,exc:Exception):
        if reporter:reporter.capture_exception(exc,component='app')
        if previous:return await previous(request,exc)
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail':'Errore interno. Apri ASSISTENZA per la diagnostica.'},status_code=500)
    app.add_exception_handler(Exception,error_handler)
    return reporter
