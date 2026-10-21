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
    local = Path(candidate.get('local_asset_path') or '')
    # Stock preview_path can be a search JPEG, not a playable video preview.
    # Judge the downloaded video segment whenever it is available.
    image = candidate.get('kind') == 'image'
    path = local if not image and local.is_file() else preview if preview.is_file() else local
    if not image and path.suffix.lower() in {'.jpg','.jpeg','.png','.webp','.gif'}:
        return {**candidate,'sampled_frames':[]}
    if not path.is_file():
        return {**candidate, 'sampled_frames': []}
    stat = path.stat()
    folder = Path(directory) / fingerprint([str(path.resolve()), stat.st_size, stat.st_mtime_ns,
        candidate.get('source_start_seconds') if path != preview else 0])[:24]
    folder.mkdir(parents=True, exist_ok=True)
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
        if not output.is_file() or not output.stat().st_size:
            raise ValueError('Nessun fotogramma decodificabile nel punto richiesto')
        frames.append(str(output))
    return {**candidate, 'sampled_frames': frames}


def contact_sheet(frames):
    """Pack the actual temporal samples, keeping order, proportions and labels."""
    from PIL import Image,ImageDraw
    paths=[Path(p) for p in frames]
    if len(paths)!=3 or any(not p.is_file() or not p.stat().st_size for p in paths):
        raise ValueError('Servono tre fotogrammi reali per la tavola video')
    signature=fingerprint([(str(p.resolve()),p.stat().st_size,p.stat().st_mtime_ns) for p in paths]+['contact-sheet-v1'])[:24]
    output=paths[0].parent/('board-'+signature+'.jpg')
    if output.is_file() and output.stat().st_size:return output
    board=Image.new('RGB',(1536,560),(24,27,34));draw=ImageDraw.Draw(board)
    for i,(path,label) in enumerate(zip(paths,['1 - inizio','2 - meta','3 - fine'])):
        with Image.open(path) as image:
            image=image.convert('RGB');image.thumbnail((512,512))
            board.paste(image,(i*512+(512-image.width)//2,40+(512-image.height)//2))
        draw.text((i*512+12,10),label,fill='white')
    temporary=output.with_suffix('.tmp.jpg');board.save(temporary,quality=90);temporary.replace(output)
    return output


def judge_batch(candidates, client):
    if client is None:
        return validated_verdicts(candidates, None)
    usable = [row for row in candidates if len(row.get('sampled_frames') or []) >= (3 if row.get('kind') == 'video' else 1)
              and all(Path(p).is_file() and Path(p).stat().st_size for p in row['sampled_frames'])]
    if not usable:
        return validated_verdicts(candidates, None)
    parts, manifest = [], []
    packed=bool(getattr(client,'contact_sheets',False))
    for row in usable:
        indexes = []
        attachments=[str(contact_sheet(row['sampled_frames']))] if packed and row.get('kind')=='video' else row['sampled_frames']
        for value in attachments:
            indexes.append(len(parts)+1)
            parts.append(dict(type='image', mime_type='image/jpeg', data=base64.b64encode(Path(value).read_bytes()).decode('ascii')))
        manifest.append(dict(asset_id=row['asset_id'], frames=indexes,
            requested_scene=row.get('visual_target') or row.get('beat_text'),
            transcript=row.get('beat_text'), places=row.get('places', [])))
    board_note='Each video image is a contact sheet of three real frames, left to right: inizio, meta, fine. Judge ALL three cells, not only the central cell. An image candidate has one still. ' if packed else ''
    prompt = board_note+(
        'Evaluate the ACTUAL attached frames against each requested scene and transcript. '
        'Frame numbers are 1-based in attachment order. Metadata is not evidence. '
        'Require matching subject, action and historical/geographic context. Do not infer a named place '
        'from a generic road/uniform. Reject conflicting architecture, flags, uniforms or unrelated subjects. '
        'A video must be coherent across all its samples. If uncertain use confidence below 85; '
        'do not invent evidence. Return exactly one verdict per asset_id, with a concrete reason. '
        'A verified still image can be active coverage when no suitable video exists.\n'
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
