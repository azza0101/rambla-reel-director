from backend.app.release_version import RELEASE_VERSION
from backend.app.curation_ui_v2 import render_curation_page_v2
from tools.resolve_bridge.standalone_bridge import RELEASE_VERSION as BRIDGE_VERSION


def test_rambla_and_native_bridge_share_the_same_visible_release_version():
    assert RELEASE_VERSION == "v0028"
    assert BRIDGE_VERSION == RELEASE_VERSION
    page = render_curation_page_v2("release-version-test")
    assert f'<span class="brandProductV41">RMBL B ROLL</span><span class="releaseVersionV35">{RELEASE_VERSION}</span>' in page


def test_product_uses_the_supplied_wordmark_and_mark_as_favicon():
    page = render_curation_page_v2("brand-assets")
    assert 'class="brandWordmarkV41"' in page
    assert 'rel="icon" type="image/png"' in page
    assert 'data:image/png;base64,' in page


def test_release_version_uses_fixed_four_digit_format():
    assert len(RELEASE_VERSION) == 5
    assert RELEASE_VERSION.startswith("v")
    assert RELEASE_VERSION[1:].isdigit()
