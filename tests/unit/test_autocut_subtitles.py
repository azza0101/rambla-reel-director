from tests.unit.test_cut_pass import transcript


def test_subtitles_use_final_cut_map_and_exclude_removed_words():
    from backend.app.autocut_subtitles import subtitle_rows
    raw=transcript([(0,1,'scarta'),(3,4,'prima frase'),(8,9,'ultima frase')])
    plan={'revision':'test','fps':'30','removed_word_indices':[0],'duration_seconds':2,
          'segments':[{'source_in_frame':90,'source_out_frame':120,'edited_in_frame':0,'edited_out_frame':30},
                      {'source_in_frame':240,'source_out_frame':270,'edited_in_frame':30,'edited_out_frame':60}]}
    rows=subtitle_rows(raw,plan)
    assert [r['text'] for r in rows]==['prima frase','ultima frase']
    assert rows[0]['start_frame']==0 and rows[-1]['end_frame']==60
    assert rows[1]['start_seconds']==1


def test_subtitle_option_is_enabled_by_default():
    from backend.app.autocut_service import ApplyRequest
    from backend.app.autocut_ui import render_autocut
    assert ApplyRequest(revision='r').create_subtitles is True
    assert 'id="integrationCreateSubtitles"' in render_autocut()


def test_caption_chunks_are_short_and_keep_all_words():
    from backend.app.autocut_subtitles import subtitle_rows
    from backend.app.cut_pass import build_cut_plan,clean_transcript
    raw=transcript([(0,5,'Questa frase contiene molte parole per verificare tutti i sottotitoli generati.')])
    plan=build_cut_plan(raw,duration=6,fps=30,signature='s',groups=[])
    rows=subtitle_rows(raw,plan)
    assert all(len(r['text'].split())<=4 for r in rows)
    assert ' '.join(r['text'] for r in rows)==clean_transcript(raw,plan)['text']
    assert all(a['end_frame']<=b['start_frame'] for a,b in zip(rows,rows[1:]))


def test_unchecked_subtitles_never_call_resolve_import():
    from backend.app.autocut_subtitles import apply_subtitles
    assert apply_subtitles(None,None,None,{},100)==0


def test_apply_uses_existing_native_import_and_checks_timing(monkeypatch):
    from types import SimpleNamespace as Obj
    from backend.app.autocut_subtitles import apply_subtitles
    import backend.app.resolve_native_subtitles as native
    calls=[];verified=[];items=[object()]
    monkeypatch.setattr(native,'insert_native_subtitles',lambda *a,**kw:calls.append((a,kw)) or items)
    monkeypatch.setattr(native,'verify_native_subtitles',lambda *a,**kw:verified.append(kw))
    monkeypatch.setattr(native,'subtitle_track_for_items',lambda *a:1)
    timeline=Obj(SetTrackName=lambda *a:True,SetTrackEnable=lambda *a:True)
    rows=[{'text':'ciao','start_seconds':0,'end_seconds':1,'start_frame':0,'end_frame':30}]
    payload={'native_cut':{'fps':'30'},'subtitle_rows':rows,'subtitle_path':'captions.srt'}
    assert apply_subtitles(None,object(),timeline,payload,108000)==1
    assert calls[0][0][3]==rows and calls[0][1]['target_track']==1
    assert verified[0]['base_frame']==108000


def test_words_outside_actual_kept_video_never_become_end_captions():
    from backend.app.autocut_subtitles import subtitle_rows
    raw=transcript([(0,1,'dentro'),(8,9,'fuori')])
    plan={'revision':'r','fps':'30','duration_frames':30,'duration_seconds':1,'removed_word_indices':[],
        'segments':[{'source_in_frame':0,'source_out_frame':30,'edited_in_frame':0,'edited_out_frame':30}]}
    rows=subtitle_rows(raw,plan)
    assert [r['text'] for r in rows]==['dentro']
    assert rows[-1]['end_frame']<=30
