import json
from pathlib import Path


def _store(tmp_path):
    from backend.app.curation_project import ProjectStore

    return ProjectStore(
        tmp_path / "projects",
        probe_runner=lambda _: {
            "duration": 12.5,
            "fps": 25.0,
            "width": 1920,
            "height": 1080,
            "has_audio": True,
        },
        audio_probe_runner=lambda _: 12.5,
    )


def test_project_save_always_writes_openable_rambla_manifest(tmp_path):
    store = _store(tmp_path)
    project = store.create("KURA reel")

    manifest = store.manifest_path(project.project_id)
    assert manifest.name == "project.rambla.json"
    assert manifest.is_file()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "rambla-project-1"
    assert payload["project_id"] == project.project_id
    assert payload["name"] == "KURA reel"
    assert payload["analysis_signature"] == project.analysis_signature


def test_manifest_reopens_existing_project_without_creating_or_analyzing(tmp_path):
    store = _store(tmp_path)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    project = store.register_local_video(store.create("KURA reel").project_id, source)

    opened = store.load_manifest(store.manifest_path(project.project_id))
    assert opened.project_id == project.project_id
    assert opened.source_video.path == str(source.resolve())
    assert opened.analysis_signature == project.analysis_signature


def test_manifest_rejects_wrong_store_or_tampered_project_id(tmp_path):
    import pytest

    store = _store(tmp_path)
    project = store.create("Demo")
    payload = json.loads(store.manifest_path(project.project_id).read_text(encoding="utf-8"))
    payload["project_id"] = "deadbeefdead"
    bad = tmp_path / "bad.rambla.json"
    bad.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises((FileNotFoundError, ValueError)):
        store.load_manifest(bad)


def test_recent_projects_are_sorted_by_manifest_mtime(tmp_path):
    store = _store(tmp_path)
    first = store.create("First")
    second = store.create("Second")
    first_path = store.manifest_path(first.project_id)
    second_path = store.manifest_path(second.project_id)
    first_path.touch()
    second_path.touch()
    # Force deterministic ordering independent of filesystem timestamp precision.
    import os
    os.utime(first_path, (1, 1))
    os.utime(second_path, (2, 2))

    recent = store.list_recent(limit=10)
    assert [row["project_id"] for row in recent[:2]] == [second.project_id, first.project_id]
