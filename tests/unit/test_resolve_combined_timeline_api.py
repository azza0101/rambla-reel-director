import json

from fastapi.testclient import TestClient

from backend.app.curation_project import ProjectStore
from backend.app.curation_server import create_app
from backend.app.transcript_intents import transcript_document


def client_with_selection(tmp_path):
    projects = tmp_path / "projects"
    store = ProjectStore(projects, probe_runner=lambda _: {})
    project = store.create("Combined")
    run = projects / project.project_id / "run"
    run.mkdir(parents=True, exist_ok=True)
    chunks = [{"id": "c1", "start": 0.0, "end": 1.0, "text": "Uno due", "words": [
        {"text": "Uno", "start": 0.0, "end": 0.5}, {"text": "due", "start": 0.5, "end": 1.0},
    ]}]
    (run / "semantic-chunks.json").write_text(json.dumps(chunks), encoding="utf-8")
    signature = transcript_document(run)["transcript_signature"]
    (run / "phrase-intents.json").write_text(json.dumps({
        "schema_version": "rambla-phrase-intents-1", "transcript_signature": signature,
        "phrases": {"c1": {"highlight": True, "highlighted_word_indices": [0]}},
    }), encoding="utf-8")
    return TestClient(create_app(project_root=projects)), project


def test_combined_timeline_route_forwards_titles_subtitles_and_template(tmp_path, monkeypatch):
    client, project = client_with_selection(tmp_path)
    captured = {}

    def fake(payload, **_):
        captured.update(payload)
        return {"status": "created", "title_count": 1, "subtitle_count": 1}

    monkeypatch.setattr("backend.app.resolve_textplus_timeline.run_resolve_helper", fake)
    response = client.post(f"/api/curation/projects/{project.project_id}/resolve/combined-timeline")

    assert response.status_code == 200, response.text
    assert captured["mode"] == "combined"
    assert [row["text"] for row in captured["titles"]] == ["Uno"]
    assert [row["text"] for row in captured["subtitles"]] == ["due"]
    assert captured["title_name"] == "KURA_paper_title_v8"
    assert captured["project_name"] == "Combined"
    assert captured["timeline_name"] == "Combined - SUBS + KEYWORDS TIMELINE v1"
    assert captured["media_bin_name"] == "TEMP"
    assert "RAMBLA_1_NATIVE_SUBS_" in captured["subtitle_srt_path"]


def test_combined_drt_route_streams_helper_output(tmp_path, monkeypatch):
    client, project = client_with_selection(tmp_path)

    def fake(payload, **_):
        target = payload["drt_output_path"]
        from pathlib import Path
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        with open(target, "wb") as stream:
            stream.write(b"DRT DATA")
        return {"status": "created", "drt_path": target}

    monkeypatch.setattr("backend.app.resolve_textplus_timeline.run_resolve_helper", fake)
    response = client.post(f"/api/curation/projects/{project.project_id}/resolve/combined-timeline.drt")

    assert response.status_code == 200, response.text
    assert response.content == b"DRT DATA"
    assert response.headers["content-disposition"].endswith('.drt"')


def test_combined_timeline_allows_subtitles_without_highlights(tmp_path, monkeypatch):
    client, project = client_with_selection(tmp_path)
    run = tmp_path / "projects" / project.project_id / "run"
    data = json.loads((run / "phrase-intents.json").read_text(encoding="utf-8"))
    data["phrases"]["c1"] = {"highlight": False, "highlighted_word_indices": []}
    (run / "phrase-intents.json").write_text(json.dumps(data), encoding="utf-8")
    captured = {}

    def fake(payload, **_):
        captured.update(payload)
        return {"status": "created"}

    monkeypatch.setattr("backend.app.resolve_textplus_timeline.run_resolve_helper", fake)
    response = client.post(f"/api/curation/projects/{project.project_id}/resolve/combined-timeline")

    assert response.status_code == 200, response.text
    assert captured["title_count"] == 0
    assert captured["titles"] == []
    assert [row["text"] for row in captured["subtitles"]] == ["Uno due"]


def test_each_resolve_export_uses_a_fresh_subtitle_source(tmp_path, monkeypatch):
    client, project = client_with_selection(tmp_path)
    paths = []

    def fake(payload, **_):
        paths.append(payload["subtitle_srt_path"])
        return {"status": "created"}

    monkeypatch.setattr("backend.app.resolve_textplus_timeline.run_resolve_helper", fake)
    assert client.post(f"/api/curation/projects/{project.project_id}/resolve/combined-timeline").status_code == 200
    assert client.post(f"/api/curation/projects/{project.project_id}/resolve/combined-timeline").status_code == 200
    assert paths[0] != paths[1]
