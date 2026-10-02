"""Builder used only on the isolated hotfix-check branch."""
from pathlib import Path
import subprocess


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise RuntimeError(f"Patch anchor changed or ambiguous: {before[:100]!r}")
    return text.replace(before, after, 1)


native_path = Path("backend/app/resolve_native_subtitles.py")
source = native_path.read_text(encoding="utf-8")
source = replace_once(source, "def insert_native_subtitles(\n", '''def reserve_subtitle_track_at_start(timeline: Any) -> int:
    """Reserve an empty ST1 before the caller snapshots/protects source tracks.

    Native SRT append can ignore clipInfo.trackIndex. Insert a track at index 1
    instead of unlocking an occupied ST1: existing subtitle clips retain their
    IDs, timing and track content, with only their track numbers increasing.
    The caller must already have created its BCK backup.
    """
    count = int(timeline.GetTrackCount("subtitle") or 0)
    before = {
        _identity(item): (track, int(item.GetStart()), int(item.GetEnd()), str(item.GetName()))
        for track in range(1, count + 1)
        for item in (timeline.GetItemListInTrack("subtitle", track) or [])
    }
    locks = [bool(timeline.GetIsTrackLocked("subtitle", track)) for track in range(1, count + 1)]
    added = timeline.AddTrack("subtitle", {"index": 1}) if count else timeline.AddTrack("subtitle")
    if added is False or int(timeline.GetTrackCount("subtitle") or 0) != count + 1:
        raise RuntimeError("Resolve could not reserve a new empty native Subtitle track at ST1")
    if timeline.GetItemListInTrack("subtitle", 1):
        raise RuntimeError("Resolve ignored the new ST1 position; existing subtitles were not overwritten")
    after = {
        _identity(item): (track, int(item.GetStart()), int(item.GetEnd()), str(item.GetName()))
        for track in range(2, count + 2)
        for item in (timeline.GetItemListInTrack("subtitle", track) or [])
    }
    expected = {identity: (track + 1, start, end, text)
                for identity, (track, start, end, text) in before.items()}
    if after != expected:
        raise RuntimeError("Resolve changed existing subtitles while reserving ST1")
    for track, locked in enumerate(locks, start=2):
        if timeline.SetTrackLock("subtitle", track, locked) is False:
            raise RuntimeError("Resolve could not preserve an existing Subtitle track lock")
    if timeline.SetTrackLock("subtitle", 1, False) is False:
        raise RuntimeError("Resolve could not unlock the empty new ST1")
    enable = getattr(timeline, "SetTrackEnable", None)
    if callable(enable) and enable("subtitle", 1, True) is False:
        raise RuntimeError("Resolve could not enable the new Subtitle track")
    return 1


def insert_native_subtitles(
''')
source = replace_once(source,
    '    del resolve, fps, base_frame  # SRT is relative; Resolve anchors it to the timeline start.\n    if not rows:\n        return []\n',
    '''    del resolve
    if not rows:
        return []
    if fps <= 0:
        raise ValueError("subtitle fps must be positive")
    start_getter = getattr(timeline, "GetStartFrame", None)
    timeline_start = int(start_getter()) if callable(start_getter) else int(base_frame)
    offset = (int(base_frame) - timeline_start) / fps
    if offset < 0:
        raise ValueError("Subtitle IN is before the start of the timeline")
    # SRT import is anchored to timeline start, not the playhead/current IN.
    srt_rows = [{**row, "start_seconds": float(row["start_seconds"]) + offset,
                 "end_seconds": float(row["end_seconds"]) + offset} for row in rows]
''')
source = replace_once(source,
    '    before = {_identity(item) for item in _subtitle_items(timeline)}\n',
    '''    if target_track == 1 and _subtitle_items(timeline, 1):
        raise RuntimeError("Selective native subtitle import requires a reserved empty ST1")
    before = {_identity(item) for item in _subtitle_items(timeline)}
''')
assert source.count('render_filtered_srt(rows)') == 2
source = source.replace('render_filtered_srt(rows)', 'render_filtered_srt(srt_rows)')
source = replace_once(source,
    '                if target_track is None\n',
    '                if target_track is None or wanted_track == 1\n')
native_path.write_text(source, encoding="utf-8")

materializer_path = Path("backend/app/resolve_textplus_timeline.py")
source = materializer_path.read_text(encoding="utf-8")
source = replace_once(source, '    normalize_subtitle_rows,\n',
                      '    normalize_subtitle_rows,\n    reserve_subtitle_track_at_start,\n')
source = replace_once(source,
    '            elif apply_scope == "subtitles":\n                muted_subtitle_count = mute_prior_rambla_subtitles(generated)\n',
    '''            elif apply_scope == "subtitles":
                if not payload.get("subtitles"):
                    raise ValueError("Nessun sottotitolo nel pacchetto: seleziona i sottotitoli in RMBL")
                muted_subtitle_count = mute_prior_rambla_subtitles(generated)
                # Reserve ST1 BEFORE snapshotting item tracks and lock states.
                # The SRT importer uses ST1 regardless of clipInfo.trackIndex.
                subtitle_target_track = reserve_subtitle_track_at_start(generated)
''')
source = replace_once(source,
    '            if apply_scope == "subtitles":\n                subtitle_target_track = int(generated.GetTrackCount("subtitle") or 0) + 1\n', '')
source = replace_once(source,
    '                reserve_subtitle_track=bool(payload.get("subtitles")) and mode in {"combined", "editing"} and include_subtitles,\n',
    '                reserve_subtitle_track=bool(payload.get("subtitles")) and mode in {"combined", "editing"} and include_subtitles and apply_scope != "subtitles",\n')
materializer_path.write_text(source, encoding="utf-8")

Path("RAMBLA_VERSION").write_text("v0046\n", encoding="utf-8")
handoff = Path("docs/HANDOFF.md")
text = replace_once(handoff.read_text(encoding="utf-8"), 'Versione: `v0045`', 'Versione: `v0046`')
text += '''

### SOLO SUBS: conflitto tra destinazione e lock ST1 — v0046

- Root cause nel percorso v0040-v0045: protect_existing_tracks bloccava ST1,
  mentre insert_native_subtitles sbloccava soltanto ST2 richiesta. L'importatore
  SRT nativo poteva restituire un valore truthy ma non inserire alcun caption.
- SOLO SUBS ora riserva una nuova ST1 vuota con AddTrack("subtitle", {"index": 1})
  PRIMA degli snapshot e dei lock. Le vecchie tracce sottotitoli passano a ST2,
  ST3, ecc.; identità, testi, frame e lock vengono verificati e conservati.
- I vecchi subs RMBL rimangono disattivati, non eliminati. La nuova ST1 riceve
  un normale AppendToTimeline([subtitle_media]), senza il trackIndex ignorato.
- Se Resolve ignora l'inserimento indicizzato della traccia, non viene eseguito
  l'append su una ST1 occupata. Il percorso di errore conserva il backup BCK.
- Il file SRT include la differenza fra IN corrente e inizio timeline: non si
  basa sulla posizione del playhead e non modifica marker o tracce video/audio.
- La modifica non tocca il layout del Bridge, SOLO MEDIA o le maniglie B-roll.
- Regressioni testate nel simulatore dell'importatore nativo: ST1 bloccata,
  trackIndex ignorato, invii consecutivi, vecchi caption conservati, IN non-zero,
  marker invariati, lock ripristinati e rifiuto delle destinazioni non sicure.
- Verifica su Resolve reale richiesta: i test automatici non aprono Resolve.
'''
handoff.write_text(text, encoding="utf-8")
subprocess.run(["python", "-m", "compileall", "-q", str(native_path), str(materializer_path)], check=True)
