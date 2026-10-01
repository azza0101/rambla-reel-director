from html.parser import HTMLParser
import json
import shutil
import subprocess

import pytest

from backend.app.curation_ui import BUILD_PREFIX, BUILD_SENTINEL_PREFIX, move_selection, phrase_status, remaining_decisions, render_curation_page


def test_phrase_status_and_completion_require_real_decision():
    assert phrase_status([], False) == "Needs Choice"
    assert phrase_status(["asset"], False) == "Selected"
    assert phrase_status("NO_BROLL", False) == "NO BROLL"
    assert phrase_status([], True) == "Error"
    assert remaining_decisions(["a", "b", "c"], {"a": [], "b": ["asset"], "c": "NO_BROLL"}) == 1


def test_reorder_updates_deterministic_asset_order():
    assert move_selection(["video", "image", "video-2"], 1, -1) == ["image", "video", "video-2"]
    assert move_selection(["video", "image", "video-2"], 1, 1) == ["video", "video-2", "image"]


def test_candidate_markup_never_nests_buttons():
    class ButtonNesting(HTMLParser):
        def __init__(self):
            super().__init__(); self.depth = 0; self.nested = False
        def handle_starttag(self, tag, attrs):
            if tag == "button":
                if self.depth: self.nested = True
                self.depth += 1
        def handle_endtag(self, tag):
            if tag == "button": self.depth -= 1
    parser = ButtonNesting(); parser.feed(render_curation_page())
    assert parser.nested is False


def test_authoritative_renderer_has_build_marker_and_no_legacy_ui():
    page = render_curation_page("abc1234")
    assert f"{BUILD_PREFIX} abc1234" in page
    assert f'{BUILD_SENTINEL_PREFIX}abc1234' in page
    assert "Solo selezionati" not in page
    assert "Selezione locale" not in page
    assert page.count("<script>") == 1
    from backend.app.curation_ui_v2 import render_curation_page_v2
    product_page=render_curation_page_v2("abc1234")
    assert '/desktop-target' in product_page
    assert 'desktopTargetRevision' in product_page


def test_visual_beat_number_is_stable_when_the_rail_is_filtered():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node runtime unavailable")
    page = render_curation_page("beat-number")
    function = next(
        line for line in page.splitlines()
        if line.startswith("function visualBeatLabelV36(")
    )
    script = function + "\nconsole.log(visualBeatLabelV36([{id:'a'},{id:'b'},{id:'c'}],{id:'b'}));"

    result = subprocess.run([node, "-e", script], capture_output=True, text=True, encoding="utf-8")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "BEAT 2"


def test_acceptance_launcher_uses_dynamic_local_port_and_fast_forward_contract():
    from pathlib import Path
    launcher = (Path(__file__).parents[2] / "tools" / "start_curation_acceptance.ps1").read_text(encoding="utf-8")
    assert "8765..8799" in launcher
    assert "$port = $null" in launcher
    assert "merge --ff-only" in launcher
    assert "status --porcelain" in launcher
    assert "RAMBLA_BUILD_TOKEN" in launcher
    assert "Start-Process $url" in launcher
    assert "reset --hard" not in launcher
    assert ".curation-acceptance-server.json" in launcher
    assert "Stop-Process -Id $oldProcess.Id" in launcher


def test_launcher_browser_failure_is_nonfatal_and_manual_url_is_always_emitted():
    from pathlib import Path
    launcher = (Path(__file__).parents[2] / "tools" / "start_curation_acceptance.ps1").read_text(encoding="utf-8")
    manual = launcher.index('Write-Output "OPEN MANUALLY: $url"')
    browser = launcher.index("$browser = Start-Process $url")
    assert manual < browser
    assert "Default browser failed" in launcher
    assert "msedge.exe" in launcher
    assert "Browser could not be opened" in launcher
    assert "Remote blob download failed after 3 attempts" in launcher
    assert "git hash-object --no-filters" in launcher
    assert launcher.rstrip().endswith("exit 0")
    browser_section = launcher[browser:]
    assert "Stop-Process -Id $process.Id" not in browser_section


def test_staged_curation_controller_separates_actions_and_inspection():
    page = render_curation_page("stage123")
    assert "FIND B-ROLL" in page and "FIND IMAGES" in page
    assert "Analysis Details" in page and "transcript" in page
    assert "startStage('analyze')" in page
    assert "startStage('source/videos')" in page
    assert "startStage('source/images')" in page
    media_handler = page[page.index("media.onclick"):page.index("node.querySelector('.select').onclick")]
    assert "pick(" not in media_handler
    assert "node.querySelector('.select').onclick=()=>pick" in page
    assert "selected?'Deselect':'Select'" in page
    assert 'id="lightboxImage" hidden' in page and 'id="lightboxVideo" controls hidden' in page
    assert "media.onclick=()=>inspectMedia(media)" in page
    assert "if(video)target.play().catch" in page
    assert "r.transcript_status==='active'" in page
    assert "Analysis failed before ASR:" in page


def test_selected_media_card_has_an_explicit_visual_state():
    page = render_curation_page("selected-card")
    assert ".card.active{" in page
    assert "--selected-card" in page
    assert "SELEZIONATO" in page


def test_analysis_details_render_concrete_visual_plan_and_search_evidence():
    page = render_curation_page("planner")
    assert 'id="visualPlanDetails"' in page
    assert "editorial_function" in page and "core_meaning" in page and "visual_mode" in page
    assert "image_queries" in page and "video_queries" in page and "avoid" in page
    assert "image_search" in page and "video_search" in page


def test_project_controls_and_vertical_shelves_are_first_class_ui():
    page = render_curation_page("project-v2")
    assert "OPEN PROJECT FILE" in page
    assert "SAVE PROJECT FILE" in page
    assert "project.rambla.json" in page
    assert "SOCIAL / SHORTS / REELS" in page
    assert "YOUTUBE / GENERAL FALLBACK" in page
    assert "STOCK / PEXELS" in page
    assert "VERTICAL SOCIAL" in page
