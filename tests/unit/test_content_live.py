import pytest

from backend.app.content_live import frame_range, save_verified_project, source_fingerprint, validate_video_probe


def test_frame_range_uses_source_timeline_absolute_start() -> None:
    assert frame_range(90000, 25, 54.4, 58.9) == (91360, 91473)


def test_source_fingerprint_changes_with_audio_or_video_state() -> None:
    before = {
        "timeline_id": "source-id",
        "video": [{"id": "v1", "start": 90000, "end": 92135, "transform": {"ZoomX": 1.0}}],
        "audio": [{"id": "a1", "start": 90000, "end": 92135}],
    }
    after = {**before, "audio": [{"id": "a1", "start": 90000, "end": 92134}]}
    assert source_fingerprint(before) != source_fingerprint(after)


def test_video_probe_requires_exact_frame_count_and_fps() -> None:
    expected = {"streams": [{"codec_type": "video", "nb_frames": "113", "r_frame_rate": "25/1"}]}
    assert validate_video_probe(expected, expected_frames=113, fps=25) == 113
    with pytest.raises(ValueError, match="frame count"):
        validate_video_probe(expected, expected_frames=112, fps=25)
    with pytest.raises(ValueError, match="frame rate"):
        validate_video_probe(expected, expected_frames=113, fps=30)
    with pytest.raises(ValueError, match="video stream"):
        validate_video_probe({"streams": []}, expected_frames=113, fps=25)


def test_save_verified_project_requires_success_and_unchanged_source() -> None:
    expected = {"timeline_id": "master", "video": ["clip"]}
    assert save_verified_project(lambda: True, lambda: expected, expected) is True
    with pytest.raises(RuntimeError, match="save failed"):
        save_verified_project(lambda: False, lambda: expected, expected)
    with pytest.raises(RuntimeError, match="source changed"):
        save_verified_project(lambda: True, lambda: {"timeline_id": "master", "video": []}, expected)
