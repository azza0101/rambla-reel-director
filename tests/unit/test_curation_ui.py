from html.parser import HTMLParser

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


def test_acceptance_launcher_uses_safe_dynamic_port_and_fast_forward_contract():
    from pathlib import Path
    launcher = (Path(__file__).parents[2] / "tools" / "start_curation_acceptance.ps1").read_text(encoding="utf-8")
    assert "8765..8799" in launcher
    assert "merge --ff-only" in launcher
    assert "status --porcelain" in launcher
    assert "RAMBLA_BUILD_TOKEN" in launcher
    assert "Start-Process $url" in launcher
    assert "reset --hard" not in launcher
    assert "Stop-Process -Id $process.Id" in launcher


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
