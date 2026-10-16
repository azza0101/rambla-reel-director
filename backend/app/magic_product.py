"""Production adapters: reuse CUT, research, selections and Resolve handoff."""
import asyncio
from dataclasses import asdict
from fractions import Fraction
import json
import os
from pathlib import Path
import subprocess
from .atomic_io import write_json
from .magic_cut import MagicCutAdapter
from .magic_editorial import run_magic_editorial, editorial_context
from .magic_coverage import shortlist_candidates, choose_coverage, validated_verdicts
from .magic_research import research_beats
from .magic_visual import sample_candidate, judge_batch
from .magic_usage import provider_scope, check_current
from .magic_services import MagicBudgetReached
from .magic_store import fingerprint


def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else default


def source_signature(projects, root, pid):
    project = projects.load(pid)
    files = [Path(project.source_video.path)] if project.source_video else []
    if project.guide_audio:
        files.append(Path(project.guide_audio.path))
    signatures = [(str(path), path.stat().st_size, path.stat().st_mtime_ns) for path in files]
    state = {name: read_json(Path(root)/pid/'run'/name) for name in
        ('semantic-chunks.json','phrase-intents.json','transcript-corrections.json')}
    bridge = read_json(Path(root)/pid/'resolve-bridge.json', {})
    state['resolve_source'] = bridge.get('cut_source')
    if bridge.get('cut_source', {}).get('supported'):
        from .resolve_cut_source import verify_snapshot_files
        verify_snapshot_files(bridge['cut_source'])
    return fingerprint([project.analysis_signature, signatures, state])


def plan_beats(run):
    from .geographic_context import beat_places
    plan = read_json(run/'visual-plan.json', {})
    context = editorial_context(' '.join(str(b.get('original_text') or b.get('text') or '') for b in plan.get('visual_beats', [])))
    topic = str(plan.get('global_topic') or '') + ' ' + context
    preceding, output = '', []
    for beat in plan.get('visual_beats', []):
        text = str(beat.get('original_text') or beat.get('text') or beat.get('transcript') or beat.get('core_meaning') or '')
        if beat.get('action') == 'BROLL':
            shots = beat.get('shots') or []
            output.append({**beat, 'text':text, 'places':beat_places(text, topic, preceding),
                'queries':list(dict.fromkeys(q for shot in shots for q in shot.get('video_queries', []))),
                'image_queries':list(dict.fromkeys(q for shot in shots for q in shot.get('image_queries', [])))})
        preceding += ' '+text
    return output


def configured_visual_client():
    from .gemini_interactions import GeminiInteractionsClient, DEFAULT_GEMINI_MODEL
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    return GeminiInteractionsClient(key, model=os.environ.get('RAMBLA_DIRECTOR_MODEL', DEFAULT_GEMINI_MODEL),
        thinking_level='low', max_retries_per_model=0, fallback_models=()) if key else None


def generic_candidates(beat, items):
    rows = [dict(asset_id=f"{beat['id']}--pexels:{item['provider_id']}", chunk_id=beat['id'],
        kind='video', provider='pexels', title=item.get('title',''), description=item.get('description',''),
        source_page=item.get('source_page',''), score=-1, role='generic', generic_item=item)
        for item in items]
    return shortlist_candidates(rows, beat['text'], beat['places'], limit=2)


def media_duration(path):
    probe = subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(path)],
        capture_output=True, text=True, check=True, timeout=20)
    return float(json.loads(probe.stdout)['format']['duration'])


class MagicProductServices:
    def __init__(self, projects, root, store, cut_engine, research, prepare, payload, deliver, *, visual_client=configured_visual_client, generics=None):
        self.projects, self.root, self.store = projects, Path(root), store
        self.cut = MagicCutAdapter(projects, root, store, cut_engine)
        self.research, self.prepare, self.payload, self.deliver = research, prepare, payload, deliver
        self.visual_client = visual_client
        self.generics = generics
        self.check = lambda run_id: None

    async def run_phase(self, phase, context, options, report):
        with provider_scope(self.store, context.run_id, phase, lambda:self.check(context.run_id)):
            if phase == 'cut':
                return await self.cut.run(context, options, report)
            pid = context.output_project_id
            if not pid:
                raise ValueError('CUT MAGICO non confermato')
            run = self.root/pid/'run'
            if phase == 'editorial':
                return await asyncio.to_thread(run_magic_editorial, run, pid,
                    self.projects.load(pid).source_video.duration, report)
            if phase == 'research':
                result = await research_beats(plan_beats(run), options, self.store._path(context.run_id).parent,
                    lambda beat,provider,query:self.research(pid,beat,provider,query), report)
                if self.generics and 'pexels' in options.providers:
                    try:
                        await self.generics(pid, options.queries_per_provider)
                    except Exception as exc:
                        result['warnings'].append(f'Coperture generiche: {exc}')
                        result['partial'] = True
                return result
            if phase == 'selection':
                return await self.select(pid, run, context, options, report)
            if phase == 'preparation':
                issues = await self.prepare(pid, None, lambda percent,message:report(percent,100,message))
                if issues:
                    raise ValueError('Media selezionati non pronti: '+str(issues))
                payload = await asyncio.to_thread(self.payload, pid)
                path = self.store._path(context.run_id).with_name('resolve-payload.json')
                check_current()
                write_json(path, payload)
                report(1,1,'Pacchetto Resolve preparato')
                return dict(payload_path=str(path))
            if phase == 'delivery':
                payload = read_json(self.store._path(context.run_id).with_name('resolve-payload.json'))
                return await self.deliver(pid, payload, context.run_id, report)
            raise ValueError('Fase MAGICO sconosciuta')

    async def select(self, pid, run, context, options, report):
        from .curation_artifacts import load_curation_run
        from .curation_selection import SelectionStore
        from .editorial_import import active_retrieval_root
        from .native_cut_export import load_native_cut
        from .stock_export_media import stock_media_path
        from .social_media import media_path
        cut = await asyncio.to_thread(load_native_cut, self.root/pid, self.root)
        fps = float(Fraction(cut['fps']))
        total = round(float(cut['duration_seconds'])*fps)
        view = await asyncio.to_thread(load_curation_run, run)
        beats = plan_beats(run)
        candidates, warnings = [], []
        generics = read_json(run/'generic-coverage.json', {}).get('items', [])
        for beat in beats:
            rows = [asdict(c) for c in view.candidate_index.values() if c.chunk_id == beat['id']]
            rows.extend(generic_candidates(beat, generics))
            rows.sort(key=lambda r: (0 if r['provider']=='pexels' else 1, -r['score']))
            # Keep room for an image alternative without letting video pools starve it.
            videos = shortlist_candidates([r for r in rows if r['kind']=='video'],beat['text'],beat['places'],limit=options.candidates_per_beat)
            images = shortlist_candidates([r for r in rows if r['kind']=='image'],beat['text'],beat['places'],limit=options.candidates_per_beat)
            chosen = (videos[:max(1, options.candidates_per_beat-1)] + images[:1])[:options.candidates_per_beat]
            for row in chosen:
                row.update(beat_text=beat['text'],places=beat['places'],visual_target=beat.get('core_meaning') or beat['text'])
                candidates.append(row)
        # Interleave beats so the first visual budget serves the entire story.
        grouped = {b['id']:[c for c in candidates if c['chunk_id']==b['id']] for b in beats}
        ordered = [rows[index] for index in range(options.candidates_per_beat)
            for rows in grouped.values() if index < len(rows)]
        verdicts = validated_verdicts(candidates, None)
        client = self.visual_client()
        maximum = options.max_visual_requests * 12 if client is not None else 0
        prepared = []
        for index,row in enumerate(ordered[:maximum]):
            check_current()
            if row.get('role') == 'generic':
                from .stock_export_media import prepare_pexels_video
                try:
                    await prepare_pexels_video(run, row['asset_id'].rsplit(':',1)[-1])
                    issues = []
                except (OSError,ValueError,RuntimeError) as exc:
                    issues = [str(exc)]
            else:
                issues = await self.prepare(pid, [row['asset_id']], None)
            if issues:
                warnings.extend(str(issue) for issue in issues)
                continue
            path = row.get('local_asset_path') or row.get('preview_path')
            if row['kind']=='video' and row['provider']=='pexels':
                path = str(stock_media_path(run,row['asset_id'].rsplit(':',1)[-1]))
            elif row['kind']=='video' and row['provider'] in {'youtube','youtube_shorts','tiktok','instagram'}:
                path = str(media_path(row['source_page'],row['provider'],run,'full'))
            row.update(local_asset_path=path,local_available=bool(path and Path(path).is_file()))
            if not row['local_available']:
                continue
            if row['kind']=='video':
                row['duration_frames'] = round(await asyncio.to_thread(media_duration,path)*fps)
                row['source_in_frame'] = round(float(row.get('source_start_seconds') or 0)*fps)
                if row.get('role') == 'generic':
                    from .video_preview import materialize_clip
                    preview = await asyncio.to_thread(materialize_clip,path,run/'magic-generic-previews',row['asset_id'])
                    row.update(preview_path=preview['preview_path'],poster_path=preview['poster_path'])
            try:
                sampled = await asyncio.to_thread(sample_candidate,row,run/'magic-frames')
                prepared.append(sampled)
            except (OSError,ValueError,subprocess.SubprocessError) as exc:
                warnings.append(f"{row['asset_id']}: campioni non disponibili ({type(exc).__name__})")
            report(index+1,max(1,len(ordered[:maximum])*2),'Preparo i campioni delle coperture')
        for index in range(0,len(prepared),12):
            check_current()
            batch = prepared[index:index+12]
            try:
                verdicts.update(await asyncio.to_thread(judge_batch,batch,client))
            except MagicBudgetReached:
                warnings.append('Budget visivo raggiunto: candidati restanti non approvati')
                break
            except ValueError as exc:
                warnings.append(f'Risposta visiva non valida: {exc}')
                break
            except Exception as exc:
                from .gemini_interactions import GeminiAPIError
                if not isinstance(exc, GeminiAPIError):
                    raise
                warnings.append(f'Verifica visiva non disponibile: {exc}')
                break
            report(min(len(ordered[:maximum])*2,len(ordered[:maximum])+index+len(batch)),
                max(1,len(ordered[:maximum])*2),'Coerenza visiva verificata')
        decisions, used_sources = [], set()
        for beat in beats:
            local_candidates = [c for c in candidates if c['chunk_id'] == beat['id'] and c.get('source_page') not in used_sources]
            result = choose_coverage(beat['id'],local_candidates,verdicts,start=round(float(beat['start'])*fps),
                end=round(float(beat['end'])*fps),total_frames=total,fps=fps)
            if result:
                selected = next(c for c in local_candidates if c['asset_id'] == result.asset_id)
                if selected.get('role') == 'generic':
                    result.role = 'generic'
                if selected.get('source_page'):
                    used_sources.add(selected['source_page'])
                decisions.append(result.model_dump())
            else:
                warnings.append(f"{beat['id']}: nessuna copertura verificata, resta il parlato")
        check_current()
        retrieval = active_retrieval_root(run)
        self.persist_generic_candidates(retrieval, candidates, decisions)
        selections = SelectionStore(retrieval,{c['asset_id']:{'chunk_id':c['chunk_id']} for c in candidates},[b['id'] for b in beats])
        for decision in decisions:
            selections.set_chunk_selection(decision['beat_id'],[decision['asset_id']],no_broll=False)
        write_json(retrieval/'magic-coverage.json',dict(plan_signature=fingerprint(read_json(run/'visual-plan.json')),
            cut_revision=context.cut_revision,fps=fps,decisions=decisions,verdicts=verdicts))
        report(1,1,'Coperture selezionate e immagini alternative salvate')
        return dict(selected=len(decisions),warnings=warnings,partial=bool(warnings))

    @staticmethod
    def persist_generic_candidates(retrieval, candidates, decisions):
        from .quality_video import QUALITY_VERSION
        selected = {d['asset_id'] for d in decisions if d['role'] == 'generic'}
        if not selected:
            return
        path = retrieval/'online-candidates.json'
        artifact = read_json(path, [])
        artifact = [r for r in artifact if not r.get('magic_generic')]
        for row in candidates:
            if row['asset_id'] not in selected:
                continue
            data = dict(row.get('generic_item') or {})
            data.update(id='pexels:'+row['asset_id'].rsplit(':',1)[-1], provider='pexels', source='pexels',
                score=1, preview_path=row.get('preview_path'), poster_path=row.get('poster_path'),
                clip_verified=True, source_start_seconds=0, source_end_seconds=4,
                quality_state='magic_visual_verified', quality_reasons=['Actual frame verification passed'])
            artifact.append(dict(beat_id=row['chunk_id']+':magic-generic', parent_beat_id=row['chunk_id'],
                magic_generic=True, quality_version=QUALITY_VERSION, candidates=[data]))
        write_json(path, artifact)
