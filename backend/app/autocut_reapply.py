"""Read-only fingerprints for explicit replacement of edited timelines."""
import hashlib,json


def timeline_snapshot(timeline):
    records=[];items={}
    def call(obj,name,default=None):
        method=getattr(obj,name,None)
        return method() if callable(method) else default
    for kind in ('video','audio','subtitle'):
        items[kind]=[]
        for track in range(1,int(timeline.GetTrackCount(kind) or 0)+1):
            for clip in timeline.GetItemListInTrack(kind,track) or []:
                items[kind].append(clip)
                records.append({'kind':kind,'track':track,'id':call(clip,'GetUniqueId'),
                    'start':clip.GetStart(),'end':clip.GetEnd(),'left':call(clip,'GetLeftOffset'),
                    'right':call(clip,'GetRightOffset'),'enabled':call(clip,'GetClipEnabled'),
                    'properties':call(clip,'GetProperty',{})})
    content={'timeline':timeline.GetUniqueId(),'clips':records,'markers':timeline.GetMarkers() or {}}
    signature=hashlib.sha256(json.dumps(content,sort_keys=True,default=str).encode()).hexdigest()
    return {'signature':signature,'items':items}


def inspect_timeline(timeline,cut):
    from .resolve_native_cut import validate_active_source
    snapshot=timeline_snapshot(timeline);items=snapshot['items']
    modified=len(items['video'])!=1 or len(items['audio'])!=1 or bool(items['subtitle'])
    if not modified:
        modified=any(callable(getattr(c,'GetClipEnabled',None)) and not c.GetClipEnabled() for c in items['video']+items['audio'])
    if not modified:
        try:validate_active_source(items['video']+items['audio'],int(timeline.GetStartFrame()),cut)
        except RuntimeError:modified=True
    return {'modified':modified,'timeline_signature':snapshot['signature']}
