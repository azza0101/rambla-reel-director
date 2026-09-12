import json

import backend.app.director_benchmark as benchmark_module
from backend.app.director_benchmark import benchmark, run_from_files
from backend.app.qwen_stack import QwenConfig


TRANSCRIPT = {"source": "clip.mov", "timeline_fps": 25, "segments": [
    {"start": 0, "end": 2, "text": "Workflow nodi", "words": []},
]}
OUTLINE = {"beats": [{"id": "nodes", "start_seconds": 0, "end_seconds": 2,
                      "intent": "workflow", "broll_queries": ["node workflow screenshot"]}]}
ASSETS = [{"id": "nodes", "client_id": "rambla", "path": "C:/nodes.png",
           "description": "node workflow screenshot", "tags": [], "kind": "image"}]


def test_benchmark_does_not_claim_qwen_inference_when_weights_missing(tmp_path):
    report = benchmark(TRANSCRIPT, OUTLINE, ASSETS, client_id="rambla", source_frames=50,
                       config=QwenConfig(model_root=tmp_path))
    assert report["heuristic"]["status"] == "COMPLETE"
    assert report["qwen"]["status"] == "UNAVAILABLE"
    assert report["qwen"]["models_exercised"] == []
    assert report["qwen"]["duration_ms"] is None
    assert "director" in report["qwen"]["blockers"]
    assert report["same_input"]["beat_ids"] == ["nodes"]


def test_benchmark_cli_persists_report_without_resolve(tmp_path):
    paths = []
    for name, value in (("transcript.json", TRANSCRIPT), ("outline.json", OUTLINE),
                        ("manifest.json", {"client_id": "rambla", "assets": ASSETS})):
        path = tmp_path / name
        path.write_text(json.dumps(value), encoding="utf-8")
        paths.append(path)
    output = tmp_path / "report.json"
    report = run_from_files(*paths, output_path=output, model_root=tmp_path / "models", source_frames=50)
    assert json.loads(output.read_text(encoding="utf-8"))["qwen"]["status"] == "UNAVAILABLE"
    assert report["heuristic"]["beat_count"] == 1


def test_benchmark_runs_only_available_embedding_role_with_fallbacks(tmp_path, monkeypatch):
    class TestEmbedder:
        def __init__(self, config):
            self.model = None
            self.completed_calls = 0

        def __call__(self, items):
            self.model = object()
            self.completed_calls += 1
            return [[1.0, 0.0] for _ in items]

    monkeypatch.setattr(benchmark_module, "LocalQwenEmbedder", TestEmbedder)
    monkeypatch.setattr(benchmark_module, "capabilities", lambda config: {
        role: {"available": role == "embedding", "reason": "missing" if role != "embedding" else "ready"}
        for role in ("director", "embedding", "reranker")
    })
    report = benchmark(TRANSCRIPT, OUTLINE, ASSETS, client_id="rambla", source_frames=50,
                       config=QwenConfig(model_root=tmp_path))
    assert report["qwen"]["status"] == "PARTIAL_COMPLETE"
    assert report["qwen"]["models_exercised"] == ["Qwen3-VL-Embedding-2B"]
    assert report["qwen"]["decisions"][0]["providers"]["director"] == "deterministic-rule-v1"


def test_loaded_but_failed_director_is_not_reported_as_exercised(tmp_path, monkeypatch):
    class FailedGenerator:
        def __init__(self, config):
            self.model = object()
            self.completed_calls = 0

        def __call__(self, prompt):
            raise RuntimeError("inference failed")

    monkeypatch.setattr(benchmark_module, "LocalQwenDirectorGenerator", FailedGenerator)
    monkeypatch.setattr(benchmark_module, "capabilities", lambda config: {
        role: {"available": role == "director", "reason": "missing" if role != "director" else "ready"}
        for role in ("director", "embedding", "reranker")
    })
    report = benchmark(TRANSCRIPT, OUTLINE, ASSETS, client_id="rambla", source_frames=50,
                       config=QwenConfig(model_root=tmp_path))
    assert report["qwen"]["status"] == "FAILED_FALLBACK"
    assert report["qwen"]["models_exercised"] == []
