"""Validate native, downloaded video for final editing, never a preview."""
from pathlib import Path

from .video_preview import probe_full_video


class MediaQualityError(ValueError):
    """The source is missing, unverified or below the editing quality floor."""


def require_editing_quality(path) -> dict:
    """Require at least 720 pixels on the short side; never upscale."""
    try:
        facts = probe_full_video(str(Path(path)))
        width = int(facts.get('width') or 0)
        height = int(facts.get('height') or 0)
        if not facts.get('playable') or width <= 0 or height <= 0:
            raise MediaQualityError('Impossibile verificare la risoluzione del video finale')
        if min(width, height) < 720:
            raise MediaQualityError(f'Video {width}x{height}: richiesti almeno 720 pixel sul lato corto (HD). Cerca una versione HD o scegli un’altra clip.')
        return facts
    except (TypeError, OSError):
        raise MediaQualityError('Impossibile verificare la risoluzione del video finale') from None


def normalize_new_download(path, destination) -> Path:
    """Cap newly downloaded high-resolution sources at 1080p, without upscaling."""
    source = Path(path)
    facts = require_editing_quality(source)
    width, height = int(facts['width']), int(facts['height'])
    if min(width, height) <= 1080 and max(width, height) <= 1920:
        return source
    from .envato_light_media import prepare_light_media
    return prepare_light_media(source, Path(destination))
