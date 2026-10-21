"""Local captions generated from the final reviewed CUT map, without ASR/AI."""
from fractions import Fraction
from pathlib import Path
from .cut_pass import clean_transcript
from .resolve_native_subtitles import normalize_subtitle_rows,render_filtered_srt


def subtitle_rows(raw,plan):
    cleaned=clean_transcript(raw,plan);rows=[];batch=[];rate=float(Fraction(plan['fps']))
    def flush():
        if batch:
            rows.append({'text':' '.join(w['text'] for w in batch),
                'start_seconds':batch[0]['start'],'end_seconds':batch[-1]['end']})
            batch.clear()
    for segment in cleaned['segments']:
        for word in segment['words']:
            # Transcript review preserves text even when a legacy plan omits its
            # source span. Captions must describe only speech actually on video.
            if not any(min(word['source_end']*rate,cut['source_out_frame'])>max(word['source_start']*rate,cut['source_in_frame']) for cut in plan['segments']):continue
            if batch and (len(batch)>=4 or len(' '.join(w['text'] for w in batch)+' '+word['text'])>40
                or word['end']-batch[0]['start']>2.5 or word['start']-batch[-1]['end']>.45):flush()
            batch.append(word)
            if word['text'].endswith(('.','!','?')):flush()
        flush()
    normalized=normalize_subtitle_rows(rows,fps=rate)
    limit=plan.get('duration_frames',round(plan['duration_seconds']*rate))
    if normalized and normalized[-1]['end_frame']>limit:raise ValueError('Tempi sottotitoli oltre il CUT: verifica la trascrizione allineata')
    return normalized


def prepare_subtitles(project_root,plan):
    import json
    folder=Path(project_root)/'cut'
    aligned=folder/'transcript-aligned.json'
    valid=(aligned.is_file() and (folder/'alignment-signature.json').is_file()
        and json.loads((folder/'alignment-signature.json').read_text('utf-8')).get('signature')==plan['source_signature'])
    raw=json.loads((aligned if valid else folder/'transcript-original.json').read_text('utf-8'))
    rows=subtitle_rows(raw,plan)
    if not rows:raise ValueError('Nessun sottotitolo da generare per il CUT corrente')
    path=folder/('autocut-subs-'+plan['revision']+'.srt')
    path.write_text(render_filtered_srt(rows),encoding='utf-8-sig',newline='\n')
    return {'subtitle_rows':rows,'subtitle_path':str(path.resolve())}


def apply_subtitles(resolve,project,timeline,payload,base_frame):
    rows=payload.get('subtitle_rows') or []
    if not rows:return 0
    from .resolve_native_subtitles import insert_native_subtitles,verify_native_subtitles,subtitle_track_for_items
    fps=float(Fraction(payload['native_cut']['fps']))
    items=insert_native_subtitles(resolve,project,timeline,rows,fps,base_frame,
        srt_path=Path(payload['subtitle_path']),target_track=1)
    verify_native_subtitles(timeline,rows,fps=fps,base_frame=base_frame,items=items)
    track=subtitle_track_for_items(timeline,items)
    if track is None:raise RuntimeError('Traccia sottotitoli Auto-Cut non identificabile')
    if timeline.SetTrackName('subtitle',track,'RMBL AUTO-CUT · SOTTOTITOLI') is False:
        raise RuntimeError('Impossibile identificare la traccia Auto-Cut')
    if timeline.SetTrackEnable('subtitle',track,True) is False:
        raise RuntimeError('Impossibile attivare i sottotitoli Auto-Cut')
    return len(items)
