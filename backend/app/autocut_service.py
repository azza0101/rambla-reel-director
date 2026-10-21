"""Isolated, session-authenticated Auto-Cut worker; no bridge, social or editorial routes."""
from dataclasses import asdict
from pathlib import Path
import asyncio
import hashlib
import json
import os
import secrets
import sys
from subprocess import SubprocessError

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .atomic_io import write_json
from .curation_project import ProjectStore
from .cut_pass_routes import install_cut_routes


class SourceRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    path: str
    project_name: str = Field(min_length=1,max_length=200)
    timeline_id: str = Field(min_length=1,max_length=200)
    timeline_name: str = Field(min_length=1,max_length=200)


class ApplyRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: str = Field(min_length=1,max_length=100)


def create_app(data_root: Path, *, token: str, probe_runner=None, enable_automatic_diagnostics=False) -> FastAPI:
    if len(token)<16: raise ValueError('Auto-Cut requires a private session token')
    data_root=Path(data_root).resolve();root=data_root/'projects';root.mkdir(parents=True,exist_ok=True)
    if probe_runner is None:
        from .debug_server import _probe_source_video
        probe_runner=_probe_source_video
    store=ProjectStore(root,probe_runner=probe_runner)
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    app.state.autocut_apply_jobs={};tasks=set()
    from .diagnostics_routes import install_diagnostics_routes
    reporter=install_diagnostics_routes(app,data_root/'diagnostics',app_root=Path(__file__).resolve().parents[2])
    if reporter and enable_automatic_diagnostics and not reporter.settings()['choice_made']:
        reporter.set_automatic(True,start_worker=False)

    @app.middleware('http')
    async def authenticate(request:Request,call_next):
        if not secrets.compare_digest(request.headers.get('X-Autocut-Session',''),token):
            return JSONResponse({'detail':'Private Auto-Cut session required'},status_code=403)
        if request.method!='GET' and any(j['status']=='running' for j in app.state.autocut_apply_jobs.values()):
            return JSONResponse({'detail':'Attendi applicazione CUT in corso'},status_code=409)
        return await call_next(request)

    def load_project(pid):
        try:return store.load(pid)
        except (ValueError,FileNotFoundError):raise HTTPException(404,'Progetto Auto-Cut non trovato')

    @app.get('/autocut/health')
    async def health():
        from .release_version import RELEASE_VERSION
        return {'service':'rmbl-autocut','version':RELEASE_VERSION,'pid':os.getpid()}

    @app.get('/autocut/busy')
    async def busy():return {'busy':any(j.get('status')=='running' for j in app.state.cut_jobs.values()) or any(j['status']=='running' for j in app.state.autocut_apply_jobs.values())}

    @app.post('/autocut/shutdown')
    async def shutdown():
        if (await busy())['busy']:raise HTTPException(409,'Auto-Cut sta lavorando')
        server=getattr(app.state,'server',None)
        if server:server.should_exit=True
        return {'status':'stopping'}

    @app.get('/autocut',response_class=HTMLResponse)
    async def page():
        from .autocut_ui import render_autocut
        return HTMLResponse(render_autocut(),headers={'Cache-Control':'no-store'})

    @app.post('/autocut/source')
    async def source(request:SourceRequest):
        path=Path(request.path).resolve()
        if not path.is_file():raise HTTPException(422,'Video originale non disponibile su questo computer')
        stat=path.stat()
        key=hashlib.sha256(f'{request.project_name}|{request.timeline_id}|{path}|{stat.st_size}|{stat.st_mtime_ns}'.encode()).hexdigest()
        index_path=data_root/'sources.json'
        index=json.loads(index_path.read_text('utf-8')) if index_path.is_file() else {}
        if key in index:
            project=load_project(index[key])
        else:
            project=store.create(request.timeline_name)
            try:project=await asyncio.to_thread(store.register_local_video,project.project_id,path)
            except (ValueError,OSError,KeyError,SubprocessError) as exc:raise HTTPException(422,'Sorgente non leggibile: '+str(exc)) from exc
            if not project.source_video.has_audio:raise HTTPException(422,'La sorgente non contiene audio')
            index[key]=project.project_id;write_json(index_path,index)
            write_json(root/project.project_id/'resolve-context.json',request.model_dump())
        write_json(data_root/'last-session.json',{'project_id':project.project_id})
        return asdict(project)

    @app.get('/autocut/session')
    async def session():
        saved=data_root/'last-session.json'
        status=data_root/'update-status.json'
        if not saved.is_file():return {'update':json.loads(status.read_text('utf-8')) if status.is_file() else None}
        project=load_project(json.loads(saved.read_text('utf-8'))['project_id'])
        context=json.loads((root/project.project_id/'resolve-context.json').read_text('utf-8'))
        status=data_root/'update-status.json'
        return {'project':asdict(project),'context':context,'update':json.loads(status.read_text('utf-8')) if status.is_file() else None}

    @app.get('/api/curation/projects/{pid}')
    async def project(pid:str):return asdict(load_project(pid))

    @app.get('/api/curation/projects/{pid}/media/source-video/source')
    async def original(pid:str):
        project=load_project(pid)
        if not project.source_video:raise HTTPException(404,'Video non disponibile')
        return FileResponse(project.source_video.path)

    install_cut_routes(app,store,root,load_project,lambda _:None)
    # This product has no confirm-child/editorial workflow: Apply uses the current reviewed map.
    app.router.routes[:]=[route for route in app.router.routes if not getattr(route,'path','').endswith('/cut/confirm')]

    def native_payload(pid,revision):
        load_project(pid)
        if app.state.cut_jobs.get(pid,{}).get('status')=='running':raise HTTPException(409,'Attendi la fine del CUT')
        file=root/pid/'cut'/'plan.json'
        if not file.is_file():raise HTTPException(409,'Avvia prima Auto-Cut')
        plan=json.loads(file.read_text('utf-8'))
        if plan['revision']!=revision:raise HTTPException(409,'CUT modificato: ricarica la revisione corrente')
        from .native_cut_export import load_native_cut
        try:cut=load_native_cut(root/pid,root)
        except (ValueError,OSError,SubprocessError) as exc:raise HTTPException(409,str(exc)) from exc
        if cut.get('revision')!=revision:raise HTTPException(409,'CUT cambiato durante la preparazione: riprova dalla revisione aggiornata')
        return {'native_cut':cut,'context':json.loads((root/pid/'resolve-context.json').read_text('utf-8'))}

    @app.get('/autocut/projects/{pid}/native-cut')
    async def native(pid:str,revision:str):return await asyncio.to_thread(native_payload,pid,revision)

    @app.post('/autocut/projects/{pid}/apply')
    async def apply(pid:str,request:ApplyRequest):
        if any(j['status']=='running' for j in app.state.autocut_apply_jobs.values()):raise HTTPException(409,'Applicazione già in corso')
        payload=await asyncio.to_thread(native_payload,pid,request.revision)
        if any(j['status']=='running' for j in app.state.autocut_apply_jobs.values()):raise HTTPException(409,'Applicazione già in corso')
        if json.loads((root/pid/'cut'/'plan.json').read_text('utf-8'))['revision']!=request.revision:raise HTTPException(409,'CUT modificato durante la preparazione')
        previous=app.state.autocut_apply_jobs.get(pid,{})
        if previous.get('revision')==request.revision and previous.get('status')=='succeeded':return previous
        job={'status':'running','revision':request.revision,'message':'Creo timeline CUT nativa…','progress':0}
        app.state.autocut_apply_jobs[pid]=job
        async def run():
            try:
                process=await asyncio.create_subprocess_exec(sys.executable,'-m','backend.app.autocut_apply',stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
                process.stdin.write(json.dumps(payload).encode());await process.stdin.drain();process.stdin.close()
                reported_error=None
                async for raw in process.stdout:
                    try:row=json.loads(raw)
                    except (ValueError,TypeError):continue
                    if row.get('type')=='progress':job.update(message=row['message'],progress=row['percent'])
                    elif row.get('type')=='result':job.update(result=row['result'])
                    elif row.get('type')=='error':reported_error=row['message']
                code=await process.wait()
                if reported_error:raise RuntimeError(reported_error)
                if code or 'result' not in job:raise RuntimeError('Applicazione interrotta: apri Diagnostica CUT')
                job.update(status='succeeded',progress=100,message='CUT applicato · timeline originale conservata')
            except Exception as exc:
                if reporter:reporter.capture_exception(exc,component='cut',phase='apply')
                job.update(status='failed',message=str(exc))
            write_json(root/pid/'last-apply.json',job)
        task=asyncio.create_task(run());tasks.add(task);task.add_done_callback(tasks.discard)
        return dict(job)

    @app.get('/autocut/projects/{pid}/apply')
    async def apply_status(pid:str):
        load_project(pid)
        return app.state.autocut_apply_jobs.get(pid,{'status':'idle'})
    return app


def main():
    import argparse
    import uvicorn
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,required=True);parser.add_argument('--data-root',type=Path,required=True)
    args=parser.parse_args()
    from .project_config import load_project_credentials
    load_project_credentials(Path(__file__).resolve().parents[2])
    app=create_app(args.data_root,token=os.environ.get('RMBL_AUTOCUT_SESSION',''),enable_automatic_diagnostics=True)
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=args.port,access_log=False))
    app.state.server=server
    server.run()

if __name__=='__main__':main()
