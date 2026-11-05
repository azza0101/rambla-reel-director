"""Conservative export of one Resolve timeline and its referenced media."""
from __future__ import annotations
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path


def export_timeline_package(resolve, timeline, target: Path, *, confirm_missing=None) -> dict:
    target = Path(target)
    if target.exists():
        raise RuntimeError('Il file di destinazione esiste già: scegli un altro nome')
    sources = {}
    missing = {}
    warnings = []
    for kind in ('video', 'audio', 'subtitle'):
        for track in range(1, int(timeline.GetTrackCount(kind) or 0) + 1):
            for item in timeline.GetItemListInTrack(kind, track) or []:
                media = item.GetMediaPoolItem() if hasattr(item, 'GetMediaPoolItem') else None
                if not media:
                    if kind != 'subtitle': warnings.append('Elemento senza sorgente nel Media Pool: verifica titoli e composizioni')
                    continue
                path = str(media.GetClipProperty('File Path') or '')
                if not path:
                    if kind != 'subtitle': warnings.append('Elemento senza file sorgente: controlla compound, Fusion ed effetti')
                    continue
                source = Path(path)
                if not source.is_file():
                    missing[str(source).casefold()] = str(source)
                    continue
                sources[str(source.resolve()).casefold()] = source.resolve()
    missing_paths = list(missing.values())
    if missing_paths:
        if confirm_missing is None:
            raise RuntimeError('Media non disponibile: ' + ', '.join(missing_paths))
        if not confirm_missing(missing_paths):
            raise RuntimeError('Esportazione annullata: media mancanti')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rambla-share-') as temp:
        drt = Path(temp) / 'Timeline.drt'
        if timeline.Export(str(drt), resolve.EXPORT_DRT, resolve.EXPORT_NONE) is False or not drt.is_file():
            raise RuntimeError('Resolve non ha esportato la timeline DRT')
        temp_zip = Path(temp) / 'package.zip'
        manifest = []
        with zipfile.ZipFile(temp_zip, 'w', allowZip64=True) as archive:
            archive.write(drt, 'Timeline.drt', compress_type=zipfile.ZIP_DEFLATED)
            for source in sources.values():
                ident = hashlib.sha256(str(source).encode('utf-8')).hexdigest()[:12]
                name = f'Media/{ident}/{source.name}'
                archive.write(source, name, compress_type=zipfile.ZIP_STORED)
                manifest.append({'file': name, 'original_name': source.name})
            archive.writestr('manifest.json', json.dumps({'timeline': str(timeline.GetName()), 'media': manifest, 'missing_media':missing_paths, 'warnings': warnings}, ensure_ascii=False, indent=2))
            archive.writestr('LEGGIMI.txt', 'Estrai tutta la cartella. In Resolve importa Timeline.drt. Se i media risultano offline, usa Relink Media e seleziona la cartella Media. Font, effetti, plugin e file esterni Fusion possono richiedere installazione separata. Verifica la timeline prima di consegnarla.\n')
        # Never replace a pre-existing user file.
        created = False
        try:
            with target.open('xb') as output, temp_zip.open('rb') as source:
                created = True
                import shutil
                shutil.copyfileobj(source, output)
        except Exception:
            if created: target.unlink(missing_ok=True)
            raise
    return {'path': str(target), 'media_count': len(sources), 'missing_count':len(missing_paths), 'warnings': warnings}
