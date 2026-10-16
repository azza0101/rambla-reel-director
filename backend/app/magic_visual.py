"""Bounded frame sampling and existing Gemini transport, without agent runtime."""
import base64
import json
from pathlib import Path
import subprocess
from .magic_store import fingerprint
from .magic_coverage import validated_verdicts


def sample_candidate(candidate, directory):
    """Sample the available clip itself, never substitute its search thumbnail."""
    preview = Path(candidate.get('preview_path') or '')
    path = preview if preview.is_file() else Path(candidate.get('local_asset_path') or '')
    if not path.is_file():
        return {**candidate, 'sampled_frames': []}
    stat = path.stat()
    folder = Path(directory) / fingerprint([str(path.resolve()), stat.st_size, stat.st_mtime_ns,
        candidate.get('source_start_seconds') if path != preview else 0])[:24]
    folder.mkdir(parents=True, exist_ok=True)
    image = candidate.get('kind') == 'image'
    if image:
        offsets = [None]
    else:
        probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'json', str(path)], capture_output=True, text=True, check=True, timeout=20)
        duration = float(json.loads(probe.stdout)['format']['duration'])
        if duration <= 0:
            raise ValueError('Durata media non valida')
        start = 0 if path == preview else max(0, float(candidate.get('source_start_seconds') or 0))
        span = min(4.0, duration-start)
        if span <= 0:
            raise ValueError('Intervallo sorgente non disponibile')
        offsets = [start + span * fraction for fraction in (.2, .5, .8)]
    frames = []
    for index, offset in enumerate(offsets):
        output = folder / f'{index}.jpg'
        if not output.is_file() or not output.stat().st_size:
            command = ['ffmpeg', '-v', 'error', '-y']
            if offset is not None:
                command += ['-ss', f'{offset:.6f}']
            command += ['-i', str(path), '-frames:v', '1', '-vf', 'scale=512:512:force_original_aspect_ratio=decrease', str(output)]
            subprocess.run(command, capture_output=True, check=True, timeout=30)
        frames.append(str(output))
    return {**candidate, 'sampled_frames': frames}


def judge_batch(candidates, client):
    if client is None:
        return validated_verdicts(candidates, None)
    usable = [row for row in candidates if len(row.get('sampled_frames') or []) >= (3 if row.get('kind') == 'video' else 1)]
    if not usable:
        return validated_verdicts(candidates, None)
    parts, manifest = [], []
    for row in usable:
        indexes = []
        for value in row['sampled_frames']:
            indexes.append(len(parts)+1)
            parts.append(dict(type='image', mime_type='image/jpeg', data=base64.b64encode(Path(value).read_bytes()).decode('ascii')))
        manifest.append(dict(asset_id=row['asset_id'], frames=indexes,
            requested_scene=row.get('visual_target') or row.get('beat_text'),
            transcript=row.get('beat_text'), places=row.get('places', [])))
    prompt = (
        'Evaluate the ACTUAL attached frames against each requested scene and transcript. '
        'Frame numbers are 1-based in attachment order. Metadata is not evidence. '
        'Require matching subject, action and historical/geographic context. Do not infer a named place '
        'from a generic road/uniform. Reject conflicting architecture, flags, uniforms or unrelated subjects. '
        'A video must be coherent across all its samples. If uncertain use confidence below 85; '
        'do not invent evidence. Return exactly one verdict per asset_id, with a concrete reason. '
        'Images are editorial alternatives and remain disabled regardless of verdict.\n'
        + json.dumps(manifest, ensure_ascii=False))
    schema = dict(type='object', additionalProperties=False, required=['verdicts'], properties={
        'verdicts': dict(type='array', items=dict(type='object', additionalProperties=False,
            required=['asset_id','coherent','confidence','reason'], properties={
                'asset_id':dict(type='string'), 'coherent':dict(type='boolean'),
                'confidence':dict(type='integer', minimum=0, maximum=100), 'reason':dict(type='string')}))})
    reply = client.generate_json(prompt, schema, image_inputs=parts)
    verified = validated_verdicts(usable, reply.data)
    result = validated_verdicts(candidates, None)
    result.update(verified)
    return result
