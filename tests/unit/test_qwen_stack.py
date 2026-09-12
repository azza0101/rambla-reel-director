import json
import os

import pytest

from backend.app.qwen_stack import (
    QwenConfig, QwenDirector, QwenMultimodalRanker, QwenVisualJudge,
    LocalQwenASR, LocalQwenDirectorGenerator, LocalQwenEmbedder, LocalQwenReranker, QwenMetadataReranker,
    ModelUnavailable, RETRIEVAL_INSTRUCTION, capabilities, offline_model_environment,
)


def test_missing_local_weights_report_unavailable_without_loading_or_download(tmp_path):
    config = QwenConfig(model_root=tmp_path)
    state = capabilities(config)
    assert state["director"]["available"] is False
    assert state["embedding"]["available"] is False
    assert "weights" in state["embedding"]["reason"]
    assert state["embedding"]["weights_present"] is False
    assert state["embedding"]["package_present"] is False


def test_director_repairs_invalid_json_once_then_accepts_closed_payload():
    calls = []

    def generate(prompt):
        calls.append(prompt)
        if len(calls) == 1:
            return '{"action":"BROLL","query":"nodes"}'
        return json.dumps({"action": "BROLL", "query": "node graph AI workflow screenshot", "reason": "visual proof", "parameters": {"fit": "COVER"}})

    director = QwenDirector(generate)
    proposal = director.propose({"id": "beat-1", "intent": "workflow", "transcript": "nodi"})
    assert proposal["query"] == "node graph AI workflow screenshot"
    assert len(calls) == 2
    assert "invalid" in calls[1].lower()


def test_director_falls_back_after_bounded_invalid_outputs():
    calls = []
    director = QwenDirector(lambda prompt: calls.append(prompt) or "not json")
    assert director.propose({"id": "beat-1", "intent": "workflow", "transcript": "nodi"}) is None
    assert len(calls) == 2
    assert director.last_status == "INVALID_OUTPUT_FALLBACK"


def test_multimodal_ranker_rejects_cross_client_before_encoding():
    calls = []
    ranker = QwenMultimodalRanker(client_id="rambla", embed=lambda items: calls.append(items) or [[1, 0]],
                                   rerank=lambda query, rows: [0.9] * len(rows))
    with pytest.raises(ValueError, match="client"):
        ranker.rank("nodes", [{"id": "foreign", "client_id": "other", "path": "C:/other.png", "description": "nodes"}])
    assert calls == []


def test_multimodal_ranker_records_embedding_reranker_scores_and_provider():
    def embed(items):
        return [[1.0, 0.0] if item == "workflow nodes" else [0.8, 0.6] for item in items]

    ranker = QwenMultimodalRanker(client_id="rambla", embed=embed,
                                   rerank=lambda query, rows: [0.75] * len(rows))
    rows = ranker.rank("workflow nodes", [{"id": "nodes", "client_id": "rambla", "path": "C:/nodes.png",
                                            "description": "node graph", "kind": "image"}])
    assert rows[0]["embedding_score"] == 0.8
    assert rows[0]["reranker_score"] == 0.75
    assert rows[0]["providers"]["embedding"] == "Qwen3-VL-Embedding-2B"
    assert rows[0]["providers"]["reranker"] == "Qwen3-VL-Reranker-2B"


def test_visual_judge_is_disabled_by_default():
    calls = []
    judge = QwenVisualJudge(lambda beat, asset: calls.append(asset) or True)
    assert judge.check({"intent": "nodes"}, {"id": "nodes"}) is None
    assert calls == []


def test_local_runtime_adapters_refuse_missing_weights_before_import(tmp_path):
    config = QwenConfig(model_root=tmp_path)
    for adapter in (LocalQwenASR(config), LocalQwenDirectorGenerator(config),
                    LocalQwenEmbedder(config), LocalQwenReranker(config)):
        with pytest.raises(ModelUnavailable, match="local weights"):
            adapter.load()


def test_model_path_cannot_escape_runtime_root(tmp_path):
    with pytest.raises(ValueError, match="unsupported Director"):
        QwenConfig(model_root=tmp_path, director_model="../../foreign").path("director")


def test_director_generation_exception_falls_back_without_retry_storm():
    calls = []

    def broken(prompt):
        calls.append(prompt)
        raise RuntimeError("GPU unavailable")

    director = QwenDirector(broken)
    assert director.propose({"id": "beat", "intent": "nodes", "transcript": "nodes"}) is None
    assert len(calls) == 1
    assert director.last_status == "PROVIDER_ERROR_FALLBACK"


def test_reranker_score_must_be_normalized_probability():
    ranker = QwenMultimodalRanker(client_id="rambla", embed=lambda items: [[1, 0] for _ in items],
                                   rerank=lambda query, rows: [4.2])
    with pytest.raises(ValueError, match="reranker.*scores"):
        ranker.rank("nodes", [{"id": "nodes", "client_id": "rambla", "path": "C:/nodes.png", "kind": "image"}])


def test_video_asset_needs_explicit_keyframe_instead_of_text_encoding_filename():
    calls = []
    ranker = QwenMultimodalRanker(client_id="rambla", embed=lambda items: calls.append(items) or [[1, 0] for _ in items],
                                   rerank=lambda query, rows: [0.8])
    with pytest.raises(ValueError, match="keyframe"):
        ranker.rank("behind the scenes", [{"id": "video", "client_id": "rambla", "path": "C:/asset.mp4", "kind": "video"}])
    assert calls == []


def test_capability_rejects_partial_sharded_model(tmp_path):
    model = tmp_path / "Qwen3.5-4B"
    model.mkdir()
    (model / "config.json").write_text("{}", encoding="utf-8")
    (model / "model-00001-of-00002.safetensors").write_bytes(b"partial")
    (model / "model.safetensors.index.json").write_text(
        json.dumps({"weight_map": {"a": "model-00001-of-00002.safetensors", "b": "model-00002-of-00002.safetensors"}}),
        encoding="utf-8",
    )
    assert capabilities(QwenConfig(model_root=tmp_path))["director"]["reason"] == "local weights missing or incomplete"


def test_director_rejects_action_specific_parameter_mismatch():
    director = QwenDirector(lambda prompt: json.dumps({"action": "PUNCH_IN", "query": "", "reason": "emphasize hook", "parameters": {"fit": "COVER"}}))
    assert director.propose({"id": "hook", "intent": "hook", "transcript": "hello"}) is None
    assert director.last_status == "INVALID_OUTPUT_FALLBACK"


def test_embedding_only_path_does_not_require_reranker():
    ranker = QwenMultimodalRanker(client_id="rambla", embed=lambda items: [[1, 0] for _ in items], rerank=None)
    rows = ranker.rank("nodes", [{"id": "nodes", "client_id": "rambla", "path": "C:/nodes.png", "kind": "image"}])
    assert rows[0]["score"] == 1.0
    assert rows[0]["embedding_score"] == 1.0
    assert rows[0]["reranker_score"] is None
    assert rows[0]["providers"]["reranker"] is None


def test_reranker_only_path_uses_client_local_metadata_candidates():
    ranker = QwenMetadataReranker(client_id="rambla", rerank=lambda query, rows: [0.9])
    rows = ranker.rank("node workflow screenshot", [{"id": "nodes", "client_id": "rambla",
                                                     "path": "C:/nodes.png", "description": "node workflow screenshot", "tags": [], "kind": "image"}])
    assert rows[0]["embedding_score"] is None
    assert rows[0]["reranker_score"] == 0.9
    assert rows[0]["providers"]["reranker"] == "Qwen3-VL-Reranker-2B"


def test_model_cache_environment_is_runtime_local_and_restored(tmp_path):
    before = {key: os.environ.get(key) for key in ("HF_HOME", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")}
    with offline_model_environment(tmp_path):
        assert os.environ["HF_HOME"] == str(tmp_path / ".hf-cache")
        assert os.environ["HF_HUB_OFFLINE"] == "1"
        assert os.environ["TRANSFORMERS_OFFLINE"] == "1"
    assert {key: os.environ.get(key) for key in before} == before


def _complete_embedding_config(tmp_path, *, with_code_root=False):
    model = tmp_path / "Qwen3-VL-Embedding-2B"
    model.mkdir()
    (model / "config.json").write_text("{}", encoding="utf-8")
    (model / "model.safetensors").write_bytes(b"weights")
    code_root = None
    if with_code_root:
        code_root = tmp_path / "qwen-code"
        module = code_root / "src" / "models"
        module.mkdir(parents=True)
        (module / "qwen3_vl_embedding.py").write_text("class Qwen3VLEmbedder: pass\n", encoding="utf-8")
    return QwenConfig(model_root=tmp_path, embedding_code_root=code_root)


def test_embedding_capability_accepts_explicit_official_source_root(tmp_path):
    config = _complete_embedding_config(tmp_path, with_code_root=True)
    state = capabilities(config)["embedding"]
    assert state["weights_present"] is True
    assert state["package_present"] is True
    assert state["available"] is True


def test_local_qwen_embedder_uses_official_process_payload(tmp_path):
    config = _complete_embedding_config(tmp_path)

    class FakeOfficialEmbedder:
        def __init__(self):
            self.seen = None

        def process(self, payload):
            self.seen = payload
            return [[1.0, 0.0], [0.0, 1.0]]

    fake = FakeOfficialEmbedder()
    adapter = LocalQwenEmbedder(config, factory=lambda path: fake)
    image_path = tmp_path / "frame.jpg"
    vectors = adapter(["semantic query", str(image_path)])

    assert fake.seen == [
        {"text": "semantic query", "instruction": RETRIEVAL_INSTRUCTION},
        {"image": str(image_path)},
    ]
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]
    assert adapter.completed_calls == 1
