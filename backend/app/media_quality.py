"""Measured preview quality and deterministic project-wide visual diversity."""
import hashlib
from pathlib import Path


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
    for row in rows:
        if any(same_visual(row, prior) for prior in [*history, *selected]):
            rejected += 1
            continue
        if len(selected) < limit:
            selected.append(row)
    return selected, rejected
