"""Generative planning: domain examples belong in fixtures, never routing code."""
from __future__ import annotations
import json
from pathlib import Path
from .atomic_io import write_json


def validate_plan(value):
    if not isinstance(value, dict) or set(value) != {'editorial_function','core_meaning','subtext','visual_mode','shots','avoid'}:
        raise ValueError('visual plan must have exactly required keys')
    if any(not isinstance(value[k], str) or not value[k].strip() for k in ('editorial_function','core_meaning','subtext')):
        raise ValueError('visual plan meaning must be nonempty strings')
    if value['visual_mode'] not in {'single','sequence','juxtaposition'}:
        raise ValueError('visual plan mode invalid')
    if not isinstance(value['avoid'], list) or any(not isinstance(x,str) for x in value['avoid']):
        raise ValueError('visual plan avoid must be strings')
    if not isinstance(value['shots'],list) or not 1 <= len(value['shots']) <= 3:
        raise ValueError('visual plan needs 1-3 shots')
    ids = set()
    for shot in value['shots']:
        if not isinstance(shot,dict) or set(shot) != {'shot_id','description','image_queries','video_queries'}:
            raise ValueError('visual plan shot keys invalid')
        if any(not isinstance(shot[k],str) or not shot[k].strip() for k in ('shot_id','description')) or shot['shot_id'] in ids:
            raise ValueError('visual plan needs unique shot id and description')
        for word in ('montage', 'split view', 'split screen', 'split-screen'):
            if word in shot['description'].casefold():
                raise ValueError(f"visual plan must separate composite scenes: shot {shot['shot_id']} contains forbidden phrase '{word}'. Replace it with ONE camera view of ONE physical action at ONE location; never combine multiple views inside a shot")
        ids.add(shot['shot_id'])
        for kind in ('image_queries','video_queries'):
            q = shot[kind]
            if not isinstance(q,list) or not 2 <= len(q) <= 3 or any(not isinstance(s,str) or not 2 <= len(s.split()) <= 10 for s in q):
                raise ValueError('visual plan queries must be 2-3 short strings')
    return value

from .visual_beats import BeatPlanner as ConcreteVisualPlanner, signature as visual_plan_signature


def load_or_create_visual_plan(chunks, outline, output_dir, *, generate, model_name='Qwen3.5-4B', event_callback=None, scope_chunk_ids=None, batch_size=4):
    path = output_dir/'visual-plan.json'
    try: cached = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError): cached = {}
    if cached.get('schema_version') == 'rambla-visual-plan-1':
        raise ValueError('Use a separate experimental output directory; imported editorial plans cannot be overwritten by local generation')
    return ConcreteVisualPlanner(generate=generate, model_name=model_name, batch_size=batch_size).plan(chunks, outline, event_callback=event_callback, cached=cached, scope_chunk_ids=scope_chunk_ids, persist=lambda value: write_json(path,value))


def ensure_local_visual_plan(chunks_path,outline_path,output_dir,model_root):
    """Explicit experimental helper only; production sourcing never calls this."""
    import os
    import subprocess
    from .debug_run_cli import DEFAULT_PIPELINE_PYTHON, _event
    model = os.environ.get('RAMBLA_DIRECTOR_MODEL','Qwen3.5-4B')
    chunks = json.loads(chunks_path.read_text(encoding='utf-8'))
    outline = json.loads(outline_path.read_text(encoding='utf-8'))
    path = output_dir/'visual-plan.json'
    try:
        cached = json.loads(path.read_text(encoding='utf-8'))
        if cached.get('status') == 'complete' and cached.get('input_signature') == visual_plan_signature(chunks,outline,model) and set(cached['chunks']) == {str(c['id']) for c in chunks}:
            _event('visual_planning',100,'Qwen Director plan reused',cache_reused=True,planner_provider=model)
            return cached
    except (OSError,ValueError,KeyError): pass
    subprocess.run([os.environ.get("RAMBLA_DIRECTOR_PYTHON", str(DEFAULT_PIPELINE_PYTHON)),'-m','backend.app.visual_planner_cli','--chunks',str(chunks_path),'--outline',str(outline_path),'--output-dir',str(output_dir),'--model-root',str(model_root),'--model',model],check=True)
    return json.loads(path.read_text(encoding='utf-8'))

def apply_visual_plan_to_outline(outline,visual_plan):
    enriched = {**outline,'beats':[]}
    for beat in outline.get('beats',[]):
        row = dict(beat)
        plan = visual_plan.get('chunks',{}).get(str(beat.get('id')))
        if plan:
            shots = plan['shots']
            queries = [s['video_queries'][0] for s in shots]
            queries.extend(q for s in shots for q in s['video_queries'][1:])
            row.update(intent='; '.join(s['description'] for s in shots),broll_queries=queries,visual_plan=plan)
        enriched['beats'].append(row)
    return enriched

def merge_visual_diagnostics(artifact,kind,rows):
    merged = json.loads(json.dumps(artifact))
    for cid,diagnostics in rows.items():
        if cid in merged.get('chunks',{}): merged['chunks'][cid][f'{kind}_search'] = diagnostics
    return merged

persist_visual_plan = write_json
