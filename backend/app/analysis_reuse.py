"""Source/guide provenance migration, independent of retrieval and plan shape."""
import hashlib
import json
from .atomic_io import write_json
from .editorial_import import normalized_chunks,transcript_package,digest


def ensure_analysis_ready(run,project):
    if not project.source_video:return False
    from pathlib import Path
    from .debug_run_cli import analysis_input_signature
    try:
        chunks=normalized_chunks(run)
        raw=json.loads((run/'transcript-raw.json').read_text(encoding='utf-8'))
        if not chunks or not raw.get('segments') or any(not c['text'] or c['end']<=c['start'] for c in chunks):return False
        source=Path(project.source_video.path)
        guide=Path(project.guide_audio.path) if project.guide_audio else source
        current=analysis_input_signature(source,guide)
        stat=source.stat()
        if hashlib.sha256(f'{source.resolve()}|{stat.st_size}|{stat.st_mtime_ns}'.encode()).hexdigest()!=project.source_video.signature:return False
        marker=json.loads((run/'analysis-signature.json').read_text(encoding='utf-8')) if (run/'analysis-signature.json').is_file() else {}
        provenance=json.loads((run/'run-input.json').read_text(encoding='utf-8')) if (run/'run-input.json').is_file() else None
        if provenance is not None and provenance!=current:return False
        if marker.get('analysis_signature')==project.analysis_signature:return True
        # A stale/missing marker alone is not evidence. Actual source+guide must match.
        if provenance!=current:return False
        if not marker and (run/'visual-plan.json').is_file():
            plan=json.loads((run/'visual-plan.json').read_text(encoding='utf-8'))
            anchors=[None,project.analysis_signature,digest(current)]
            matches=[a for a in anchors if digest({'chunks':chunks,'analysis_signature':a})==plan.get('transcript_signature')]
            if not matches:return False
            marker={'analysis_signature':matches[0]}
            write_json(run/'analysis-signature.json',marker)
        # Keep the old transcript anchor: the imported JSON and its cache path stay identical.
        write_json(run/'analysis-reuse.json',{'analysis_signature':project.analysis_signature,
            'source_guide':current,'transcript_chunks':digest(chunks),'migration':'verified unchanged source and guide'})
        return True
    except (OSError,ValueError,KeyError,TypeError):return False
