"""Ignore-coverages export must be non-destructive and one-shot."""
from backend.app.timeline_export_ui import PANEL, JS


def test_ignore_and_retry_controls_exist_together():
    assert 'id="retryFailedCoverageV123"' in PANEL
    assert 'id="ignoreCoveragesV123"' in PANEL
    assert 'IGNORA COPERTURE' in PANEL
    assert 'RIPROVA DOWNLOAD' in PANEL


def test_ignore_coverages_uses_one_time_override_not_saved_preferences():
    assert "async function prepareResolveHandoffV33(overrideComponents=null)" in JS
    assert "body:JSON.stringify(overrideComponents||resolveComponentsV71)" in JS
    assert "const trimmed={...base,broll:false,social:false,generic:false}" in JS
    assert "await prepareResolveHandoffV33(trimmed)" in JS
    assert "Le selezioni originali NON verranno eliminate" in JS
    assert "resolveComponentsV71=trimmed" not in JS


def test_ignore_option_appears_after_error_or_media_issues():
    assert "$('resolveIgnoreActionsV123').hidden=false" in JS
    assert "$('resolveIgnoreActionsV123').hidden=!items.length" in JS
    assert "retryFailedCoverageV123" in JS
