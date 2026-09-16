import json
from pathlib import Path


def _write(path: Path, data=b"x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, (dict, list)):
        path.write_text(json.dumps(data), encoding="utf-8")
    else:
        path.write_bytes(data)


def test_clean_project_media_preserves_analysis_plan_and_decisions_but_removes_retrieval(tmp_path):
    from backend.app.project_maintenance import clean_project_media

    run = tmp_path / "run"
    retrieval = run / "editorial" / "digest123"
    durable = {
        "transcript-raw.json": {"segments": [{"text": "hello"}]},
        "transcript-normalized.json": {"segments": []},
        "semantic-chunks.json": [{"id": "b1", "text": "hello"}],
        "analysis-signature.json": {"analysis_signature": "sig"},
        "visual-plan.json": {"schema_version": "rambla-visual-plan-1"},
    }
    for name, payload in durable.items():
        _write(run / name, payload)
    snapshots = {name: (run / name).read_bytes() for name in durable}

    _write(retrieval / "imported-plan.json", {"schema_version": "rambla-visual-plan-1"})
    _write(retrieval / "online-candidates.json", [{"parent_beat_id": "b1", "candidates": [{"id": "yt:1"}]}])
    _write(retrieval / "image-candidates.json", {"chunks": {"b1": {"candidates": [{"id": "px:1"}]}}})
    _write(retrieval / "video-retrieval-plan.json", {})
    _write(retrieval / "online-sourcing-benchmark.json", {})
    _write(retrieval / "asset-cache" / "quality-clips" / "one.mp4", b"123456")
    _write(retrieval / "image-cache" / "one.jpg", b"123")
    _write(retrieval / "selection-plan.json", {
        "schema_version": "curation-selection-1", "resolve_calls": 0,
        "chunks": {
            "b1": {"chunk_id": "b1", "no_broll": False, "selected_assets": [{"asset_id": "yt:1", "order": 0, "track": "V2"}]},
            "b2": {"chunk_id": "b2", "no_broll": True, "selected_assets": []},
            "b3": {"chunk_id": "b3", "no_broll": False, "action": "CONTINUE_PREVIOUS_VISUAL", "continuation_from": "b1", "selected_assets": []},
        },
    })

    result = clean_project_media(run, retrieval)

    assert result["deleted_files"] >= 6
    assert result["deleted_bytes"] >= 9
    assert result["cleared_selections"] == 1
    assert result["preserved_decisions"] == 2
    assert result["resolve_calls"] == 0
    assert (retrieval / "imported-plan.json").is_file()
    assert not (retrieval / "online-candidates.json").exists()
    assert not (retrieval / "asset-cache").exists()
    selection = json.loads((retrieval / "selection-plan.json").read_text(encoding="utf-8"))
    assert selection["chunks"]["b1"]["selected_assets"] == []
    assert selection["chunks"]["b2"]["no_broll"] is True
    assert selection["chunks"]["b3"]["action"] == "CONTINUE_PREVIOUS_VISUAL"
    for name, before in snapshots.items():
        assert (run / name).read_bytes() == before


def test_clean_media_fallback_run_root_uses_allowlist_and_never_deletes_analysis(tmp_path):
    from backend.app.project_maintenance import clean_project_media

    run = tmp_path / "run"
    _write(run / "transcript-raw.json", {"segments": []})
    _write(run / "semantic-chunks.json", [])
    _write(run / "visual-plan.json", {"schema_version": "legacy-or-experimental"})
    _write(run / "online-candidates.json", [])
    _write(run / "image-candidates.json", {"chunks": {}})
    _write(run / "asset-cache" / "clip.mp4", b"media")

    clean_project_media(run, run)

    assert (run / "transcript-raw.json").is_file()
    assert (run / "semantic-chunks.json").is_file()
    assert (run / "visual-plan.json").is_file()
    assert not (run / "online-candidates.json").exists()
    assert not (run / "image-candidates.json").exists()
    assert not (run / "asset-cache").exists()
