"""Measured preview quality and deterministic project-wide visual diversity."""
import hashlib
from pathlib import Path


def balance_shots(rows):
    first=[];remaining=[];seen=set()
    for row in sorted(rows,key=lambda r:-r.get('score',0)):
        shot=row.get('shot_id')
        if shot not in seen:first.append(row);seen.add(shot)
        else:remaining.append(row)
    return first+remaining


def perceptual_hash(path: Path) -> str:
    from PIL import Image, ImageOps
    with Image.open(path) as raw:
        image = ImageOps.exif_transpose(raw).convert('L').resize((9, 8))
        pixels = list(image.getdata())
        bits = [pixels[y*9+x] > pixels[y*9+x+1] for y in range(8) for x in range(8)]
        return f'{sum(int(bit) << i for i, bit in enumerate(bits)):016x}'


def image_quality(path: Path) -> dict:
    from PIL import Image, ImageOps
    with Image.open(path) as raw:
        image = ImageOps.exif_transpose(raw).convert('RGB')
        width, height = image.size
        if max(width, height) < 1024 or min(width, height) < 480 or width * height < 500_000:
            raise ValueError('image below usable dimensions')
        pixels = list(image.convert('L').resize((9, 8)).getdata())
        bits = [pixels[y*9+x] > pixels[y*9+x+1] for y in range(8) for x in range(8)]
        fingerprint = sum(int(bit) << i for i, bit in enumerate(bits))
        return {'preview_width': width, 'preview_height': height, 'perceptual_hash': f'{fingerprint:016x}', 'content_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'portrait_crop_fraction': round(min(width, height*9/16)*min(height, width*16/9)/(width*height), 3)}


def same_visual(left: dict, right: dict) -> bool:
    for key in ('source_page', 'content_sha256', 'preview_sha256'):
        if left.get(key) and left.get(key) == right.get(key):
            return True
    a, b = left.get('perceptual_hash'), right.get('perceptual_hash')
    return bool(a and b and (int(a, 16) ^ int(b, 16)).bit_count() <= 6)


def diverse_candidates(rows: list[dict], history: list[dict], *, limit: int) -> tuple[list[dict], int]:
    selected = []
    rejected = 0
    # A mixed video list is later rendered in provider-specific shelves. A
    # global limit of 3 here used to let Shorts consume every slot before
    # TikTok/Instagram/Web Video reached the curator. Each provider therefore
    # receives the caller's bounded budget, while same-provider calls and image
    # calls retain the historical exact limit.
    video_providers = {
        str(row.get('source') or row.get('provider') or '')
        for row in rows
        if row.get('kind') == 'video' and (row.get('source') or row.get('provider'))
    }
    effective_limit = limit * len(video_providers) if len(video_providers) > 1 else limit
    for row in rows:
        if any(same_visual(row, prior) for prior in [*history, *selected]):
            rejected += 1
            continue
        if len(selected) < effective_limit:
            selected.append(row)
    return selected, rejected


def cross_chunk_duplicate_rate(groups: list[list[dict]]) -> float:
    history = []
    duplicates = total = 0
    for rows in groups:
        total += len(rows)
        duplicates += sum(any(same_visual(row, prior) for prior in history) for row in rows)
        history.extend(rows)
    return duplicates / total if total else 0.0


def other_media_history(root: Path, kind: str, beat_id: str) -> list[dict]:
    """Share fingerprints across independent stages, excluding same-beat alternatives."""
    import json
    path=root/('online-candidates.json' if kind=='video' else 'image-candidates.json')
    if not path.is_file(): return []
    payload=json.loads(path.read_text(encoding='utf-8'))
    if kind=='video':
        return [c for row in payload if row.get('parent_beat_id')!=beat_id for c in row.get('candidates',[])]
    return [c for cid,row in payload.get('chunks',{}).items() if cid!=beat_id for c in row.get('candidates',[])]
