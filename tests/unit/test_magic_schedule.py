def test_coverage_respects_phrase_source_and_minimum_duration():
    from backend.app.magic_coverage import schedule_coverage
    row=dict(asset_id='v',provider='pexels',kind='video',duration_frames=80)
    judge=dict(verdict='verified',reason='subject and action match')
    result=schedule_coverage('b',row,judge,start=60,end=300,total_frames=200,fps=30)
    assert result.edited_in_frame==60
    assert result.edited_out_frame==140
    assert result.source_out_frame==80
    assert result.enabled
    assert schedule_coverage('b',row,judge,start=180,end=200,total_frames=200,fps=30) is None


def test_image_fallback_is_disabled_and_missing_media_never_selected():
    from backend.app.magic_coverage import choose_coverage
    rows=[dict(asset_id='v',provider='pexels',kind='video',duration_frames=100,local_available=True),
          dict(asset_id='i',provider='google_images',kind='image',local_available=True)]
    verdicts={'v':dict(verdict='rejected',reason='wrong scene'),'i':dict(verdict='verified',reason='correct subject')}
    result=choose_coverage('b',rows,verdicts,start=0,end=120,total_frames=150,fps=30)
    assert result.asset_id=='i' and result.role=='fallback_image' and not result.enabled
    rows[1]['local_available']=False
    assert choose_coverage('b',rows,verdicts,start=0,end=120,total_frames=150,fps=30) is None
