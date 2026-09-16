import json
from pathlib import Path


def test_cookie_specs_are_profile_scoped_and_command_redaction_hides_path(tmp_path):
    from backend.app.social_acquisition import browser_cookie_specs, redact_sensitive_command

    profile = tmp_path / "profiles" / "tiktok"
    specs = browser_cookie_specs(profile)
    assert specs[0].startswith("edge:")
    assert str(profile) in specs[0]
    command = ["python", "-m", "yt_dlp", "--cookies-from-browser", specs[0], "https://www.tiktok.com/@x/video/1"]
    redacted = redact_sensitive_command(command)
    assert str(profile) not in redacted
    assert "[REDACTED_BROWSER_PROFILE]" in redacted


def test_authenticated_section_download_tries_browser_cookie_backends_without_leaking_errors(tmp_path):
    from backend.app.social_acquisition import download_authenticated_section

    calls = []

    def runner(command, **kwargs):
        calls.append(list(command))
        output = Path(command[command.index("-o") + 1])
        if command[command.index("--cookies-from-browser") + 1].startswith("edge:"):
            raise RuntimeError(f"failed with secret path {tmp_path}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"video")
        class Result: returncode = 0
        return Result()

    target = tmp_path / "out.mp4"
    result = download_authenticated_section(
        "https://www.tiktok.com/@x/video/1", "tiktok", target,
        start=1.0, duration=3.5, profile_root=tmp_path / "profiles", runner=runner,
    )
    assert result == target
    assert target.is_file()
    assert len(calls) == 2
    assert calls[0][calls[0].index("--cookies-from-browser") + 1].startswith("edge:")
    assert calls[1][calls[1].index("--cookies-from-browser") + 1].startswith("chrome:")


def test_authenticated_download_failure_returns_generic_error_without_profile_path(tmp_path):
    from backend.app.social_acquisition import SocialAcquisitionError, download_authenticated_section

    def runner(command, **kwargs):
        raise RuntimeError("browser cookies at " + command[command.index("--cookies-from-browser") + 1])

    try:
        download_authenticated_section(
            "https://www.instagram.com/reel/ABC/", "instagram", tmp_path / "out.mp4",
            start=0, duration=3.5, profile_root=tmp_path / "profiles", runner=runner,
        )
    except SocialAcquisitionError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected SocialAcquisitionError")
    assert str(tmp_path) not in message
    assert message == "authenticated social download failed"


def test_curation_keeps_preview_and_manual_social_discovery_candidates(tmp_path):
    from backend.app.curation_artifacts import load_curation_run

    (tmp_path / "semantic-chunks.json").write_text(json.dumps([
        {"id": "chunk-1", "text": "breaking news"}
    ]), encoding="utf-8")
    (tmp_path / "online-candidates.json").write_text(json.dumps([
        {
            "parent_beat_id": "chunk-1",
            "candidates": [],
            "discovery_sources": [
                {
                    "id": "tiktok:11", "source": "tiktok", "provider": "tiktok", "provider_id": "11",
                    "source_page": "https://www.tiktok.com/@news/video/11", "description": "news phone clip",
                    "title": "news phone clip", "score": 0.71, "rights_state": "review_required",
                    "orientation": "portrait", "preview_url": "https://img.example/11.jpg",
                    "acquisition_state": "PREVIEW_ONLY", "manual_reason": "download failed",
                    "quality_state": "source_found", "clip_verified": False,
                },
                {
                    "id": "instagram:ABC", "source": "instagram", "provider": "instagram", "provider_id": "ABC",
                    "source_page": "https://www.instagram.com/reel/ABC/", "description": "reel source",
                    "title": "reel source", "score": 0.62, "rights_state": "review_required",
                    "orientation": "portrait", "preview_url": "",
                    "acquisition_state": "MANUAL_LINK", "manual_reason": "preview unavailable",
                    "quality_state": "source_found", "clip_verified": False,
                },
            ],
        }
    ]), encoding="utf-8")

    run = load_curation_run(tmp_path)
    candidates = run.chunks[0].video_candidates
    assert [row.provider for row in candidates] == ["tiktok", "instagram"]
    assert [row.acquisition_state for row in candidates] == ["PREVIEW_ONLY", "MANUAL_LINK"]
    assert candidates[0].preview_url == "https://img.example/11.jpg"
    assert candidates[1].source_page == "https://www.instagram.com/reel/ABC/"
    assert candidates[0].clip_verified is False
    assert candidates[1].clip_verified is False
