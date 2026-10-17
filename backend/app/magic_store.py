"""Atomic MAGICO runs, phase checkpoints and a durable provider-call journal."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import threading
import uuid
from copy import deepcopy

from .atomic_io import write_json
from .magic_models import MagicOptions
from .magic_services import MagicBudgetReached


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class MagicStore:
    def __init__(self, projects_root):
        self.root = Path(projects_root)
        self.lock = threading.RLock()

    @staticmethod
    def _id(value):
        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', value):
            raise ValueError('Identificativo MAGICO non valido')
        return value

    def _path(self, run_id):
        run_id = self._id(run_id)
        paths = list(self.root.glob(f'*/magic/{run_id}/run.json'))
        if len(paths) != 1:
            raise ValueError('Run MAGICO non trovato')
        return paths[0]

    def read(self, run_id):
        with self.lock:
            return json.loads(self._path(run_id).read_text(encoding='utf-8'))

    def latest(self, project_id):
        paths = (self.root / self._id(project_id) / 'magic').glob('*/run.json')
        rows = [json.loads(p.read_text(encoding='utf-8')) for p in paths]
        return max(rows, key=lambda row: row['created_at'], default=None)

    def create_or_resume(self, project_id, signature, options):
        options = MagicOptions.model_validate(options).model_dump()
        with self.lock:
            old = self.latest(project_id)
            if old and old['source_signature'] == signature and old['options'] == options and old['status'] != 'cancelled':
                return old
            if old and old['status'] in {'queued', 'running', 'waiting_input'}:
                raise ValueError('Un run MAGICO è già aperto: annullalo prima di cambiare sorgente o opzioni')
            run_id = uuid.uuid4().hex
            now = datetime.now(timezone.utc).isoformat()
            row = dict(run_id=run_id, source_project_id=self._id(project_id), output_project_id=None,
                       source_signature=signature, options=options, status='queued', created_at=now,
                       updated_at=now, phase='queued', completed=0, total=0, percent=0,
                       message='MAGICO pronto a partire', checkpoints={}, calls={}, warnings=[], cancel_requested=False)
            path = self.root / project_id / 'magic' / run_id / 'run.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            write_json(path, row)
            return deepcopy(row)

    def latest_for_view(self, project_id):
        own = self.latest(project_id)
        if own:
            return own
        pointer = self.root/self._id(project_id)/'magic-parent-run.json'
        if not pointer.is_file():
            return None
        row = self.read(json.loads(pointer.read_text(encoding='utf-8'))['run_id'])
        return row if row.get('output_project_id') == project_id else None

    def transition(self, run_id, **changes):
        with self.lock:
            row = self.read(run_id)
            row.update(changes, updated_at=datetime.now(timezone.utc).isoformat())
            write_json(self._path(run_id), row)
            if row.get('output_project_id'):
                pointer = self.root/self._id(row['output_project_id'])/'magic-parent-run.json'
                pointer.parent.mkdir(parents=True,exist_ok=True)
                write_json(pointer,{'run_id':run_id})
            return deepcopy(row)

    def validate_source(self, run_id, signature):
        if self.read(run_id)['source_signature'] != signature:
            raise ValueError('La sorgente è cambiata: non posso pubblicare il vecchio run MAGICO')

    def checkpoint(self, run_id, phase, result, input_signature):
        with self.lock:
            row = self.read(run_id)
            row['checkpoints'][phase] = dict(result=result, input_signature=input_signature)
            return self.transition(run_id, checkpoints=row['checkpoints'])

    def begin_call(self, run_id, phase, provider, input_signature, *, visual=False):
        with self.lock:
            row = self.read(run_id)
            for call in row['calls'].values():
                if call['input_signature'] == input_signature and call['provider'] == provider and call['status'] in {'started', 'unknown'}:
                    raise ValueError('Esito della chiamata precedente incerto: verifica prima di riprovare')
            cloud = provider != 'local'
            calls = [c for c in row['calls'].values() if c['cloud']]
            if cloud and (len(calls) >= row['options']['max_cloud_requests'] or
                          (visual and sum(c['visual'] for c in calls) >= row['options']['max_visual_requests'])):
                raise MagicBudgetReached('Raggiunto il budget AI di MAGICO')
            call_id = uuid.uuid4().hex
            row['calls'][call_id] = dict(phase=phase, provider=provider, input_signature=input_signature,
                visual=visual, cloud=cloud, status='started', started_at=datetime.now(timezone.utc).isoformat())
            self.transition(run_id, calls=row['calls'])
            return call_id

    def finish_call(self, run_id, call_id, *, result=None, error=None):
        with self.lock:
            row = self.read(run_id)
            row['calls'][call_id].update(status='failed' if error else 'completed', result=result, error=error)
            self.transition(run_id, calls=row['calls'])

    def recover(self, run_id):
        with self.lock:
            row = self.read(run_id)
            unknown = False
            for call in row['calls'].values():
                if call['status'] in {'started', 'unknown'}:
                    call['status'] = 'unknown'
                    unknown = True
            return self.transition(run_id, calls=row['calls'],
                status='waiting_input' if unknown else row['status'],
                message='Esito AI incerto dopo interruzione: nessuna richiesta ripetuta' if unknown else row['message'])
