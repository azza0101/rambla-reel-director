def test_image_alternatives_get_dedicated_track_below_titles_and_are_disabled():
    from backend.app.resolve_textplus_timeline import active_track_layout, append_broll_clips
    rows=[dict(asset_id='v',track_index=2,role='coverage'),dict(asset_id='i',track_index=2,role='fallback_image')]
    clips,title=active_track_layout(3,rows)
    assert clips[1]['track_index']>clips[0]['track_index'] and title>clips[1]['track_index']
    class Item:
        def SetClipEnabled(self,value): self.enabled=value;return True
        def SetClipColor(self,value): self.color=value;return True
    item=Item()
    class Pool:
        def ImportMedia(self,_): return [object()]
        def AppendToTimeline(self,_): return [item]
    class Timeline:
        def GetTrackCount(self,_): return 2
        def SetTrackName(self,kind,index,name): self.name=name;return True
    timeline=Timeline()
    clip=dict(asset_id='i',media_path='photo.jpg',track_index=2,record_start_frame=0,record_end_frame=90,
              source_start_frame=0,enabled=False,role='fallback_image',track_name='RMBL IMMAGINI ALTERNATIVE')
    assert append_broll_clips(Pool(),timeline,[clip],base_frame=0)==1
    assert item.enabled is False and item.color=='Purple'
    assert timeline.name=='RMBL IMMAGINI ALTERNATIVE'
