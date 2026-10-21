def test_magic_controls_show_real_progress_budget_and_manual_apply():
    from backend.app.curation_ui_v2 import render_curation_page_v2
    html=render_curation_page_v2('test')
    assert 'id="magicStart"' in html
    assert 'id="magicProgress"' in html and '<progress id="magicProgress"' in html
    assert 'max_cloud_requests' in html and 'max_visual_requests' in html
    assert 'id="magicCancel"' in html and 'id="magicResume"' in html
    assert 'APPLICA resta manuale' in html
    assert '/magic/latest' in html
    assert 'id="magicOpenResult"' in html
    assert "magicSend.id='magicSend'" in html and 'INVIA AL BRIDGE' in html
    assert '/send' in html
    assert 'id="magicPhases"' in html
    assert 'renderMagicPhases' in html
    assert 'await hydrate()' in html
    assert 'prepareBrollViewV24()' in html
    assert 'desktopTargetRevision=target.revision' in html
    assert "history.replaceState(null,'',resultUrl.href)" in html
    assert 'id="magicRestart"' in html and '/restart' in html
    assert 'ensureMagicAnalysis' in html
    assert 'await ensureMagicAnalysis(pid)' in html
    assert '/projects/${pid}/analyze' in html
    # MAGICO may create a result, but must never navigate Source to it by itself.
    assert 'magicCutOpenedRun' not in html
    assert 'await openMagicOutput(3)' not in html
