"""Observable preparation jobs; no Resolve timeline mutations."""
import asyncio
import time
import uuid


class ResolvePrepareJobs:
    def __init__(self):
        self.jobs = {}
        self.tasks = {}

    def start(self, project_id, runner):
        for row in self.jobs.values():
            if row['project_id'] == project_id and row['status'] == 'preparing':
                return self.status(row['job_id'])
        job_id = uuid.uuid4().hex
        row = dict(job_id=job_id, project_id=project_id, status='preparing', percent=0,
                   message='Controllo selezioni', started=time.monotonic())
        self.jobs[job_id] = row
        def report(percent, message):
            row.update(percent=percent, message=message)
        report.media = lambda media: row.update(media=media)
        async def run():
            try:
                result = await asyncio.wait_for(runner(report), timeout=600)
                row.update(status='ready', percent=90, message='Pacchetto pronto · attendo ricezione del bridge', package=result)
            except Exception as exc:
                row.update(status='failed', message=str(exc) or 'Preparazione scaduta dopo 10 minuti', error=str(exc))
            finally:
                row['media'] = None
                self.tasks.pop(job_id, None)
        self.tasks[job_id] = asyncio.create_task(run())
        return self.status(job_id)

    def status(self, job_id):
        row = self.jobs[job_id]
        return {k:v for k,v in row.items() if k != 'started'} | {'elapsed_seconds': int(time.monotonic()-row['started'])}
