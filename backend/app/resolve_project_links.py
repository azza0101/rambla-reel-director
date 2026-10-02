"""Stable project identity across source and generated Resolve timelines."""
from pathlib import Path
import json
from .atomic_io import write_json


def read(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def choose_project(rows, timeline_id, links):
    existing = {row['project_id'] for row in rows}
    if links.get(timeline_id) in existing:
        return links[timeline_id]
    matches = [row for row in rows if row['timeline_id'] == timeline_id]
    return max(matches, key=lambda row: (row['reviewed'], row['modified']))['project_id'] if matches else ''


def linked_project(root, timeline_id):
    rows = []
    for path in Path(root).glob('*/project.json'):
        manifest = read(path.parent / 'resolve-bridge.json')
        rows.append(dict(project_id=path.parent.name,
                         timeline_id=str(manifest.get('resolve_timeline_id') or ''),
                         reviewed=(path.parent / 'run' / 'phrase-intents.json').is_file(),
                         modified=path.stat().st_mtime_ns))
    return choose_project(rows, timeline_id, read(Path(root).parent / 'resolve-project-links.json'))


def link_project(root, project_id, *timeline_ids):
    if not (Path(root) / project_id / 'project.json').is_file():
        raise ValueError('RAMBLA project does not exist')
    path = Path(root).parent / 'resolve-project-links.json'
    links = read(path)
    for timeline_id in timeline_ids:
        if timeline_id:
            links[str(timeline_id)] = project_id
    write_json(path, links)


def saved_project_to_open(root, timeline_id=''):
    """Opening the app may resume saved work; audio capture still requires an exact link."""
    root = Path(root)
    linked = linked_project(root, timeline_id) if timeline_id else ''
    if linked:
        return linked, 'timeline'
    for filename in ('last-open-project.json', 'workspace-session.json'):
        project_id = str(read(root.parent / filename).get('project_id') or '')
        # Saved state is data, not an arbitrary filesystem path.
        if project_id and Path(project_id).name == project_id and (root / project_id / 'project.json').is_file():
            return project_id, 'last_saved'
    return '', ''
