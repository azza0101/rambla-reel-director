from types import SimpleNamespace


def test_download_issue_exposes_safe_source_and_captcha_action():
    from backend.app.resolve_media_issues import download_issue

    candidate = SimpleNamespace(
        asset_id="beat_003--youtube_shorts:CfDCPuB5mDE",
        chunk_id="beat_003",
        provider="youtube_shorts",
        source_page="https://www.youtube.com/shorts/CfDCPuB5mDE",
        title="Egypt short",
    )
    row = download_issue(candidate, RuntimeError(
        "Provider verification required: open the source and complete login/CAPTCHA manually."
    ))

    assert row == {
        "asset_id": "beat_003--youtube_shorts:CfDCPuB5mDE",
        "beat_id": "beat_003",
        "provider": "youtube_shorts",
        "title": "Egypt short",
        "source_page": "https://www.youtube.com/shorts/CfDCPuB5mDE",
        "reason": "verification_required",
        "message": "Apri la fonte e completa login/CAPTCHA, poi riprova il download.",
    }


def test_download_issue_marks_unsupported_format_without_hiding_source():
    from backend.app.resolve_media_issues import download_issue

    candidate = SimpleNamespace(
        asset_id="beat_020--youtube_shorts:gVlTobCC3iw",
        chunk_id="beat_020",
        provider="youtube_shorts",
        source_page="https://www.youtube.com/shorts/gVlTobCC3iw",
        title="Minya short",
    )
    row = download_issue(candidate, RuntimeError("Provider could not supply this media format."))

    assert row["reason"] == "format_unavailable"
    assert row["source_page"].endswith("gVlTobCC3iw")
    assert "saltata" in row["message"].lower()


def test_export_ui_renders_source_links_and_retry_for_skipped_clips():
    from pathlib import Path

    source = Path("backend/app/timeline_export_ui.py").read_text(encoding="utf-8")
    assert "renderResolveMediaIssuesV48" in source
    assert "APRI FONTE E VERIFICA" in source
    assert "RIPROVA DOWNLOAD" in source
    assert 'target="_blank"' in source


def test_resolve_preparation_keeps_running_when_selected_media_download_fails():
    from pathlib import Path

    source = Path("backend/app/curation_server.py").read_text(encoding="utf-8")
    assert "Download delle clip selezionate non completato" not in source
    assert "broll_timeline_payload(project_id, allow_unavailable=True," in source
    assert 'payload["media_issues"] = media_issues' in source
