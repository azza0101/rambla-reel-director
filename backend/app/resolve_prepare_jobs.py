"""Observable, cancellable Resolve preparation jobs."""
import asyncio
import json
import threading
import time
import uuid
from pathlib import Path


class _CacheTracker:
    def __init__(self):
        self.files = {}
        self.envato = []

    def file(self, value):
        path = Path(value)
        self.files.setdefault(path, path.exists() or path.is_symlink())

    def envato_scope(self, directory, registry, asset_id):
        directory, registry = Path(directory), Path(registry)
        if directory.is_symlink(): return
        before = {p for p in directory.rglob('*') if p.is_file() and not p.is_symlink()} if directory.is_dir() else set()
        try: existing = json.loads(registry.read_text(encoding='utf8')).get('assets', {})
        except (OSError, ValueError, TypeError): existing = {}
        self.envato.append((directory, registry, asset_id, before, existing.get(asset_id)))

    def discard_new(self):
        failures = []
        for path, existed in self.files.items():
            if not existed:
                try:
                    if path.is_file() and not path.is_symlink(): path.unlink()
                except OSError: failures.append(path.name)
        for directory, registry, asset_id, before, previous in self.envato:
            if directory.is_symlink(): continue
            if directory.is_dir():
                for path in directory.rglob('*'):
                    try:
                        if path not in before and path.is_file() and not path.is_symlink():
                            path.resolve().relative_to(directory.resolve())
                            path.unlink()
                    except (OSError, ValueError): failures.append(path.name)
            try:
                payload=json.loads(registry.read_text(encoding='utf8'))
                row=payload.get('assets',{}).get(asset_id) or {}
                candidate=Path(str(row.get('media_path') or ''))
                if row and candidate.resolve().is_relative_to(directory.resolve()):
                    if previous is None: payload['assets'].pop(asset_id, None)
                    else: payload['assets'][asset_id]=previous
                    from .atomic_io import write_json
                    write_json(registry,payload)
            except (OSError, ValueError, TypeError): pass
        return failures


class ResolvePrepareJobs:
    def __init__(self):
        self.jobs = {}
        self.tasks = {}
        self.cancellation = {}

    def start(self, project_id, runner):
        for row in self.jobs.values():
            if row['project_id'] == project_id and row['status'] in {'preparing','waiting_user','cancelling'}:
                return self.status(row['job_id'])
        job_id = uuid.uuid4().hex
        row = dict(job_id=job_id, project_id=project_id, status='preparing', percent=0,
                   message='Controllo selezioni', started=time.monotonic())
        self.jobs[job_id] = row
        event, tracker = threading.Event(), _CacheTracker()
        self.cancellation[job_id] = {'event':event, 'tracker':tracker, 'keep':True}
        def report(percent, message):
            if row['status'] == 'preparing': row.update(percent=percent, message=message)
        report.media = lambda media: row.update(media=media) if row['status']=='preparing' else None
        report.cancel_event = event
        report.track_cache_file = tracker.file
        report.track_envato_cache = tracker.envato_scope
        async def issue_prompt(issue):
            if self.cancellation[job_id].get('ignore_future'): return 'ignore'
            future=asyncio.get_running_loop().create_future()
            self.cancellation[job_id]['decision']=future
            row.update(status='waiting_user', issue=dict(issue), message='Scelta richiesta per una copertura')
            try: return await future
            finally:
                self.cancellation[job_id].pop('decision',None)
                row.pop('issue',None)
                if row['status']=='waiting_user': row['status']='preparing'
        report.issue = issue_prompt
        async def run():
            try:
                result = await asyncio.wait_for(runner(report), timeout=3600)
                row.update(status='ready', percent=90, message='Pacchetto pronto · attendo ricezione del bridge', package=result)
            except asyncio.CancelledError:
                failures=[] if self.cancellation[job_id]['keep'] else tracker.discard_new()
                message='Invio interrotto · file scaricati conservati' if self.cancellation[job_id]['keep'] else 'Invio interrotto · nuovi file rimossi'
                if failures: message+=' · alcuni file non sono stati rimossi'
                row.update(status='cancelled', message=message)
            except Exception as exc:
                row.update(status='failed', message=str(exc) or 'Preparazione scaduta dopo un’ora', error=str(exc))
            finally:
                row['media'] = None
                self.tasks.pop(job_id, None)
        self.tasks[job_id] = asyncio.create_task(run())
        return self.status(job_id)

    async def cancel(self, job_id, *, keep_cached=True):
        row=self.jobs[job_id]
        if row['status'] not in {'preparing','waiting_user','cancelling'}: return self.status(job_id)
        if row['status'] in {'preparing','waiting_user'}:
            row.update(status='cancelling',message='Interruzione in corso…')
            control=self.cancellation[job_id];control['keep']=bool(keep_cached);control['event'].set()
            task=self.tasks.get(job_id)
            if task:task.cancel()
        task=self.tasks.get(job_id)
        if task:
            try: await asyncio.shield(task)
            except asyncio.CancelledError: pass
        if row['status']=='cancelling':
            control=self.cancellation[job_id]
            failures=[] if control['keep'] else control['tracker'].discard_new()
            message='Invio interrotto · file scaricati conservati' if control['keep'] else 'Invio interrotto · nuovi file rimossi'
            if failures: message+=' · alcuni file non sono stati rimossi'
            row.update(status='cancelled',message=message,media=None)
            self.tasks.pop(job_id,None)
        return self.status(job_id)

    def decide(self, job_id, choice):
        row=self.jobs[job_id]
        if choice not in {'retry','ignore','ignore_all'}: raise ValueError('Scelta non valida')
        future=self.cancellation[job_id].get('decision')
        if row['status']!='waiting_user' or not future or future.done(): raise ValueError('Nessuna scelta in attesa')
        if choice == 'ignore_all': self.cancellation[job_id]['ignore_future']=True
        future.set_result('ignore' if choice == 'ignore_all' else choice)
        return self.status(job_id)

    def status(self, job_id):
        row = self.jobs[job_id]
        return {k:v for k,v in row.items() if k != 'started'} | {'elapsed_seconds': int(time.monotonic()-row['started'])}
