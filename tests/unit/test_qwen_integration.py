import json

from backend.app.director_engine import build_edit_plan
from backend.app.director_preview import render_report
from backend.app.qwen_stack import QwenDirector, QwenMultimodalRanker, compose_qwen_plan, prepare_qwen_decisions


TRANSCRIPT = {"source": "clip.mov", "timeline_fps": 25, "segments": [
    {"start": 0, "end": 2, "text": "Parlo del workflow a nodi.", "words": []},
]}
OUTLINE = {"beats": [{"id": "nodes", "start_seconds": 0, "end_seconds": 2,
                      "intent": "spiegare nodi AI", "broll_queries": ["generic nodes"]}]}
ASSET = {"id": "workflow", "client_id": "rambla", "path": "C:/workflow.png",
         "description": "node graph workflow", "kind": "image"}


def test_qwen_proposal_and_multimodal_scores_reach_plan_and_html():
    generated = []

    def generate(prompt):
        generated.append(prompt)
        return json.dumps({"action": "BROLL", "query": "node graph workflow screenshot", "reason": "show visual process", "parameters": {"fit": "COVER"}})

    outline, director = prepare_qwen_decisions(TRANSCRIPT, OUTLINE, QwenDirector(generate))
    ranker = QwenMultimodalRanker(client_id="rambla", embed=lambda items: [[1.0, 0.0] for _ in items],
                                   rerank=lambda query, rows: [0.9] * len(rows))
    plan = build_edit_plan(TRANSCRIPT, outline, [ASSET], client_id="rambla", source_frames=50,
                           director=director, reranker=ranker)
    beat = plan["beats"][0]
    assert "Parlo del workflow" in generated[0]
    assert beat["action"] == "BROLL"
    assert "node graph workflow screenshot" in beat["broll_query"]
    assert beat["selected_asset"]["embedding_score"] == 1.0
    assert beat["selected_asset"]["reranker_score"] == 0.9
    assert beat["providers"]["director"] == "Qwen3.5-4B"
    html = render_report(plan)
    assert "Qwen3.5-4B" in html
    assert "Qwen3-VL-Embedding-2B" in html
    assert "Qwen3-VL-Reranker-2B" in html
    assert "0.9" in html


def test_invalid_qwen_output_falls_back_to_exact_heuristic_plan():
    original = build_edit_plan(TRANSCRIPT, OUTLINE, [ASSET], client_id="rambla", source_frames=50)
    outline, director = prepare_qwen_decisions(TRANSCRIPT, OUTLINE, QwenDirector(lambda prompt: "invalid"))
    fallback = build_edit_plan(TRANSCRIPT, outline, [ASSET], client_id="rambla", source_frames=50, director=director)
    assert fallback["beats"][0]["action"] == original["beats"][0]["action"]
    assert fallback["beats"][0]["broll_query"] == original["beats"][0]["broll_query"]
    assert fallback["beats"][0]["providers"]["director"] == "deterministic-rule-v1"


def test_asset_backed_qwen_action_without_candidate_falls_back():
    response = json.dumps({"action": "STICKER", "query": "no matching sticker", "reason": "add label", "parameters": {"label": "AI"}})
    outline, director = prepare_qwen_decisions(TRANSCRIPT, OUTLINE, QwenDirector(lambda prompt: response))
    plan = build_edit_plan(TRANSCRIPT, outline, [], client_id="rambla", source_frames=50, director=director)
    assert plan["beats"][0]["action"] == "TALKING_HEAD"
    assert plan["beats"][0]["providers"]["director"] == "deterministic-rule-v1"


def test_embedding_only_partial_plan_keeps_rule_director_and_provenance():
    plan = compose_qwen_plan(TRANSCRIPT, OUTLINE, [ASSET], client_id="rambla", source_frames=50,
                             embedder=lambda items: [[1.0, 0.0] for _ in items])
    beat = plan["beats"][0]
    assert beat["action"] == "BROLL"
    assert beat["providers"]["director"] == "deterministic-rule-v1"
    assert beat["providers"]["embedding"] == "Qwen3-VL-Embedding-2B"
    assert beat["providers"]["reranker"] is None
