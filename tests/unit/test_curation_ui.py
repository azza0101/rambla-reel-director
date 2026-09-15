from html.parser import HTMLParser

from backend.app.curation_ui import BUILD_MARKER, move_selection, phrase_status, remaining_decisions, render_curation_page


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
    page = render_curation_page()
    assert BUILD_MARKER in page
    assert "Solo selezionati" not in page
    assert "Selezione locale" not in page
    assert page.count("<script>") == 1
