import copy

import pytest

from backend.app.director_engine import (
    FasterWhisperArtifact, PexelsProvider, PixabayProvider, build_edit_plan, validate_edit_plan,
)


TRANSCRIPT = {
    "timeline_fps": 25,
    "segments": [
        {"start": 0, "end": 2, "text": "Parlo in camera.", "words": []},
        {"start": 2, "end": 4, "text": "Ecco il workflow a nodi.", "words": []},
        {"start": 4, "end": 6, "text": "Seguimi per altri video.", "words": []},
    ],
}
OUTLINE = {
    "beats": [
        {"id": "intro", "start_seconds": 0, "end_seconds": 2, "intent": "presentazione personale", "broll_queries": []},
        {"id": "workflow", "start_seconds": 2, "end_seconds": 4, "intent": "mostrare il processo di produzione visuale a nodi", "broll_queries": ["node based AI video production workflow screenshot"]},
        {"id": "cta", "start_seconds": 4, "end_seconds": 6, "intent": "invito a seguire il canale", "broll_queries": []},
    ]
}
ASSETS = [
    {"id": "workflow-image", "client_id": "rambla", "path": "C:/client/workflow.png", "description": "AI video production node workflow screenshot", "tags": ["nodi", "processo"], "kind": "image"},
    {"id": "other-client", "client_id": "other", "path": "C:/other/workflow.png", "description": "perfect node workflow screenshot", "tags": ["workflow"], "kind": "image"},
]


def test_plan_covers_every_source_frame_and_is_reproducible():
    first = build_edit_plan(TRANSCRIPT, OUTLINE, ASSETS, client_id="rambla", source_frames=150)
    second = build_edit_plan(TRANSCRIPT, OUTLINE, ASSETS, client_id="rambla", source_frames=150)
    assert first == second
    assert [(b["start_frame"], b["end_frame"]) for b in first["beats"]] == [(0, 50), (50, 100), (100, 150)]
    assert first["beats"][0]["action"] == "TALKING_HEAD"
    assert first["beats"][1]["action"] == "BROLL"
    assert first["beats"][2]["action"] == "TALKING_HEAD"
    assert first["source"]["fps"] == 25
    validate_edit_plan(first)


def test_plan_persists_short_coverage_slots_without_replacing_legacy_beats():
    plan = build_edit_plan(TRANSCRIPT, OUTLINE, ASSETS, client_id="rambla", source_frames=150)

    assert len(plan["coverage_slots"]) == 1
    slot = plan["coverage_slots"][0]
    assert slot["beat_id"] == "workflow"
    assert slot["start_seconds"] == 2.0
    assert slot["end_seconds"] == 4.0
    assert slot["start_frame"] == 50
    assert slot["end_frame"] == 100
    assert slot["minimum_proposals"] == 2
    assert len(plan["beats"]) == 3
    validate_edit_plan(plan)


def test_retrieval_never_crosses_client_boundary_and_keeps_ranking_evidence():
    plan = build_edit_plan(TRANSCRIPT, OUTLINE, ASSETS, client_id="rambla", source_frames=150)
    beat = plan["beats"][1]
    assert beat["selected_asset"]["id"] == "workflow-image"
    assert beat["selected_asset"]["client_id"] == "rambla"
    assert all(row["client_id"] == "rambla" for row in beat["candidates"])
    assert beat["candidates"][0]["score"] > 0
    assert "workflow" in beat["broll_query"].lower()


def test_caption_coverage_uses_every_transcript_segment():
    plan = build_edit_plan(TRANSCRIPT, OUTLINE, ASSETS, client_id="rambla", source_frames=150)
    assert " ".join(c["text"] for c in plan["captions"]) == "Parlo in camera. Ecco il workflow a nodi. Seguimi per altri video."
    assert plan["captions"][0]["start_frame"] == 0
    assert plan["captions"][-1]["end_frame"] == 150
    assert all(c["emphasis_candidates"] is not None for c in plan["captions"])


def test_validator_rejects_gaps_and_cross_client_assets():
    plan = build_edit_plan(TRANSCRIPT, OUTLINE, ASSETS, client_id="rambla", source_frames=150)
    gap = copy.deepcopy(plan)
    gap["beats"][1]["start_frame"] = 51
    with pytest.raises(ValueError, match="coverage"):
        validate_edit_plan(gap)
    leaked = copy.deepcopy(plan)
    leaked["beats"][1]["selected_asset"]["client_id"] = "other"
    with pytest.raises(ValueError, match="client"):
        validate_edit_plan(leaked)


def test_validator_rejects_coverage_slot_outside_source():
    plan = build_edit_plan(TRANSCRIPT, OUTLINE, ASSETS, client_id="rambla", source_frames=150)
    broken = copy.deepcopy(plan)
    broken["coverage_slots"][0]["end_frame"] = 151
    with pytest.raises(ValueError, match="coverage slot"):
        validate_edit_plan(broken)


def test_generic_brand_overlap_does_not_insert_workflow_visual_everywhere():
    outline = {"beats": [
        {"id": "brand", "start_seconds": 0, "end_seconds": 2, "intent": "Rambla Studio film production", "broll_queries": ["Rambla Studio video production behind the scenes"]},
        {"id": "nodes", "start_seconds": 2, "end_seconds": 4, "intent": "workflow a nodi", "broll_queries": ["node based AI video production workflow screenshot"]},
        {"id": "cta", "start_seconds": 4, "end_seconds": 6, "intent": "Rambla Studio call to action", "broll_queries": ["Rambla Studio brand call to action"]},
    ]}
    asset = {"id": "nodes", "client_id": "rambla", "path": "C:/RamblaStudio/workflow.png", "description": "Rambla Studio AI video production node workflow screenshot", "tags": ["node", "workflow"], "kind": "image"}
    plan = build_edit_plan(TRANSCRIPT, outline, [asset], client_id="rambla", source_frames=150)
    assert [beat["action"] for beat in plan["beats"]] == ["TALKING_HEAD", "BROLL", "TALKING_HEAD"]


def test_asr_artifact_adapter_preserves_word_timestamps(tmp_path):
    import json

    path = tmp_path / "asr.json"
    path.write_text(json.dumps(TRANSCRIPT), encoding="utf-8")
    assert FasterWhisperArtifact(path).load()["segments"][1]["start"] == 2
    assert FasterWhisperArtifact(path).load()["segments"][1]["words"] == []


def test_stock_providers_stop_at_missing_credential_boundary():
    assert PexelsProvider().list_assets("rambla") == []
    assert PixabayProvider().list_assets("rambla") == []
    assert PexelsProvider().availability() == "CREDENTIAL_REQUIRED"
    assert PixabayProvider().availability() == "CREDENTIAL_REQUIRED"
