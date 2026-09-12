import pytest

from backend.app.captions import render_srt, validate_caption_target, validate_overlay_probe


def test_render_srt_uses_transcript_timestamps() -> None:
    segments = [
        {"start": 0.0, "end": 1.234, "text": "Ciao mondo"},
        {"start": 1.5, "end": 2.0, "text": "Rambla Studio"},
    ]
    assert render_srt(segments) == (
        "1\n00:00:00,000 --> 00:00:01,234\nCiao mondo\n\n"
        "2\n00:00:01,500 --> 00:00:02,000\nRambla Studio\n"
    )


def test_render_srt_rejects_overlapping_segments() -> None:
    with pytest.raises(ValueError, match="overlap"):
        render_srt([
            {"start": 0.0, "end": 2.0, "text": "Uno"},
            {"start": 1.9, "end": 3.0, "text": "Due"},
        ])


def test_caption_overlay_requires_alpha_and_exact_range() -> None:
    probe = {"streams": [{"codec_type": "video", "pix_fmt": "argb", "nb_frames": "113", "r_frame_rate": "25/1"}]}
    assert validate_overlay_probe(probe, expected_frames=113, fps=25) == 113
    with pytest.raises(ValueError, match="alpha"):
        validate_overlay_probe({"streams": [{**probe["streams"][0], "pix_fmt": "yuv420p"}]}, expected_frames=113, fps=25)


def test_caption_target_must_be_distinct_duplicate_with_exact_broll() -> None:
    source = {"timeline_id": "master", "name": "REEL MASTER"}
    target = {
        "timeline_id": "duplicate",
        "name": "REEL_AI_v06",
        "video": [{"track": 2, "name": "workflow-113f.mp4", "start": 91360, "end": 91473}],
    }
    validate_caption_target(source, target, name="REEL_AI_v06", broll_start=91360, broll_end=91473)
    with pytest.raises(ValueError, match="B-roll"):
        validate_caption_target(source, {**target, "video": []}, name="REEL_AI_v06", broll_start=91360, broll_end=91473)
    with pytest.raises(ValueError, match="duplicate"):
        validate_caption_target(source, {**target, "timeline_id": "master"}, name="REEL_AI_v06", broll_start=91360, broll_end=91473)
