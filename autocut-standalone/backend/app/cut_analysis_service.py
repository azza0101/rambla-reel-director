"""Shared CUT analysis; called by both manual routes and MAGICO adapters."""
import json
import hashlib
import asyncio
from pathlib import Path
from .atomic_io import write_json
from .cut_pass import build_cut_plan, prepare_suggestions
from .cut_semantic import REVIEW_VERSION


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
        context_path=folder.parent/'resolve-context.json'
        selection=read(context_path).get('source_range') if context_path.is_file() else None
        if selection:
            from .autocut_range import transcribe_range,validate_range
            selection=validate_range(selection,p.source_video.duration,p.source_video.fps)
            progress(0,'Trascrivo soltanto IN OUT · tempi riferiti al video originale…')
            raw=transcribe_range(Path(p.source_video.path),folder,selection,transcribe)
        else:
            raw = transcribe(Path(p.source_video.path), folder)
        write_json(cached, raw)
        write_json(signature, {'signature': p.analysis_signature})
    from .cut_timing_guard import repair_anomalies
    raw=repair_anomalies(raw,Path(p.source_video.path),folder,transcribe,
        notify=lambda message:progress(0,message))
    from .cut_audio_context import annotate_relative_volume
    if raw.get('volume_context_version')!=1:
        progress(0,'Misuro il volume relativo della voce · controllo locale…')
        raw=annotate_relative_volume(raw,Path(p.source_video.path))
    write_json(cached,raw)
    timing_signature=hashlib.sha256(json.dumps(raw['segments'],sort_keys=True).encode()).hexdigest()
    if (folder.parent/'resolve-context.json').is_file():
        raw['pause_removal_opt_in']=True
        write_json(cached,raw)
    progress(1, 'Trascrizione pronta · riconosco ripartenze e take…')
    proposal_signature = folder / 'suggestions-signature.json'
    if proposal_signature.is_file() and (folder / 'suggestions.json').is_file() and read(proposal_signature).get('signature') == p.analysis_signature and read(proposal_signature).get('review_version') == REVIEW_VERSION and read(proposal_signature).get('timing_signature') == timing_signature:
        suggestion = read(folder / 'suggestions.json')
        progress(1, 'Gruppi già riconosciuti · riprendo dalla verifica delle take')
    else:
        suggestion = propose(raw)
        if not isinstance(suggestion, dict):
            suggestion = {'groups': suggestion, 'discards': []}
        write_json(folder / 'suggestions.json', suggestion)
        write_json(proposal_signature, {'signature': p.analysis_signature, 'review_version': REVIEW_VERSION, 'timing_signature':timing_signature})
    groups, discards, warnings = prepare_suggestions(suggestion)
    progress(2, 'Verifico l’ultima take completa di ciascuna frase…')
    groups = choose(raw, groups)
    write_json(folder / 'reviewed-suggestions.json', {'groups': groups, 'discards': discards})
    progress(2, 'Take verificate · calcolo tagli e tempi del montaggio…')
    plan = build_cut_plan(raw, duration=p.source_video.duration, fps=p.source_video.fps,
                         signature=p.analysis_signature, groups=groups, discards=discards)
    plan['warnings'] = warnings + suggestion.get('warnings', [])
    progress(2, 'Verifico ripartenze parziali rimaste nel testo…')
    from .cut_residual import review_residual_takes
    if suggestion.get('semantic_review_version') != REVIEW_VERSION:
        plan = review_residual_takes(raw, plan)
    else:
        write_json(folder / 'semantic-review.json', {'source_signature': p.analysis_signature, 'review_version': REVIEW_VERSION, 'groups': plan['groups'], 'discards': plan['discards'], 'removed_word_indices': plan['removed_word_indices'], 'warnings': plan['warnings']})
    plan = align(p, folder, plan, progress)
    write_json(folder / 'plan.json', plan)
    from .cut_pass import clean_transcript, words_of
    # This detailed editorial report stays in the local project. It is never
    # part of automatic GitHub diagnostics, which remain sanitized.
    write_json(folder / 'editorial-review.json', {
        'source_signature': p.analysis_signature, 'revision': plan['revision'],
        'original_text': ' '.join(w['text'] for w in words_of(raw)),
        'kept_text': clean_transcript(raw, plan)['text'],
        'groups': plan['groups'], 'discards': plan['discards'],
        'removed_word_indices': plan['removed_word_indices'],
        'warnings': plan.get('warnings', [])})
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
