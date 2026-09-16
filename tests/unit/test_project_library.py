import json
import os
from pathlib import Path

import pytest


def _store(tmp_path):
    from backend.app.curation_project import ProjectStore
    return ProjectStore(
        tmp_path / "projects",
        probe_runner=lambda _: {"duration": 10, "fps": 25, "width": 1080, "height": 1920, "has_audio": False},
        audio_probe_runner=lambda _: 10.0,
    )


def test_project_library_reports_size_source_and_state_and_sorts_recent_first(tmp_path):
    from backend.app.project_maintenance import project_library_rows

    store = _store(tmp_path)
    first = store.create("First")
    second = store.create("Second")
    source = tmp_path / "source.mp4"; source.write_bytes(b"video")
    store.register_local_video(second.project_id, source)

    run = store.root / second.project_id / "run"
    run.mkdir(parents=True)
    (run / "transcript-raw.json").write_text("{}", encoding="utf-8")
    (run / "visual-plan.json").write_text('{"schema_version":"rambla-visual-plan-1"}', encoding="utf-8")
    (run / "cache.bin").write_bytes(b"x" * 33)
    os.utime(store.manifest_path(first.project_id), (1, 1))
    os.utime(store.manifest_path(second.project_id), (2, 2))

    rows = project_library_rows(store)
    assert [row["project_id"] for row in rows[:2]] == [second.project_id, first.project_id]
    row = rows[0]
    assert row["name"] == "Second"
    assert row["source_filename"] == "source.mp4"
    assert row["size_bytes"] >= 33
    assert row["file_count"] >= 4
    assert row["has_transcript"] is True
    assert row["has_editorial_plan"] is True
    assert row["modified_at"]


def test_rename_project_updates_project_and_manifest_without_changing_identity(tmp_path):
    from backend.app.project_maintenance import rename_project

    store = _store(tmp_path)
    project = store.create("Old name")
    before_signature = project.analysis_signature

    renamed = rename_project(store, project.project_id, "  KURA Thailand  ")
    assert renamed.project_id == project.project_id
    assert renamed.name == "KURA Thailand"
    assert renamed.analysis_signature == before_signature
    assert store.load(project.project_id).name == "KURA Thailand"
    manifest = json.loads(store.manifest_path(project.project_id).read_text(encoding="utf-8"))
    assert manifest["name"] == "KURA Thailand"

    with pytest.raises(ValueError):
        rename_project(store, project.project_id, "   ")
    with pytest.raises(ValueError):
        rename_project(store, project.project_id, "x" * 121)


def test_delete_project_tree_is_scoped_and_reports_freed_storage(tmp_path):
    from backend.app.project_maintenance import delete_project_tree

    store = _store(tmp_path)
    victim = store.create("Delete me")
    survivor = store.create("Keep me")
    nested = store.root / victim.project_id / "run" / "clips"
    nested.mkdir(parents=True)
    (nested / "clip.mp4").write_bytes(b"123456789")

    result = delete_project_tree(store, victim.project_id)
    assert result["project_id"] == victim.project_id
    assert result["deleted_bytes"] >= 9
    assert result["deleted_files"] >= 3
    assert result["resolve_calls"] == 0
    assert not (store.root / victim.project_id).exists()
    assert (store.root / survivor.project_id / "project.json").is_file()

    with pytest.raises(ValueError):
        delete_project_tree(store, "../../outside")
