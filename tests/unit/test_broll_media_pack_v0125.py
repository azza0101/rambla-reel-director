"""Media Pack and selective-ignore regressions."""
import json
import zipfile
from pathlib import Path
import pytest
from fastapi import HTTPException

from backend.app.export_ignore import ignored_for_export
from backend.app.media_pack_export import create_media_pack


def test_ignore_ids_with_r_n_digits_are_valid():
    assert ignored_for_export("youtube:marine_2026,pexels:9012") == {
        "youtube:marine_2026", "pexels:9012"
    }
    assert ignored_for_export("") == set()


@pytest.mark.parametrize("bad", ["hello\nworld", "hello\x00world", "too" * 400])
def test_ignore_rejects_actual_control_characters_and_long_ids(bad):
    with pytest.raises(HTTPException) as err:
        ignored_for_export(bad)
    assert err.value.status_code == 422


def test_media_pack_zip_groups_selected_media_and_reports_missing(tmp_path):
    root = tmp_path / "project"
    local = root / "run" / "assets"
    local.mkdir(parents=True)
    (local / "baku.mp4").write_bytes(b"dummy video")
    (local / "image.png").write_bytes(b"dummy image")
    generic_dir = root / "run" / "resolve-media" / "pexels"
    generic_dir.mkdir(parents=True)
    (generic_dir / "pexels_123.mp4").write_bytes(b"stock video")
    plan = {"fps": 25, "duration_frames": 150,
            "clips": [
                {"asset_id": "youtube:marine_2026", "beat_id": "beat_017", "title": "Baku tower",
                 "source_page": "https://youtube.com/watch?v=abc", "media_path": str(local / "baku.mp4"),
                 "track_index": 1, "duration_frames": 50, "record_start_frame": 0, "record_end_frame": 50,
                 "source_start_frame": 0, "source_end_frame": 50},
                {"asset_id": "image:test", "beat_id": "beat_018", "title": "Baku photo",
                 "source_page": "", "media_path": str(local / "image.png"),
                 "track_index": 1, "duration_frames": 25, "record_start_frame": 50, "record_end_frame": 75,
                 "source_start_frame": 0, "source_end_frame": 25},
            ],
            "unavailable": [{"beat_id": "beat_019", "asset_id": "youtube:missing", "reason": "download failed"}]}
    dest = tmp_path / "export.zip"
    result = create_media_pack(
        dest, project_id="abc123", project_name="Baku",
        project_root=root, timeline=plan,
        generic_rows=[{"provider_id": "123", "place": "Baku", "title": "City",
                       "source_page": "https://www.pexels.com/video/123"}],
        selected_generics=["123"], selected_images=[{"beat_id":"beat_020", "asset_id":"other-image", "media_path":str(local / "image.png"), "title":"Extra image"}], captions_srt="1\n00:00:00,000 --> 00:00:01,000\nHello",
        titles=[{"text": "Baku", "start_seconds": 0}],
    )
    assert result["media_count"] == 4
    assert result["missing_count"] == 1
    with zipfile.ZipFile(dest) as zipf:
        names = set(zipf.namelist())
        assert any(name.startswith("01_FRASI/beat_017/") and name.endswith(".mp4") for name in names)
        assert any(name.startswith("01_FRASI/beat_018/") and name.endswith(".png") for name in names)
        assert any(name.startswith("01_FRASI/beat_020/") and name.endswith(".png") for name in names)
        assert "02_LUOGHI_E_GENERICI/Baku/pexels_123.mp4" in names
        assert "03_RESOLVE/timeline.xml" in names
        assert "03_RESOLVE/sottotitoli.srt" in names
        assert "03_RESOLVE/titoli_e_testi.json" in names
        manifest=json.loads(zipf.read("manifest.json"))
        assert manifest["resolve_drp_included"] is False
        assert manifest["missing"][0]["beat_id"] == "beat_019"
        assert "relink" in zipf.read("LEGGIMI.txt").decode().lower()


def test_media_pack_does_not_exfiltrate_external_file(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    secret = tmp_path / "private.txt"
    secret.write_text("PRIVATE SECRET")
    plan={"fps":25,"duration_frames":0,"clips":[{"beat_id":"beat_1","asset_id":"unsafe",
            "media_path":str(secret),"title":"outside"}],"unavailable":[]}
    dest=tmp_path/"output.zip"
    result=create_media_pack(dest,project_id="x",project_name="Test",
                             project_root=project,timeline=plan)
    assert result["media_count"] == 0
    assert result["missing_count"] == 1
    with zipfile.ZipFile(dest) as z:
        assert b"PRIVATE SECRET" not in z.read("manifest.json")


def test_media_pack_button_and_selective_skip_suppression():
    from backend.app.timeline_export_ui import JS, PANEL
    assert 'id="exportMediaPackV125"' in PANEL
    assert "ignoredCoverageIdsV123.add(id)" in JS
    assert "await prepareResolveHandoffV33(true)" in JS
    assert "if(!preserveIssues)renderResolveMediaIssuesV48([])" in JS
    assert "resolveComponentsV71=trimmed" not in JS
