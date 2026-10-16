"""Shared CUT analysis; called by both manual routes and MAGICO adapters."""
import json
import asyncio
from pathlib import Path
from .atomic_io import write_json
from .cut_pass import build_cut_plan, prepare_suggestions


def analyze_cut_project(project, folder, progress, *, transcribe, propose, choose, align):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    def read(path):
        return json.loads(path.read_text(encoding='utf-8'))
    p = project
    cached = folder / 'transcript-original.json'
    signature = folder / 'source-signature.json'
    progress(0, 'Trascrizione integrale con tempi per parola…')
    if cached.is_file() and signature.is_file() and read(signature).get('signature') == p.analysis_signature:
        raw = read(cached)
    else:
        raw = transcribe(Path(p.source_video.path), folder)
        write_json(cached, raw)
        write_json(signature, {'signature': p.analysis_signature})
    progress(1, 'Trascrizione pronta · riconosco ripartenze e take…')
    proposal_signature = folder / 'suggestions-signature.json'
    if proposal_signature.is_file() and (folder / 'suggestions.json').is_file() and read(proposal_signature).get('signature') == p.analysis_signature:
        suggestion = read(folder / 'suggestions.json')
        progress(1, 'Gruppi già riconosciuti · riprendo dalla verifica delle take')
    else:
        suggestion = propose(raw)
        if not isinstance(suggestion, dict):
            suggestion = {'groups': suggestion, 'discards': []}
        write_json(folder / 'suggestions.json', suggestion)
        write_json(proposal_signature, {'signature': p.analysis_signature})
    groups, discards, warnings = prepare_suggestions(suggestion)
    progress(2, 'Verifico l’ultima take completa di ciascuna frase…')
    groups = choose(raw, groups)
    write_json(folder / 'reviewed-suggestions.json', {'groups': groups, 'discards': discards})
    progress(2, 'Take verificate · calcolo tagli e tempi del montaggio…')
    plan = build_cut_plan(raw, duration=p.source_video.duration, fps=p.source_video.fps,
                         signature=p.analysis_signature, groups=groups, discards=discards)
    plan['warnings'] = warnings
    progress(2, 'Verifico ripartenze parziali rimaste nel testo…')
    from .cut_residual import review_residual_takes
    plan = review_residual_takes(raw, plan)
    plan = align(p, folder, plan, progress)
    write_json(folder / 'plan.json', plan)
    progress(3, 'Proposta salvata · preparo la revisione')
    return {'revision': plan['revision'], 'groups': len(plan['groups'])}


class CutEngine:
    """Call the existing asynchronous CUT operations without an HTTP loopback."""
    def __init__(self, actions, state, current):
        self.actions, self.state, self.current = actions, state, current

    async def perform(self, action, pid, *, request=None, report=lambda *args: None):
        operation = self.actions[action]
        job = await operation(pid, request) if request is not None else await operation(pid)
        if job.get('status') != 'running':
            return job
        while True:
            row = self.state(pid)
            report(min(4, int(row.get('completed', 0))), 4, row.get('message', 'CUT in corso'))
            if row.get('status') == 'succeeded':
                return row.get('result') or {}
            if row.get('status') != 'running':
                from .magic_services import MagicWaitingInput, MagicBudgetReached
                error = row.get('message') or 'CUT non riuscito'
                if row.get('error_type') == 'MagicBudgetReached':
                    raise MagicBudgetReached(error)
                if row.get('error_type') == 'MagicWaitingInput':
                    raise MagicWaitingInput(error)
                raise RuntimeError(error)
            await asyncio.sleep(.25)
