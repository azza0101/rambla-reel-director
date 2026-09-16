def test_social_ui_exposes_login_controls_and_provider_shelves():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("social-test")
    for marker in (
        "TIKTOK LOGIN", "INSTAGRAM LOGIN", "YOUTUBE SHORTS",
        "TIKTOK", "INSTAGRAM REELS", "WEB / NEWS VIDEO",
        "CLIP READY", "PREVIEW", "MANUAL", "OPEN SOURCE",
    ):
        assert marker in html
    assert "/social/${provider}/login" in html
    assert "socialLoginV2('tiktok')" in html
    assert "socialLoginV2('instagram')" in html
    assert "/social/status" in html


def test_social_login_ui_never_runs_analyze_or_accepts_credentials():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("social-test")
    start = html.index("async function socialLoginV2")
    end = html.index("function installSocialShelvesV2")
    source = html[start:end]
    assert "startStage('analyze')" not in source
    assert "password" not in source.casefold()
    assert "username" not in source.casefold()


def test_social_fallback_card_state_is_derived_from_preview_status_and_selectability():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("social-test")
    assert "preview_status==='manual'" in html
    assert "a.selectable===false" in html
    assert "socialStateV2" in html
