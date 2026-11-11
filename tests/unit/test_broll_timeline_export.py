from pathlib import Path
import shutil
import uuid

import pytest


def _plan():
    return {"visual_beats": [
        {"id": "b1", "start": 1.0, "end": 3.0, "action": "BROLL"},
        {"id": "b2", "start": 5.0, "end": 6.5, "action": "BROLL"},
        {"id": "b3", "start": 8.0, "end": 9.0, "action": "BROLL"},
    ]}


def _workspace():
    path = Path(f".test-broll-export-{uuid.uuid4().hex}")
    path.mkdir()
    return path


def test_selected_clips_start_with_their_phrase_and_use_separate_tracks():
    from backend.app.broll_timeline_export import build_broll_timeline_plan

    tmp_path = _workspace()
    first, second = tmp_path / "first.mp4", tmp_path / "second.mp4"
    first.write_bytes(b"x")
    second.write_bytes(b"x")
    selection = {"chunks": {"b1": {"selected_assets": [
        {"asset_id": "a1", "order": 0, "track": "V2"},
        {"asset_id": "a2", "order": 1, "track": "V3"},
    ]}}}
    assets = {
        "a1": {"media_path": str(first), "duration_seconds": 3.5, "title": "Original bathroom clip",
               "source_page": "https://example.test/original", "provider": "envato"},
        "a2": {"media_path": str(second), "duration_seconds": 4.0},
    }

    result = build_broll_timeline_plan(_plan(), selection, assets, fps=25)

    assert [(row["record_start_frame"], row["record_end_frame"], row["track_index"]) for row in result["clips"]] == [
        (25, 75, 2), (25, 75, 3),
    ]
    assert all(row["source_start_frame"] == 0 and row["source_end_frame"] == 50 for row in result["clips"])
    assert result["clips"][0]["title"] == "Original bathroom clip"
    assert result["clips"][0]["source_page"] == "https://example.test/original"
    assert result["clips"][0]["provider"] == "envato"
    shutil.rmtree(tmp_path)


def test_selected_full_media_starts_at_the_exact_preview_window_not_at_source_zero():
    from backend.app.broll_timeline_export import build_broll_timeline_plan

    tmp_path = _workspace()
    media = tmp_path / "full-source.mp4"
    media.write_bytes(b"x")
    selection = {"chunks": {"b1": {"selected_assets": [
        {"asset_id": "windowed", "order": 0, "track": "V2"},
    ]}}}
    assets = {
        "windowed": {
            "media_path": str(media),
            "duration_seconds": 30.0,
            "source_start_seconds": 12.0,
            "source_end_seconds": 15.5,
        }
    }

    result = build_broll_timeline_plan(_plan(), selection, assets, fps=25)
    clip = result["clips"][0]

    assert clip["source_start_frame"] == 300
    assert clip["source_end_frame"] == 350
    assert clip["preview_source_start_seconds"] == 12.0
    assert clip["preview_source_end_seconds"] == 15.5
    shutil.rmtree(tmp_path)


def test_selected_image_covers_the_exact_phrase_on_its_ordered_track():
    from backend.app.broll_timeline_export import build_broll_timeline_plan

    tmp_path = _workspace()
    image = tmp_path / "egypt-archive.jpg"
    image.write_bytes(b"image")
    selection = {"chunks": {"b1": {"selected_assets": [
        {"asset_id": "still-1", "order": 1, "track": "V3"},
    ]}}}
    assets = {"still-1": {
        "media_path": str(image), "duration_seconds": 0, "kind": "image",
        "title": "Egypt archive", "provider": "wikimedia",
    }}

    result = build_broll_timeline_plan(_plan(), selection, assets, fps=25)

    assert result["unavailable"] == []
    assert result["clips"] == [{
        "beat_id": "b1", "asset_id": "still-1", "title": "Egypt archive",
        "original_text": "", "editorial_meaning": "", "place": "",
        "source_page": "", "provider": "wikimedia", "kind": "image",
        "media_path": str(image.resolve()), "track_index": 3,
        "record_start_frame": 25, "record_end_frame": 75,
        "source_start_frame": 0, "source_end_frame": 50,
        "duration_frames": 50, "preview_source_start_seconds": 0.0,
        "preview_source_end_seconds": None,
    }]
    shutil.rmtree(tmp_path)


def test_unselected_beats_are_allowed_and_unavailable_selected_media_is_reported():
    from backend.app.broll_timeline_export import build_broll_timeline_plan

    selection = {"chunks": {"b2": {"selected_assets": [{"asset_id": "manual", "order": 0, "track": "V2"}]}}}
    result = build_broll_timeline_plan(_plan(), selection, {"manual": {"media_path": None}}, fps=25)

    assert result["clips"] == []
    assert result["selected_beat_count"] == 1
    assert result["unavailable"] == [{"beat_id": "b2", "asset_id": "manual", "reason": "clip file is not available locally"}]


def test_clip_shorter_than_phrase_is_rejected_instead_of_changing_timing():
    from backend.app.broll_timeline_export import build_broll_timeline_plan

    tmp_path = _workspace()
    media = tmp_path / "short.mp4"
    media.write_bytes(b"x")
    selection = {"chunks": {"b1": {"selected_assets": [{"asset_id": "short", "order": 0, "track": "V2"}]}}}
    result = build_broll_timeline_plan(_plan(), selection, {"short": {"media_path": str(media), "duration_seconds": 1.0}}, fps=25)

    assert result["clips"] == []
    assert "shorter than phrase" in result["unavailable"][0]["reason"]
    shutil.rmtree(tmp_path)


def test_xml_contains_exact_timing_and_one_video_track_per_selection():
    from backend.app.broll_timeline_export import build_broll_timeline_plan, render_fcp7_xml

    tmp_path = _workspace()
    media = tmp_path / "clip & one.mp4"
    media.write_bytes(b"x")
    selection = {"chunks": {"b2": {"selected_assets": [{"asset_id": "a1", "order": 0, "track": "V2"}]}}}
    plan = build_broll_timeline_plan(_plan(), selection, {"a1": {"media_path": str(media), "duration_seconds": 3.5}}, fps=25)

    xml = render_fcp7_xml(plan, sequence_name="Test B-ROLL v1")

    assert "<name>Test B-ROLL v1</name>" in xml
    assert "<start>125</start>" in xml and "<end>163</end>" in xml
    assert media.resolve().as_uri().replace("&", "&amp;") in xml
    assert xml.count("<track>") == 2  # V1 placeholder + selected V2
    shutil.rmtree(tmp_path)


def test_plan_requires_positive_integer_fps():
    from backend.app.broll_timeline_export import build_broll_timeline_plan

    with pytest.raises(ValueError, match="fps"):
        build_broll_timeline_plan(_plan(), {"chunks": {}}, {}, fps=0)
