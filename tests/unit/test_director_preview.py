import json

from backend.app.director_cli import run_from_artifacts
from backend.app.director_preview import render_report


def test_report_shows_every_beat_and_escapes_untrusted_transcript():
    plan = {
        "client_id": "rambla", "content_hash": "abc", "source": {"fps": 25, "duration_frames": 150},
        "beats": [
            {"id": "one", "start_frame": 0, "end_frame": 50, "transcript": "<script>alert(1)</script>",
             "action": "TALKING_HEAD", "rationale": "keep speaker", "broll_query": "", "selected_asset": None,
             "candidates": [], "caption_text": "hello"},
            {"id": "two", "start_frame": 50, "end_frame": 150, "transcript": "Workflow", "action": "BROLL",
             "rationale": "show proof", "broll_query": "workflow nodes", "selected_asset": {"id": "asset", "path": "C:/a.png", "score": 0.9},
             "candidates": [{"id": "asset", "score": 0.9, "reason": "metadata"}], "caption_text": "world"},
        ], "captions": [{"start_frame": 0, "end_frame": 150, "text": "hello world"}],
    }
    html = render_report(plan)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert "workflow nodes" in html
    assert "TALKING_HEAD" in html and "BROLL" in html
    assert "C:/a.png" in html
    assert "hello world" in html


def test_report_renders_online_candidate_gallery_without_secret_urls():
    remote = {
        "id": "pexels:42",
        "client_id": "rambla",
        "path": "Z:/cache/42.jpg",
        "preview_path": "Z:/cache/42.jpg",
        "score": 0.82,
        "embedding_score": 0.82,
        "reranker_score": None,
        "reason": "multimodal semantic embedding",
        "source": "pexels",
        "source_page": "https://www.pexels.com/video/42/",
        "provider_id": "42",
        "creator": {"name": "Alice", "profile_page": "https://www.pexels.com/@alice"},
        "rights_state": "provider_stock_terms",
        "query": "frustrated creative computer work",
        "selected_full_download": False,
        "selected_rendition_url": "https://cdn.pexels.com/full.mp4?token=SECRET",
        "providers": {"embedding": "Qwen3-VL-Embedding-2B", "reranker": None, "retrieval": "pexels"},
    }
    alternate = {**remote, "id": "pexels:43", "provider_id": "43", "score": 0.71, "embedding_score": 0.71,
                 "source_page": "https://www.pexels.com/video/43/", "preview_path": "Z:/cache/43.jpg", "path": "Z:/cache/43.jpg"}
    plan = {
        "client_id": "rambla",
        "content_hash": "hash",
        "source": {"fps": 25, "duration_frames": 100, "media": "reel.mp4"},
        "beats": [{
            "id": "beat-1", "start_frame": 0, "end_frame": 100,
            "transcript": "Passavo ore a fare tutto manualmente.", "action": "BROLL",
            "rationale": "visual evidence", "broll_query": "manual repetitive computer work",
            "selected_asset": remote, "candidates": [remote, alternate], "caption_text": "Passavo ore",
            "review_state": "AUTO_SELECTED",
            "providers": {"director": "rule", "embedding": "Qwen3-VL-Embedding-2B", "reranker": None, "retrieval": "pexels"},
        }],
        "captions": [{"start_frame": 0, "end_frame": 100, "text": "Passavo ore", "review_state": "ASR_UNREVIEWED"}],
    }

    html = render_report(plan)

    assert "Candidate review" in html
    assert "pexels:42" in html and "pexels:43" in html
    assert "SELECTED" in html
    assert "Qwen3-VL-Embedding-2B" in html
    assert "0.82" in html and "0.71" in html
    assert "Alice" in html
    assert "provider_stock_terms" in html
    assert "https://www.pexels.com/video/42/" in html
    assert "file:///Z:/cache/42.jpg" in html
    assert "cdn.pexels.com" not in html
    assert "token=SECRET" not in html


def test_report_renders_coverage_slot_proposal_a_b_with_crop_and_source_time():
    proposal_a = {
        "id": "youtube:abc", "source": "youtube", "provider_id": "abc",
        "source_page": "https://www.youtube.com/watch?v=abc", "preview_path": "Z:/cache/abc.jpg",
        "path": "Z:/cache/abc.jpg", "qwen_score": 0.91, "embedding_score": 0.91,
        "crop_score": 0.32, "final_score": 0.792, "crop_box": [0.34, 0.0, 0.66, 1.0],
        "needs_tracking": True, "rights_state": "review_required",
        "source_start_seconds": 75.0, "source_end_seconds": 78.5,
    }
    proposal_b = {
        "id": "pexels:43", "source": "pexels", "provider_id": "43",
        "source_page": "https://www.pexels.com/video/43/", "preview_path": "Z:/cache/43.jpg",
        "path": "Z:/cache/43.jpg", "qwen_score": 0.84, "embedding_score": 0.84,
        "crop_score": 1.0, "final_score": 0.872, "crop_box": [0.0, 0.0, 1.0, 1.0],
        "needs_tracking": False, "rights_state": "provider_stock_terms",
    }
    plan = {
        "client_id": "rambla", "content_hash": "hash",
        "source": {"fps": 25, "duration_frames": 100, "media": "reel.mp4"},
        "beats": [{
            "id": "beat-1", "start_frame": 0, "end_frame": 100, "transcript": "<b>source story</b>",
            "action": "BROLL", "rationale": "evidence", "broll_query": "source story", "selected_asset": None,
            "candidates": [], "caption_text": "source story", "review_state": "AUTO_SELECTED", "providers": {},
        }],
        "coverage_slots": [{
            "id": "beat-1:coverage:1", "beat_id": "beat-1", "start_frame": 6, "end_frame": 94,
            "start_seconds": 0.25, "end_seconds": 3.75, "visual_intent": "show exact evidence",
            "queries": ["exact source story"], "evidence_class": "exact_or_related_evidence", "minimum_proposals": 2,
            "proposal_A": proposal_a, "proposal_B": proposal_b, "proposal_C": None,
            "selected_proposal_id": "youtube:abc", "review_state": "READY",
        }],
        "captions": [{"start_frame": 0, "end_frame": 100, "text": "source story", "review_state": "ASR_UNREVIEWED"}],
    }

    html = render_report(plan)

    assert "Coverage review" in html
    assert "Proposal A" in html and "Proposal B" in html
    assert "youtube:abc" in html and "pexels:43" in html
    assert "Qwen 0.91" in html and "crop 0.32" in html
    assert "75.00–78.50s" in html
    assert "https://www.youtube.com/watch?v=abc" in html
    assert "&lt;b&gt;source story&lt;/b&gt;" in html
    assert "<b>source story</b>" not in html


def test_runtime_cli_persists_complete_offline_artifacts(tmp_path):
    transcript = {"source": "clip.mov", "timeline_fps": 25, "segments": [
        {"start": 0, "end": 2, "text": "Ciao.", "words": []},
        {"start": 2, "end": 4, "text": "Nodi workflow.", "words": []},
    ]}
    outline = {"beats": [
        {"id": "intro", "start_seconds": 0, "end_seconds": 2, "intent": "intro", "broll_queries": []},
        {"id": "nodes", "start_seconds": 2, "end_seconds": 4, "intent": "workflow nodes", "broll_queries": ["workflow nodes"]},
    ]}
    manifest = {"client_id": "rambla", "assets": [{"id": "nodes", "client_id": "rambla", "path": str(tmp_path / "nodes.png"), "description": "workflow nodes", "tags": [], "kind": "image"}]}
    (tmp_path / "nodes.png").write_bytes(b"asset")
    for name, value in (("transcript.json", transcript), ("outline.json", outline), ("manifest.json", manifest)):
        (tmp_path / name).write_text(json.dumps(value), encoding="utf-8")
    output = tmp_path / "run"
    plan = run_from_artifacts(tmp_path / "transcript.json", tmp_path / "outline.json", tmp_path / "manifest.json", output, source_frames=100)
    assert plan["source"]["duration_frames"] == 100
    assert json.loads((output / "edit-plan.json").read_text(encoding="utf-8"))["content_hash"] == plan["content_hash"]
    assert (output / "transcript-raw.json").exists()
    assert (output / "transcript-normalized.json").exists()
    assert (output / "semantic-beats.json").exists()
    assert "Nodi workflow" in (output / "review.html").read_text(encoding="utf-8")
