"""Production adapters: reuse CUT, research, selections and Resolve handoff."""
import asyncio
from dataclasses import asdict
from fractions import Fraction
import json
import os
import re
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


def normalize_semantic_chunk_boundaries(run):
    """Repair tiny adjacent-chunk overlaps left by an older CUT checkpoint.

    Editorial validation requires each beat to begin no earlier than the one
    before it ends.  Old saved CUTs may be off by one frame at a boundary, so
    repair the persisted checkpoint before resuming instead of forcing a new
    CUT (and keep a one-time rollback copy).
    """
    path = Path(run) / 'semantic-chunks.json'
    chunks = read_json(path, [])
    if not isinstance(chunks, list):
        return 0
    previous_end, changed = 0.0, 0
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        try:
            start, end = float(chunk['start']), float(chunk['end'])
        except (KeyError, TypeError, ValueError):
            continue
        repaired_start = max(start, previous_end)
        repaired_end = max(end, repaired_start + 0.001)
        if repaired_start != start or repaired_end != end:
            if changed == 0:
                backup = path.with_name('semantic-chunks.before-boundary-normalization.json')
                if not backup.exists():
                    write_json(backup, chunks)
            chunk['start'] = repaired_start
            chunk['end'] = repaired_end
            chunk['duration'] = repaired_end - repaired_start
            changed += 1
        previous_end = repaired_end
    if changed:
        write_json(path, chunks)
    return changed


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
    # v2 deliberately invalidates runs created before MAGICO was locked to the
    # active Source file.  A partial run from that older policy must never be
    # resumed against the wrong inherited CUT lineage.
    return fingerprint(['magic-current-source-v2', project.analysis_signature, signatures, state])


def _literal_anchor_queries(text, proposed, *, image=False):
    """Keep explicit objects and named places in sourcing, not only AI paraphrases."""
    from .geographic_context import places_in
    proposals = [str(query).strip() for query in proposed if str(query).strip()]
    anchors = []
    if re.search(r'\b(passaport\w*|passports?)\b', str(text), re.I) and not any(
        re.search(r'\b(passaport\w*|passports?)\b', query, re.I) for query in proposals
    ):
        anchors.append('passport travel document close up photo' if image else 'passport travel document close up footage')
    for place in places_in(text):
        if not any(place.casefold() in query.casefold() for query in proposals + anchors):
            anchors.append(f'{place} travel documentary photo' if image else f'{place} travel documentary footage')
    return list(dict.fromkeys(anchors + proposals))


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
                'queries':_literal_anchor_queries(text, (q for shot in shots for q in shot.get('video_queries', []))),
                'image_queries':_literal_anchor_queries(text, (q for shot in shots for q in shot.get('image_queries', [])), image=True)})
        preceding += ' '+text
    return output


def configured_visual_client():
    if os.environ.get('RAMBLA_VISUAL_BACKEND','').casefold()=='freellmapi':
        from .visual_gateway import FreeLLMVisualClient
        return FreeLLMVisualClient(os.environ.get('RAMBLA_FREELLM_API_KEY',''),endpoint=os.environ.get('RAMBLA_FREELLM_URL','http://127.0.0.1:8831/v1/chat/completions'),model=os.environ.get('RAMBLA_FREELLM_MODEL','auto'))
    from .gemini_interactions import GeminiInteractionsClient, DEFAULT_GEMINI_MODEL
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    return GeminiInteractionsClient(key, model=os.environ.get('RAMBLA_DIRECTOR_MODEL', DEFAULT_GEMINI_MODEL),
        thinking_level='low', max_retries_per_model=0) if key else None


def generic_candidates(beat, items):
    rows = [dict(asset_id=f"{beat['id']}--pexels:{item['provider_id']}", chunk_id=beat['id'],
        kind='video', provider='pexels', title=item.get('title',''), description=item.get('description',''),
        source_page=item.get('source_page',''), score=-1, role='generic', generic_item=item)
        for item in items]
    return shortlist_candidates(rows, beat['text'], beat['places'], limit=2)


def visual_candidate_order(beats, candidates):
    """Verify specific videos and photos before spending budget on topic-level filler.

    Each beat gets a first video/photo/generic pass before extras. Images are
    eligible for visible coverage when specific video evidence is unavailable.
    """
    grouped = {str(beat['id']): [] for beat in beats}
    for candidate in candidates:
        grouped.setdefault(str(candidate['chunk_id']), []).append(candidate)
    lanes = {}
    for beat_id, rows in grouped.items():
        videos = [row for row in rows if row.get('kind') == 'video' and row.get('role') != 'generic']
        images = [row for row in rows if row.get('kind') == 'image']
        generics = [row for row in rows if row.get('role') == 'generic']
        lanes[beat_id] = videos[:1] + images[:1] + generics[:1] + videos[1:] + images[1:] + generics[1:]
    maximum = max((len(rows) for rows in lanes.values()), default=0)
    return [rows[index] for index in range(maximum) for rows in lanes.values() if index < len(rows)]


def spread_visual_candidates(ordered, limit):
    """Spend a small visual budget across the whole edit, not only its opening."""
    if limit<=0:return []
    first={}
    for row in ordered:first.setdefault(row['chunk_id'],row)
    leaders=list(first.values())
    if len(leaders)>limit:
        positions=[len(leaders)//2] if limit==1 else [round(i*(len(leaders)-1)/(limit-1)) for i in range(limit)]
        return [leaders[i] for i in positions]
    seen={row['asset_id'] for row in leaders}
    return (leaders+[row for row in ordered if row['asset_id'] not in seen])[:limit]


def coverage_upgrade_scope(beats, selections, decisions):
    """Retry uncovered scenes and automatic stills; protect manual choices/videos."""
    automatic={d['beat_id']:d for d in decisions}
    output=[]
    for beat in beats:
        if beat['end']-beat['start']<1.5:
            continue
        selected=selections.get(beat['id'],{})
        if selected.get('no_broll'):
            continue
        assets=[a['asset_id'] for a in selected.get('selected_assets',[])]
        old=automatic.get(beat['id'],{})
        if not assets or (assets==[old.get('asset_id')] and old.get('role') in {'image_coverage','fallback_image'}):
            output.append(beat['id'])
    return output


def automatic_generic_selection(items, *, limit=4):
    """Keep a small, always-present topic/place generic coverage set."""
    selected, identities, places = [], set(), set()
    for prefer_places in (True, False):
        for item in items:
            provider_id = str(item.get('provider_id') or '')
            is_place = str(item.get('coverage_group') or '') == 'places' and bool(str(item.get('place') or '').strip())
            if not provider_id or provider_id in identities or is_place != prefer_places:
                continue
            place = str(item.get('place') or '').casefold().strip()
            if is_place and place in places:
                continue
            selected.append(provider_id); identities.add(provider_id)
            if place:
                places.add(place)
            if len(selected) == limit:
                return selected
    return selected


def media_duration(path):
    probe = subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(path)],
        capture_output=True, text=True, check=True, timeout=20)
    return float(json.loads(probe.stdout)['format']['duration'])


class MagicProductServices:
    def __init__(self, projects, root, store, cut_engine, research, prepare, payload, deliver, *, visual_client=configured_visual_client, generics=None, media_prepare_timeout_seconds=75):
        self.projects, self.root, self.store = projects, Path(root), store
        self.cut = MagicCutAdapter(projects, root, store, cut_engine)
        self.research, self.prepare, self.payload, self.deliver = research, prepare, payload, deliver
        self.visual_client = visual_client
        self.generics = generics
        self.media_prepare_timeout_seconds = float(media_prepare_timeout_seconds)
        if self.media_prepare_timeout_seconds <= 0:
            raise ValueError('Timeout preparazione media non valido')
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
                repaired = normalize_semantic_chunk_boundaries(run)
                result = await asyncio.to_thread(run_magic_editorial, run, pid,
                    self.projects.load(pid).source_video.duration, report)
                if repaired:
                    result.setdefault('warnings', []).append(
                        f'Corrette {repaired} micro-sovrapposizioni del CUT salvato prima del piano editoriale.'
                    )
                return result
            if phase == 'research':
                result = await research_beats(plan_beats(run), options, self.store._path(context.run_id).parent,
                    lambda beat,provider,query:self.research(pid,beat,provider,query), report)
                if self.generics and 'pexels' in options.providers:
                    try:
                        await self.generics(pid, options.queries_per_provider)
                        generic_path = run/'generic-coverage.json'
                        generic = read_json(generic_path, {'items': [], 'selected': []})
                        generic['selected'] = automatic_generic_selection(generic.get('items') or [])
                        write_json(generic_path, generic)
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

    async def select(self, pid, run, context, options, report, *, beat_ids=None):
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
        if beat_ids is not None:
            scope=set(beat_ids)
            beats=[beat for beat in beats if beat['id'] in scope]
        candidates, warnings = [], []
        generic_state = read_json(run/'generic-coverage.json', {})
        selected_generic_ids = {str(value) for value in (generic_state.get('selected') or [])}
        generics = [item for item in (generic_state.get('items') or [])
                    if str(item.get('provider_id') or '') in selected_generic_ids]
        for beat in beats:
            rows = [asdict(c) for c in view.candidate_index.values() if c.chunk_id == beat['id']]
            rows.extend(generic_candidates(beat, generics))
            rows.sort(key=lambda r: (-float(r.get('score') or 0), str(r.get('asset_id') or '')))
            # Reserve distinct visual lanes so a broad Pexels generic cannot
            # displace a passport still, a Sri Lanka result or a specific video.
            videos = shortlist_candidates([r for r in rows if r['kind']=='video' and r.get('role') != 'generic'],
                                          beat['text'],beat['places'],limit=options.candidates_per_beat)
            images = shortlist_candidates([r for r in rows if r['kind']=='image'],
                                          beat['text'],beat['places'],limit=options.candidates_per_beat)
            filler = shortlist_candidates([r for r in rows if r.get('role') == 'generic'],
                                          beat['text'],beat['places'],limit=1)
            free_video_slots = max(1, options.candidates_per_beat - int(bool(images)) - int(bool(filler)))
            chosen = (videos[:free_video_slots] + images[:1] + filler[:1])[:options.candidates_per_beat]
            for row in chosen:
                row.update(beat_text=beat['text'],places=beat['places'],visual_target=beat.get('core_meaning') or beat['text'])
                candidates.append(row)
        # Spread the verification budget across specific videos, stills and generics.
        ordered = visual_candidate_order(beats, candidates)
        verdicts = validated_verdicts(candidates, None)
        client = self.visual_client()
        # Keep the automatic pass responsive: visual preparation can involve a
        # download and frame extraction per candidate. visual_candidate_order already
        # spreads this small budget across beats and media types.
        batch_size=min(12,max(1,int(getattr(client,'max_candidates_per_batch',12))))
        maximum = min(48, options.max_visual_requests * batch_size) if client is not None else 0
        ordered=spread_visual_candidates(ordered,maximum)
        prepared = []
        for index,row in enumerate(ordered[:maximum]):
            check_current()
            if row.get('role') == 'generic':
                from .stock_export_media import prepare_pexels_video
                try:
                    await asyncio.wait_for(
                        prepare_pexels_video(run, row['asset_id'].rsplit(':',1)[-1]),
                        timeout=self.media_prepare_timeout_seconds,
                    )
                    issues = []
                except asyncio.TimeoutError:
                    issues = [f"{row['asset_id']}: preparazione media scaduta dopo {self.media_prepare_timeout_seconds:g}s"]
                except (OSError,ValueError,RuntimeError) as exc:
                    issues = [str(exc)]
            else:
                try:
                    issues = await asyncio.wait_for(
                        self.prepare(pid, [row['asset_id']], None),
                        timeout=self.media_prepare_timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    issues = [f"{row['asset_id']}: preparazione media scaduta dopo {self.media_prepare_timeout_seconds:g}s"]
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
        for index in range(0,len(prepared),batch_size):
            check_current()
            batch = prepared[index:index+batch_size]
            for attempt in range(2):
                try:
                    verdicts.update(await asyncio.wait_for(
                        asyncio.to_thread(judge_batch,batch,client), timeout=45))
                    break
                except asyncio.TimeoutError:
                    warnings.append('Verifica visiva scaduta dopo 45s: le coperture non certificate restano fuori dal pacchetto')
                    batch = []
                    break
                except MagicBudgetReached:
                    warnings.append('Budget visivo raggiunto: candidati restanti non approvati')
                    batch = []
                    break
                except ValueError as exc:
                    warnings.append(f'Risposta visiva non valida: {exc}')
                    batch = []
                    break
                except Exception as exc:
                    from .gemini_interactions import GeminiAPIError
                    if not isinstance(exc, GeminiAPIError):
                        raise
                    if attempt == 0:
                        warnings.append(f'Verifica visiva temporaneamente non disponibile, riprovata: {exc}')
                        continue
                    warnings.append(f'Verifica visiva non disponibile: {exc}')
                    batch = []
                    break
            if not batch and any('Budget visivo raggiunto' in warning for warning in warnings):
                break
            report(min(len(ordered[:maximum])*2,len(ordered[:maximum])+index+len(batch)),
                max(1,len(ordered[:maximum])*2),'Coerenza visiva verificata')
        decisions, used_sources = [], set()
        if beat_ids is not None:
            existing=read_json(active_retrieval_root(run)/'selection-plan.json',{}).get('chunks',{})
            for bid,choice in existing.items():
                if bid in scope:continue
                for selected in choice.get('selected_assets',[]):
                    candidate=view.candidate_index.get(selected.get('asset_id'))
                    if candidate and candidate.source_page:used_sources.add(candidate.source_page)
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
        saved_decisions=decisions
        saved_verdicts=verdicts
        if beat_ids is not None:
            old=read_json(retrieval/'magic-coverage.json',{})
            replaced={d['beat_id'] for d in decisions}
            saved_decisions=[d for d in old.get('decisions',[]) if d['beat_id'] not in replaced]+decisions
            saved_verdicts={**old.get('verdicts',{}),**verdicts}
        write_json(retrieval/'magic-coverage.json',dict(plan_signature=fingerprint(read_json(run/'visual-plan.json')),
            cut_revision=context.cut_revision,fps=fps,decisions=saved_decisions,verdicts=saved_verdicts))
        report(1,1,'Coperture video e immagini verificate selezionate')
        return dict(selected=len(decisions),
            verified_videos=sum(d['role'] in {'coverage','generic'} for d in decisions),
            enabled_images=sum(d['role']=='image_coverage' for d in decisions),
            disabled_images=sum(d['role']=='fallback_image' for d in decisions),
            uncovered=len(beats)-len(decisions),warnings=warnings,partial=bool(warnings))

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
