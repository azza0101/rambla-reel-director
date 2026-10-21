from tests.unit.test_cut_pass_routes import tmp_path


def test_short_verified_clip_and_disabled_image_keep_magic_intervals(tmp_path):
    from backend.app.broll_timeline_export import build_broll_timeline_plan
    path=tmp_path/'clip.mp4';path.write_bytes(b'video')
    image=tmp_path/'photo.jpg';image.write_bytes(b'image')
    plan={'visual_beats':[dict(id='b',start=0,end=10),dict(id='c',start=10,end=15)]}
    selection={'chunks':{'b':{'selected_assets':[{'asset_id':'v'}]},'c':{'selected_assets':[{'asset_id':'i'}]}}}
    assets={'v':dict(media_path=str(path),duration_seconds=3,kind='video'),
            'i':dict(media_path=str(image),kind='image')}
    decisions=[dict(beat_id='b',asset_id='v',provider='pexels',role='coverage',enabled=True,edited_in_frame=0,edited_out_frame=90,source_in_frame=0,source_out_frame=90,verdict='verified',reason='match'),
               dict(beat_id='c',asset_id='i',provider='google_images',role='fallback_image',enabled=False,edited_in_frame=300,edited_out_frame=390,source_in_frame=0,source_out_frame=90,verdict='verified',reason='match')]
    result=build_broll_timeline_plan(plan,selection,assets,fps=30,magic_decisions=decisions)
    assert not result['unavailable'] and len(result['clips'])==2
    video,photo=result['clips']
    assert video['duration_frames']==90 and video['enabled']
    assert not photo['enabled'] and photo['track_name']=='RMBL IMMAGINI ALTERNATIVE'
    assert photo['clip_color']=='Purple' and photo['record_start_frame']==300


def test_active_verified_photo_exports_as_visible_broll_not_disabled_alternative(tmp_path):
    from backend.app.broll_timeline_export import build_broll_timeline_plan
    image=tmp_path/'passport.jpg'
    image.write_bytes(b'image')
    visual={'visual_beats':[dict(id='passport',start=2,end=6)]}
    selected={'chunks':{'passport':{'selected_assets':[{'asset_id':'photo'}]}}}
    assets={'photo':dict(media_path=str(image),kind='image',provider='google_images')}
    decision=dict(beat_id='passport',asset_id='photo',provider='google_images',
        role='image_coverage',enabled=True,edited_in_frame=60,edited_out_frame=180,
        source_in_frame=0,source_out_frame=120,verdict='verified',reason='Passport visible')
    result=build_broll_timeline_plan(visual,selected,assets,fps=30,magic_decisions=[decision])
    assert result['clip_count']==1
    row=result['clips'][0]
    assert row['kind']=='image' and row['enabled'] is True
    assert row['role']=='image_coverage' and row['track_name']==''
    assert row['record_start_frame']==60 and row['record_end_frame']==180
