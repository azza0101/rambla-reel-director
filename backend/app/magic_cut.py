"""MAGICO uses an isolated project and the existing manual CUT engine."""
from pathlib import Path
import asyncio
import json
import shutil
import subprocess
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
        bridge_data = json.loads(bridge.read_text(encoding='utf-8')) if bridge.is_file() else {}
        snapshot = bridge_data.get('cut_source') or (origin or {}).get('resolve_source')
        if bridge.is_file() and not origin:
            if not snapshot or not snapshot.get('supported'):
                issues = ' · '.join((snapshot or {}).get('issues', []))
                raise MagicWaitingInput('CUT da Resolve: usa RICALCOLA AUDIO per acquisire le clip originali. '+issues)
            from .resolve_cut_source import verify_snapshot_files
            verify_snapshot_files(snapshot)
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
                     source_path=str(source_path), inherited_origin=origin, resolve_source=snapshot,
                     guide_path=source.guide_audio.path if getattr(source,'guide_audio',None) else None)
        write_json(journal, state)
        return journal, state

    def _initialize(self, context, journal, state):
        if state['initialized']:
            return
        source = self.projects.load(context.source_project_id)
        origin = state.get('inherited_origin')
        if state.get('resolve_source') and not origin:
            from .resolve_cut_source import verify_snapshot_files, frame_rate
            from dataclasses import replace
            snapshot = state['resolve_source']
            verify_snapshot_files(snapshot)
            if not state.get('guide_path'):
                raise ValueError('Guida audio Resolve non disponibile: ricalcola audio')
            rate = frame_rate(snapshot['fps'])
            frames = snapshot['mark_out']-snapshot['mark_in']
            guide = self.root/state['work_project_id']/'source'/'resolve-guide.mp4'
            guide.parent.mkdir(parents=True,exist_ok=True)
            if not guide.is_file():
                subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'color=c=black:s=360x640:r={rate}',
                    '-i',state['guide_path'],'-frames:v',str(frames),'-c:v','libx264','-preset','veryfast',
                    '-c:a','aac','-shortest',str(guide)],check=True,capture_output=True,timeout=300)
            state['source_path'] = str(guide)
            work = self.projects.register_local_video(state['work_project_id'], guide)
            work = replace(work,source_video=replace(work.source_video,fps=float(rate),duration=frames/float(rate)))
            self.projects._save(work)
        else:
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
                inherited_source = getattr(cache_source,'source_video',None)
                if inherited_source and Path(inherited_source.path).resolve() == Path(state['source_path']).resolve():
                    from .resolve_cut_source import file_identity
                    write_json(folder/'alignment-cache-source.json',dict(signature=cache_source.analysis_signature,
                        path=str(Path(state['source_path']).resolve()),identity=file_identity(state['source_path'])))
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
            if action == 'boundaries' and state.get('inherited_origin'):
                _, _, existing = self.engine.current(pid)
                groups = existing.get('groups') or []
                if groups and all(group.get('boundaries_reviewed') is True for group in groups):
                    state['steps'][action] = {'reused_confirmed_boundaries':True}
                    write_json(journal, state)
                    report((index+1)*4,16,'CUT · confini delle take già verificati')
                    continue
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
        # Responses are addressed by the exact prompt, schema and model options.
        # Copying them does not reuse replies for different text or selections.
        inherited_cache = self.root/context.source_project_id/'run'/'magic-editorial-cache'/'api-cache'
        child_cache = self.root/state['steps']['confirm']['project_id']/'run'/'magic-editorial-cache'/'api-cache'
        if inherited_cache.is_dir():
            child_cache.mkdir(parents=True,exist_ok=True)
            for cached in inherited_cache.glob('*.json'):
                target = child_cache/cached.name
                if not target.exists():
                    shutil.copy2(cached,target)
        if state.get('resolve_source'):
            child = self.root/state['steps']['confirm']['project_id']/'cut-origin.json'
            provenance = json.loads(child.read_text(encoding='utf-8'))
            provenance['resolve_source'] = state['resolve_source']
            write_json(child,provenance)
        return dict(output_project_id=state['steps']['confirm']['project_id'],
                    cut_revision=plan['revision'], work_project_id=pid,
                    warnings=plan.get('warnings', []))
