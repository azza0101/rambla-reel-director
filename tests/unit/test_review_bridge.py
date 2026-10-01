import json
from pathlib import Path
import shutil
import uuid

import pytest

from backend.app.review_bridge import apply_review_submission, build_review_payload
from backend.app.transcript_intents import load_phrase_intents


@pytest.fixture
def run():
    root = Path(f".review-bridge-test-{uuid.uuid4().hex}")
    root.mkdir()
    chunks = [{
        "id": "c1", "start": 0.0, "end": 2.0, "text": "Una frase semplice",
        "words": [
            {"start": 0.0, "end": 0.6, "text": "Una"},
            {"start": 0.6, "end": 1.2, "text": "frase"},
            {"start": 1.2, "end": 2.0, "text": "semplice"},
        ],
    }]
    (root / "semantic-chunks.json").write_text(json.dumps(chunks), encoding="utf-8")
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_review_payload_contains_only_timed_transcript_and_selections(run):
    payload = build_review_payload(run, "project-1", "Demo")
    assert payload["schema_version"] == "rambla-transcript-review-1"
    assert payload["project_label"] == "Demo"
    assert payload["chunks"][0]["words"][1]["text"] == "frase"
    assert payload["intents"]["c1"]["coverage_word_indices"] == []
    serialized = json.dumps(payload)
    assert "source_video" not in serialized
    assert "api_key" not in serialized.casefold()


def test_review_submission_replaces_persistent_word_selections(run):
    signature = load_phrase_intents(run)["transcript_signature"]
    result = apply_review_submission(run, {
        "schema_version": "rambla-transcript-review-submission-1",
        "transcript_signature": signature,
        "changes": {"c1": {
            "coverage_word_indices": [0, 1],
            "animation_word_indices": [2],
            "highlighted_word_indices": [1],
        }},
    })
    assert result["phrases"]["c1"]["coverage_word_indices"] == [0, 1]
    assert result["phrases"]["c1"]["animation_word_indices"] == [2]
    assert result["phrases"]["c1"]["highlighted_word_indices"] == [1]


def test_review_submission_rejects_an_obsolete_transcript(run):
    with pytest.raises(ValueError, match="Transcript changed"):
        apply_review_submission(run, {
            "schema_version": "rambla-transcript-review-submission-1",
            "transcript_signature": "old",
            "changes": {"c1": {"coverage_word_indices": [0]}},
        })


def test_product_page_exposes_simple_review_link_controls():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    page = render_curation_page_v2("review-bridge")
    for element_id in ("publishReviewV19", "copyReviewLinkV19", "pullReviewV19", "onlineReviewStatusV19"):
        assert f'id="{element_id}"' in page
    assert "/review/publish" in page
    assert "/review/pull" in page
    assert "AGGIORNA DAL REVISORE" in page


def test_review_routes_publish_and_apply_the_latest_delivery():
    from fastapi.testclient import TestClient
    from backend.app.curation_project import ProjectStore
    from backend.app.curation_server import create_app

    root = Path(f".review-route-test-{uuid.uuid4().hex}")
    root.mkdir()
    probe = lambda _: {"duration": 2, "fps": 25, "width": 1080, "height": 1920, "has_audio": False}
    store = ProjectStore(root, probe_runner=probe)
    project = store.create("Shared demo")
    run = root / project.project_id / "run"
    run.mkdir()
    chunks = [{"id": "c1", "start": 0.0, "end": 2.0, "text": "Una frase", "words": [
        {"start": 0.0, "end": 1.0, "text": "Una"}, {"start": 1.0, "end": 2.0, "text": "frase"},
    ]}]
    (run / "semantic-chunks.json").write_text(json.dumps(chunks), encoding="utf-8")

    class FakeBridge:
        configured = True
        submission = None

        async def publish(self, payload):
            self.payload = payload
            return {"review_id": "review-1", "review_url": "https://example.test/review-1", "submitted_revision": 0}

        async def pull(self, review_id):
            return {"ok": True, "submitted_revision": 1, "submission": self.submission}

    bridge = FakeBridge()
    try:
        client = TestClient(create_app(project_root=root, allowed_media_roots=[root], probe_runner=probe, review_bridge_client=bridge))
        published = client.post(f"/api/curation/projects/{project.project_id}/review/publish")
        assert published.status_code == 200
        signature = bridge.payload["transcript_signature"]
        bridge.submission = {
            "schema_version": "rambla-transcript-review-submission-1",
            "transcript_signature": signature,
            "changes": {"c1": {
                "coverage_word_indices": [0, 1],
                "animation_word_indices": [],
                "highlighted_word_indices": [1],
            }},
        }
        pulled = client.post(f"/api/curation/projects/{project.project_id}/review/pull")
        assert pulled.status_code == 200
        assert pulled.json()["updated"] is True
        assert load_phrase_intents(run)["phrases"]["c1"]["highlighted_word_indices"] == [1]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_apps_script_template_is_a_complete_web_app():
    source = Path("tools/google_apps_script_review_bridge/Code.gs").read_text(encoding="utf-8")
    for marker in ("function doGet", "function doPost", "function loadReview", "function submitReview"):
        assert marker in source
    assert "DriveApp" in source
    assert "INVIA MODIFICHE" in source
    assert "google.script.url.getLocation" in source
    assert "new URLSearchParams(location.search)" not in source
    source.encode("ascii")
    assert ".word{display:inline;padding:1px 0;margin:0;" in source


def test_single_powershell_setup_is_resumable_and_finishes_local_configuration():
    source = Path("SETUP_REVISIONE_ONLINE.ps1").read_text(encoding="utf-8")
    assert "Code.gs" in source
    assert "RAMBLA_REVIEW_OWNER_SECRET" in source
    assert "RAMBLA_REVIEW_WEBAPP_URL" in source
    assert "https://script.google.com/home/projects/create" in source
    assert "Set-Clipboard" in source
    assert "launch_local_v5.py" in source
    assert "publishReviewV19" in source
    assert "ExecutionPolicy Bypass" in source
