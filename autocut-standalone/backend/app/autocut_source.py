"""Read-only Resolve source acquisition in a disposable, bounded process."""
import json


def capture_source(resolve):
    project=resolve.GetProjectManager().GetCurrentProject()
    if not project:raise ValueError('Apri un progetto Resolve')
    timeline=project.GetCurrentTimeline()
    if not timeline:raise ValueError('Apri la timeline del video originale')
    clips=[clip for track in range(1,int(timeline.GetTrackCount('video'))+1)
           for clip in (timeline.GetItemListInTrack('video',track) or [])]
    if len(clips)!=1:raise ValueError('Usa una timeline con una sola clip video integrale')
    clip=clips[0]
    if clip.GetLeftOffset()>1 or clip.GetRightOffset()>1:raise ValueError('Usa il video integrale e imposta IN OUT sulla timeline')
    media=clip.GetMediaPoolItem();path=media.GetClipProperty('File Path') if media else None
    if not path:raise ValueError('File originale non disponibile: le compound clip non sono supportate')
    result={'path':str(path),'project_name':str(project.GetName()),'timeline_name':str(timeline.GetName()),'timeline_id':str(timeline.GetUniqueId())}
    marks=timeline.GetMarkInOut() or {};video=marks.get('video') or {};audio=marks.get('audio') or {}
    marked=lambda row:any(row.get(k) is not None for k in ('in','out'))
    if marked(video) and marked(audio) and any(video.get(k)!=audio.get(k) for k in ('in','out')):
        raise ValueError('IN OUT audio/video diversi: allineali prima di importare')
    if marked(video) or marked(audio):
        row=video if marked(video) else audio
        base=int(timeline.GetStartFrame());start=int(clip.GetStart());end=int(clip.GetEnd())
        a=max(0,int(row.get('in',start-base))+base-start)
        b=min(end-start,int(row['out'])+1+base-start if row.get('out') is not None else end-start)
        if b<=a:raise ValueError('IN OUT non interseca il video originale')
        result['source_range']={'in_frame':a,'out_frame':b,'fps':str(timeline.GetSetting('timelineFrameRate'))}
    return result


def main():
    from .autocut_apply import connect
    try:print(json.dumps({'source':capture_source(connect())}),flush=True)
    except Exception as exc:
        print(json.dumps({'error':str(exc)}),flush=True)
        raise SystemExit(1)

if __name__=='__main__':main()
