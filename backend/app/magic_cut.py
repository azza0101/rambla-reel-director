"""MAGICO uses an isolated project and the existing manual CUT engine."""
from pathlib import Path
import asyncio
import json
import shutil
from .atomic_io import write_json
from .cut_pass_routes import CutReview
from .magic_services import MagicWaitingInput


class MagicCutAdapter:
    def __init__(self, projects, root, magic_store, engine):
        self.projects, self.root, self.store, self.engine = projects, Path(root), magic_store, engine

    def _workspace(self, context):
        journal = self.store._path(context.run_id).with_name('cut-workspace.json')
        if journal.is_file():
            return journal, json.loads(journal.read_text(encoding='utf-8'))
        source = self.projects.load(context.source_project_id)
        origin_path = self.root / source.project_id / 'cut-origin.json'
        origin = json.loads(origin_path.read_text(encoding='utf-8')) if origin_path.is_file() else None
        bridge = self.root / source.project_id / 'resolve-bridge.json'
        if bridge.is_file() and not origin:
            raise MagicWaitingInput('CUT da Resolve: acquisizione delle clip originali necessaria prima del montaggio automatico')
        if source.source_video is None:
            raise MagicWaitingInput('Carica un video con audio per avviare MAGICO')
        from .workspace_backup import backup_project_state
        backup_project_state(self.root / source.project_id, self.root.parent / 'backups')
        # Registering an existing source is read-only: no extra long-video copy.
        source_path = Path(origin['source_path']) if origin else Path(source.source_video.path)
        if origin and origin.get('source_identity'):
            stat = source_path.stat()
            if origin['source_identity'] != {'size':stat.st_size, 'mtime_ns':stat.st_mtime_ns}:
                raise ValueError('La sorgente originale del CUT è cambiata')
        work = self.projects.create(source.name + ' · MAGICO sorgente')
        state = dict(work_project_id=work.project_id, initialized=False, steps={},
                     source_path=str(source_path), inherited_origin=origin)
        write_json(journal, state)
        return journal, state

    def _initialize(self, context, journal, state):
        if state['initialized']:
            return
        source = self.projects.load(context.source_project_id)
        origin = state.get('inherited_origin')
        work = self.projects.register_local_video(state['work_project_id'], Path(state['source_path']))
        folder = self.root / work.project_id / 'cut'
        folder.mkdir(parents=True, exist_ok=True)
        cache_pid = str(origin.get('project_id') or '') if origin else source.project_id
        # Only a project identifier can choose an inherited cache directory.
        if cache_pid and all(c.isalnum() or c in '_-' for c in cache_pid):
            inherited = self.root / cache_pid / 'cut'
            cache_source = self.projects.load(cache_pid)
            signature = inherited / 'source-signature.json'
            if signature.is_file() and json.loads(signature.read_text(encoding='utf-8')).get('signature') == cache_source.analysis_signature:
                for path in inherited.rglob('*.json'):
                    relative = path.relative_to(inherited)
                    if path.name == 'job.json' or path.name.startswith('plan'):
                        continue
                    target = folder / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
                for name in ('source-signature.json', 'suggestions-signature.json', 'alignment-signature.json'):
                    if (folder/name).is_file():
                        write_json(folder/name, {'signature':work.analysis_signature})
        if origin and (folder / 'transcript-original.json').is_file():
            plan = {**origin['plan'], 'source_signature':work.analysis_signature, 'status':'draft'}
            plan.pop('clean_project_id', None)
            write_json(folder / 'plan.json', plan)
            state['steps']['analyze'] = {'revision':plan['revision'], 'reused_confirmed_cut':True}
        state['initialized'] = True
        write_json(journal, state)

    async def run(self, context, options, report):
        journal, state = await asyncio.to_thread(self._workspace, context)
        await asyncio.to_thread(self._initialize, context, journal, state)
        pid = state['work_project_id']
        for index, action in enumerate(('analyze', 'boundaries', 'review', 'confirm')):
            if action in state['steps']:
                report((index+1)*4, 16, 'CUT · risultato già salvato')
                continue
            request = None
            if action in {'review', 'confirm'}:
                _, _, plan = self.engine.current(pid)
                request = CutReview(revision=plan['revision'])
                if action == 'review':
                    request.tight_pauses = True
                    request.pause_mode = options.pause_mode
                    request.end_margin_ms = options.end_margin_ms
            result = await self.engine.perform(action, pid, request=request,
                report=lambda done,total,message,index=index:report(index*4+done,16,message))
            state['steps'][action] = result
            write_json(journal, state)
            report((index+1)*4, 16, f'CUT · {action} completato')
        _, _, plan = self.engine.current(pid)
        return dict(output_project_id=state['steps']['confirm']['project_id'],
                    cut_revision=plan['revision'], work_project_id=pid,
                    warnings=plan.get('warnings', []))
