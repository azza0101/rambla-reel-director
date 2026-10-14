import subprocess

from backend.app.curation_ui_v2 import render_curation_page_v2
from backend.app.transcript_intent_ui import BUILD_JS


def test_partial_chunk_does_not_mark_uncovered_words_green():
    function=next(line for line in BUILD_JS.splitlines() if line.startswith('function phraseHasExistingVideoV30('))
    script=function+'''\nconst ranges=[{start:29.266667,end:32.7}];
if(phraseHasExistingVideoV30(27.96,34.9,ranges))throw Error('partial phrase reported covered');
if(phraseHasExistingVideoV30(33,33.5,ranges))throw Error('uncovered mood word reported covered');
if(!phraseHasExistingVideoV30(30,30.5,ranges))throw Error('fully covered word missing');
if(phraseHasExistingVideoV30(0,1,[{start:0,end:.6},{start:0,end:.6}]))throw Error('overlap counted twice');
'''
    result=subprocess.run(['node','-e',script],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_page_contains_full_transcript_intent_workspace():
    page = render_curation_page_v2("intent-ui")
    for element_id in (
        "transcriptWorkspaceV14", "fullTranscriptV14", "saveTranscriptV14",
        "modeCoverageV14", "modeAnimationV14", "modeHighlightV14",
        "exportSrtV14", "copyAnimationV14", "exportAnimationV14",
        "copyTextplusV14", "exportTextplusV14", "createResolveTextplusV20",
        "transcriptPhrasePreviewV15", "continueWorkflowV15",
        "editTranscriptV16", "transcriptReviewSurfaceV16",
        "undoIntentV18", "redoIntentV18",
        "resolveTitleTemplateV21", "resolveTitleDropV21", "resolveTitleFileV21",
        "installResolveTitleV21", "resolveTitleStatusV21",
        "animationExportsV22", "editingExportsV22",
        "createResolveCombinedV22", "exportResolveCombinedDrtV22",
        "resolveErrorDialogV23", "resolveErrorTitleV23", "resolveErrorDebugV23",
            "copyResolveErrorV23", "closeResolveErrorV23",
            "resolveProgressWrapV32", "resolveProgressV32", "resolveProgressLabelV32",
    ):
        assert f'id="{element_id}"' in page
    assert "/phrase-intents" in page
    assert "/transcript/full" in page
    assert "intentCoverageV14" in page
    assert "intentAnimationV14" in page
    assert "intentHighlightV14" in page
    assert "Seleziona direttamente nella trascrizione" in page
    assert "data-transcript-word-v17" in page
    assert "clicca la prima e l’ultima parola" in page
    assert "MODIFICA TESTO" in page
    assert "transcriptIntentV14.editing" in page
    assert "editor.hidden=!transcriptIntentV14.editing" in page
    assert "PAROLE EVIDENZIATE" in page
    assert "data-highlight-word-v16" in page
    assert "transcriptChapterV17" in page
    assert "selectionAnchorV17" in page
    assert "AZZERA SELEZIONI" in page
    assert ".transcriptWordV17{display:inline;padding:0;margin:0;" in page
    assert "existingVideoPhraseV30" in page
    assert "transcriptGapV31" in page
    assert "text-decoration-skip-ink:none" in page
    assert "startResolveProgressV32" in page
    assert "existing_video_ranges" in page
    assert 'id="resolveArrivalV30"' in page
    assert "AUDIO RICEVUTO DA RESOLVE" in page
    assert "/resolve-bridge`" in page
    assert 'id="existingVideoSummaryV30"' in page
    assert "PRIMA" in page
    assert "Video presenti" in page
    assert "existingVideoBadgeV30" not in page
    assert "text-decoration-color:#73bd8c" in page
    assert "Ctrl+Z" in page
    assert "undoIntentSelectionV18" in page
    assert "redoIntentSelectionV18" in page
    assert "intentHistoryV18" in page
    assert "refreshPlanV18" in page
    assert "runDirectorV5()" in page
    assert "/resolve/textplus-timeline" in page
    assert "CREA TIMELINE PAROLE SELEZIONATE" in page
    assert "/resolve-title-templates" in page
    assert "X-Rambla-Filename" in page
    assert "resolveTitleTemplateV21" in page
    assert "transcriptPrerequisiteV72" in page
    assert "VAI A CONFERMA CUT" in page
    assert "content.inert=!ready" in page
    assert "Trascina qui un Fusion Title .drfx" in page
    assert "Riavvia Resolve" in page
    assert "restartRequired" in page
    assert "ANIMATION" in page
    assert "EDITING" in page
    assert "ESPORTA SUBS" in page
    assert "CREA TIMELINE PAROLE + SUBS" in page
    assert "ESPORTA TIMELINE PAROLE + SUBS" in page
    assert "/resolve/combined-timeline" in page
    assert "/resolve/combined-timeline.drt" in page
    assert "DaVinci Resolve non è aperto" in page
    assert "showResolveErrorV23" in page
    assert "COPIA DEBUG" in page
    editing_start = page.index('id="editingExportsV22"')
    editing_end = page.index('</details>', editing_start)
    fusion_title = page.index('id="resolveTitlePanelV21"')
    assert editing_start < fusion_title < editing_end
    assert 'id="resolveTitleOptionalV26"' in page
    assert "FUSION TITLE (OPZIONALE)" in page
    assert 'id="timelineExportV33"' in page
    assert 'id="exportTimelineXmlV33"' in page
    assert 'id="openTimelineResolveV33"' in page
    assert 'id="exportTimelineDraV33"' in page
    assert "/exports/broll-timeline.xml" in page
    assert "/resolve/broll-timeline" in page
    assert "/resolve/broll-timeline.dra" in page


def test_text_edit_save_and_cancel_are_together_below_the_text_box():
    page = render_curation_page_v2("text-edit-actions")
    editor_start = page.index('class="transcriptEditorV14"')
    textarea = page.index('id="fullTranscriptV14"', editor_start)
    actions = page.index('class="transcriptEditActionsV33"', textarea)
    cancel = page.index('id="editTranscriptV16"', actions)
    save = page.index('id="saveTranscriptV14"', actions)
    editor_end = page.index('</div>', save)
    assert textarea < actions < cancel < save < editor_end
    assert 'id="startTranscriptEditV33"' in page
    assert "ANNULLA MODIFICHE" in page
    assert ".transcriptEditActionsV33{display:flex;justify-content:flex-end" in page


def test_intent_buttons_have_persistent_tinted_colors_and_video_legend_is_compact():
    page = render_curation_page_v2("intent-colors")

    assert ".intentCoverageV14{background:#3b3566" in page
    assert ".intentAnimationV14{background:#173f31" in page
    assert ".intentHighlightV14{background:#51431f" in page
    assert ".intentCoverageV14[aria-pressed=true]" in page
    assert ".intentAnimationV14[aria-pressed=true]" in page
    assert ".intentHighlightV14[aria-pressed=true]" in page
    assert ".transcriptSelectionV15{position:relative" in page
    assert ".existingVideoSummaryV30{position:absolute;top:9px;right:10px" in page
    assert "Sottolineatura verde" not in page


def test_intent_merge_allows_overlapping_flags_in_controller():
    script = BUILD_JS + """
const base={coverage:false,animation:false,highlight:false};
const result=mergePhraseIntentV14(base,'coverage',true);
const final=mergePhraseIntentV14(mergePhraseIntentV14(result,'animation',true),'highlight',true);
if(JSON.stringify(final)!==JSON.stringify({coverage:true,animation:true,highlight:true}))throw Error(JSON.stringify(final));
"""
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr


def test_visual_beat_click_is_not_hijacked_by_active_transcript_selection_mode():
    page = render_curation_page_v2("beat-click")
    assert "if(original)original.call(button,e)" in page
    assert "if(transcriptIntentV14.mode){e.preventDefault();setTimeout" not in page


def test_derived_coverage_chunk_ids_resolve_to_original_transcript_intent():
    page = render_curation_page_v2("coverage-derived-id")
    assert "replace(/__coverage_\\d+$/,'')" in page


def test_visual_beat_badges_only_use_words_inside_each_derived_segment():
    script = BUILD_JS + r"""
const intents={phrases:{
  'chunk-1':{
    coverage_word_indices:[3,4],
    animation_word_indices:[],
    highlighted_word_indices:[0],
  }
}};
const coverage=intentForSegmentsV27([{source_chunk_id:'chunk-1',source_word_start_index:3,source_word_end_index:4}],intents);
const opening=intentForSegmentsV27([{source_chunk_id:'chunk-1',source_word_start_index:0,source_word_end_index:2}],intents);
if(JSON.stringify(coverage)!==JSON.stringify({coverage:true,animation:false,highlight:false}))throw Error(JSON.stringify(coverage));
if(JSON.stringify(opening)!==JSON.stringify({coverage:false,animation:false,highlight:true}))throw Error(JSON.stringify(opening));
"""
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr


def test_visual_beats_receive_exact_source_word_ranges_for_intent_badges():
    page = render_curation_page_v2("coverage-segment-metadata")
    assert "intent_segments" in page
    assert "source_word_start_index" in page
    assert "source_word_end_index" in page
