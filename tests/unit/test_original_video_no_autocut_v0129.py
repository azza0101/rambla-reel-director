"""Uncut, user-uploaded video delivery to Resolve, independent of AutoCut."""
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.original_video_export import load_original_video, uncut_native_contract


def registered_project(tmp_path, *, has_audio=True):
    from backend.app.curation_project import ProjectStore

    def probe(_):
        return {"duration": 4.0, "fps": 30.0, "width": 1080, "height": 1920,
                "has_audio": has_audio}

    root = tmp_path / "projects"
    store = ProjectStore(root, probe_runner=probe)
    project = store.create("KURA already edited")
    media = tmp_path / "finished_premontato.mp4"
    media.write_bytes(b"source clip, unchanged")
    project = store.register_local_video(project.project_id, media)
    return store, project, media


def test_original_contract_contains_exactly_one_complete_uncut_av_segment(tmp_path):
    _, project, media = registered_project(tmp_path)
    original = load_original_video(project)
    contract = uncut_native_contract(original)
    assert original["source_path"] == str(media.resolve())
    assert original["fps"] == "30"
    assert original["has_audio"] is True
    assert original["duration_frames"] == 120
    assert contract["segments"] == [{
        "source_in_frame": 0, "source_out_frame": 120,
        "edited_in_frame": 0, "edited_out_frame": 120,
    }]
    assert contract["source_has_audio"] is True
    assert contract["alternatives"] == []
    assert contract["revision"] == "original-uncut"


def test_original_video_source_changed_after_registration_is_rejected(tmp_path):
    _, project, media = registered_project(tmp_path)
    media.write_bytes(b"modified after registering")
    with pytest.raises(ValueError, match="cambiato"):
        load_original_video(project)


@pytest.mark.parametrize("has_audio", [True, False])
def test_original_video_apply_creates_new_base_and_never_invokes_autocut(monkeypatch, tmp_path, has_audio):
    from backend.app import original_video_apply as app
    _, project_data, _ = registered_project(tmp_path, has_audio=has_audio)
    original = load_original_video(project_data)
    previous = SimpleNamespace(GetName=lambda: "Timeline 1",
                               GetUniqueId=lambda: "source-timeline")
    pool = object()
    project = SimpleNamespace(GetName=lambda: "Resolve Test",
                              GetCurrentTimeline=lambda: previous,
                              GetMediaPool=lambda: pool)
    manager = object()
    resolve = SimpleNamespace(GetProjectManager=lambda: manager)
    new_timeline = object()
    calls = []
    def create(_resolve, _project, payload, *, progress):
        cut = payload["native_cut"]
        assert payload["original_video_import"] is True
        assert len(cut["segments"]) == 1
        assert not cut["alternatives"]
        assert cut["source_has_audio"] is has_audio
        calls.append("native-import-uncut")
        progress(65, "Video originale importato")
        return {"timeline": new_timeline, "timeline_id": "new-base",
                "timeline_name": "RMBL ORIGINALE", "base_frame": 86400}
    monkeypatch.setattr("backend.app.resolve_native_cut.create_native_cut_base", create)
    monkeypatch.setattr("backend.app.resolve_native_cut.recover_native_cut_result", lambda *_: None)
    def verify(timeline, cut, base):
        assert timeline is new_timeline and base == 86400
        return {"video_count": 1, "audio_count": int(has_audio)}
    monkeypatch.setattr("backend.app.resolve_native_cut.verify_native_cut_base", verify)
    monkeypatch.setattr("backend.app.resolve_native_cut.record_native_cut_result",
                        lambda *_: calls.append("durable-checkpoint"))
    monkeypatch.setattr("backend.app.resolve_native_cut.delete_owned_native_cut",
                        lambda *_: pytest.fail("Valid import must not delete timeline"))
    def overlay(payload):
        calls.append("overlay")
        assert payload["destination_mode"] == "active"
        assert payload["source_timeline_id"] == "new-base"
        assert payload["native_cut_fresh"] is True
        assert payload["native_cut_fps"] == "30"
        assert "original_video" not in payload
        return {"status": "created", "timeline_id": "new-base", "timeline_name": "RMBL ORIGINALE"}
    result = app.materialize_original_video(
        resolve, project,
        {"original_video": original, "titles": [{"text": "Viaggio"}]},
        materialize_overlay=overlay,
        report=lambda *_: None,
        save_project=lambda manager_: calls.append("save"),
    )
    assert result["original_video"] is True
    assert result["video_count"] == 1
    assert result["audio_count"] == int(has_audio)
    assert result["destination_mode"] == "new"
    assert result["source_unchanged"] is True
    assert calls == ["native-import-uncut", "overlay", "save", "durable-checkpoint"]


def test_failed_overlay_rolls_back_only_new_video_timeline(monkeypatch, tmp_path):
    from backend.app import original_video_apply as app
    _, data, _ = registered_project(tmp_path)
    previous = SimpleNamespace(GetName=lambda: "Timeline 1",
                               GetUniqueId=lambda: "prior")
    pool = object()
    project = SimpleNamespace(GetName=lambda: "Resolve Test",
                              GetCurrentTimeline=lambda: previous,
                              GetMediaPool=lambda: pool)
    resolve = SimpleNamespace(GetProjectManager=lambda: object())
    owned = object()
    monkeypatch.setattr("backend.app.resolve_native_cut.recover_native_cut_result", lambda *_: None)
    monkeypatch.setattr("backend.app.resolve_native_cut.create_native_cut_base",
                        lambda *_args, **_kwargs: {"timeline": owned, "timeline_id": "new",
                                                  "timeline_name": "RMBL ORIGINALE", "base_frame": 86400})
    reverted = []
    def rollback(_p, received_pool, timeline, prior, payload):
        assert received_pool is pool and timeline is owned and prior is previous
        reverted.append(True)
    monkeypatch.setattr("backend.app.resolve_native_cut.delete_owned_native_cut", rollback)
    def fail_overlay(_):
        raise RuntimeError("Fusion failed")
    with pytest.raises(RuntimeError, match="Fusion failed"):
        app.materialize_original_video(
            resolve, project, {"original_video": load_original_video(data),
                               "titles": [{"text": "titolo"}]},
            materialize_overlay=fail_overlay,
            report=lambda *_: None,
            save_project=lambda *_: None,
        )
    assert reverted == [True]


def test_video_only_before_analysis_is_exposed_and_delivered(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.curation_server import create_app
    from backend.app import resolve_textplus_timeline

    store, project, _ = registered_project(tmp_path)
    calls = []
    monkeypatch.setattr(resolve_textplus_timeline, "run_resolve_helper",
                        lambda payload: calls.append(payload) or {"status": "created"})
    with TestClient(create_app(project_root=store.root)) as client:
        url = f"/api/curation/projects/{project.project_id}"
        options = client.get(url + "/export-options").json()
        assert options["source_video_available"] is True
        assert options["components"]["source_video"] is True
        assert options["components"]["video"] is False
        assert not any(options["components"][key] for key in
                       ("subtitles", "highlights", "broll", "social", "generic"))
        client.post("/api/curation/resolve-bridge/session", json={
            "bridge_session_id": "orig-session", "bridge_version": "v0129"})
        flags = {"video": False, "source_video": True, "subtitles": False,
                 "highlights": False, "broll": False, "social": False, "generic": False}
        assert client.put(url + "/export-options", json=flags).status_code == 200
        response = client.post(url + "/resolve-preparation", json=flags)
        assert response.status_code == 200, response.text
        job = response.json()
        for _ in range(150):
            job = client.get("/api/curation/resolve-preparation/" + job["job_id"]).json()
            if job["status"] != "preparing":
                break
            time.sleep(.01)
        assert job["status"] == "ready", job.get("message")
        assert job["package"]["summary"]["original_video"] is True
        assert job["package"]["summary"]["duration_seconds"] == 4.0
        package_id = job["package"]["package_id"]
        accepted = client.post("/api/curation/resolve-handoffs/" + package_id + "/received",
                               json={"bridge_session_id": "orig-session"})
        assert accepted.status_code == 200
        applied = client.post("/api/curation/resolve-handoffs/" + package_id + "/apply", json={
            "destination_mode": "active", "apply_scope": "all",
            "current_project": "Resolve Test", "current_timeline_id": "old-timeline"})
        assert applied.status_code == 200, applied.text
        for _ in range(150):
            status = client.get("/api/curation/resolve-handoffs/" + package_id + "/status").json()
            if status["status"] != "applying":
                break
            time.sleep(.01)
        assert status["status"] == "completed", status.get("error")
        assert calls[0]["destination_mode"] == "new"
        assert calls[0]["original_video"]["duration_frames"] == 120
        assert not calls[0].get("native_cut")
