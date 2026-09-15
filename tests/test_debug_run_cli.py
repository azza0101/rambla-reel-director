import shutil
import uuid
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from backend.app.debug_run_cli import (
    build_short_outline,
    discover_image_candidates,
    has_concrete_visual_video_artifact,
    has_editorial_artifacts,
    normalize_faster_whisper,
    run_asr_stage,
)


def test_image_discovery_retries_zero_cache_and_persists_qwen_ranked_coverage():
    from backend.app.image_sources import RemoteImageCandidate

    class Source:
        provider_name = "wikimedia"
        calls = []
        async def search(self, query, *, limit):
            self.calls.append(query)
            return [RemoteImageCandidate("wikimedia", str(i), query, f"https://example.test/{i}", f"Candidate {i}", "", f"https://example.test/{i}.jpg", f"https://example.test/{i}.jpg", 640, 360, "landscape", "known_public_license", i) for i in range(5)]

    class Ranker:
        def rank(self, query, assets):
            return [dict(asset, score=score, embedding_score=score, reason="multimodal semantic embedding") for asset, score in zip(reversed(assets), (.91, .82, .71, .60, .05))]

    tmp_path = Path.cwd() / ".test-debug-cli" / uuid.uuid4().hex
    tmp_path.mkdir(parents=True)
    cached = {
        "schema_version": "curation-images-0.2",
        "chunks": {
            "chunk-1": {"status": "searched", "queries": ["tourism sustainable", "tourism sustainable documentary photography", "tourism sustainable editorial image"], "candidates": [{"provider": "wikimedia", "provider_id": "cached"}]},
            "chunk-2": {"status": "searched", "queries": ["families local village", "families local village documentary photography", "families local village editorial image"], "candidates": [], "zero_result_reason": "0 provider results"},
        },
    }
    try:
        (tmp_path / "image-candidates.json").write_text(__import__("json").dumps(cached), encoding="utf-8")
        source = Source()
        payload = discover_image_candidates(
            [{"id": "chunk-1", "text": "turismo sostenibile"}, {"id": "chunk-2", "text": "famiglie locali villaggio"}],
            tmp_path,
            sources=[source], ranker=Ranker(), preview_fetcher=lambda _url: b"jpeg", relevance_floor=.1,
        )
        assert payload["chunks"]["chunk-1"]["cache_status"] == "reused"
        retried = payload["chunks"]["chunk-2"]
        assert retried["status"] == "searched" and retried["raw_count"] >= 5
        assert retried["accepted_count"] == 4
        assert [row["score"] for row in retried["candidates"]] == [.91, .82, .71, .6]
        assert all(row["preview_path"] for row in retried["candidates"])
        assert payload["cache_reused_chunks"] == 1 and payload["retried_chunks"] == 1
    finally:
        shutil.rmtree(tmp_path)


def test_image_discovery_searches_each_concrete_shot_and_persists_shot_ranking():
    from backend.app.image_sources import RemoteImageCandidate

    class Source:
        provider_name = "wikimedia"
        async def search(self, query, *, limit):
            provider_id = query.split()[0]
            return [RemoteImageCandidate("wikimedia", provider_id, query, f"https://example.test/{provider_id}", query, "", f"https://example.test/{provider_id}.jpg", f"https://example.test/{provider_id}.jpg", 640, 360, "landscape", "known_public_license", 0)]

    class Ranker:
        def rank(self, query, assets):
            return [dict(asset, score=.75, embedding_score=.75, reason="multimodal semantic embedding") for asset in assets]

    root = Path.cwd() / ".test-debug-cli" / uuid.uuid4().hex
    root.mkdir(parents=True)
    visual_plan = {"chunks": {"chunk-1": {
        "core_meaning": "a journey requires multiple transport legs",
        "shots": [
            {"shot_id": "airplane", "description": "passengers board a commercial airplane", "image_queries": ["airport passengers boarding plane"]},
            {"shot_id": "ferry", "description": "travelers board a passenger ferry", "image_queries": ["passengers boarding ferry"]},
        ],
    }}}
    try:
        payload = discover_image_candidates(
            [{"id": "chunk-1", "text": "travel"}], root, sources=[Source()], ranker=Ranker(),
            preview_fetcher=lambda _url: b"jpeg", visual_plan=visual_plan,
        )
        row = payload["chunks"]["chunk-1"]
        assert row["queries"] == ["airport passengers boarding plane", "passengers boarding ferry"]
        assert {candidate["shot_id"] for candidate in row["candidates"]} == {"airplane", "ferry"}
        assert all(candidate["rank_reason"] == "multimodal semantic embedding" for candidate in row["candidates"])
    finally:
        shutil.rmtree(root)


def test_image_discovery_serializes_candidates_without_provider_credentials():
    class Source:
        async def search(self, query, *, limit):
            from backend.app.image_sources import RemoteImageCandidate
            return [RemoteImageCandidate("wikimedia", "1", query, "https://example.test/file", "File", "", "https://example.test/t.jpg", "https://example.test/f.jpg", 640, 360, "landscape", "known_public_license", 0)]

    captured = {}
    with patch("backend.app.debug_run_cli._write_json", side_effect=lambda path, payload: captured.update(payload)):
        payload = discover_image_candidates([{"id": "chunk-1", "text": "turismo sostenibile"}], Path("not-created"), sources=[Source()])
    assert payload["chunks"]["chunk-1"]["candidates"][0]["provider"] == "wikimedia"
    assert captured["chunks"]["chunk-1"]["query"] == "tourism sustainable"


def test_image_discovery_refreshes_stale_full_phrase_query_cache():
    class Source:
        calls = []
        async def search(self, query, *, limit):
            self.calls.append(query)
            return []

    root = Path.cwd() / ".test-debug-cli" / uuid.uuid4().hex
    root.mkdir(parents=True)
    try:
        (root / "image-candidates.json").write_text(
            '{"chunks":{"chunk-1":{"query":"Questo è il vecchio testo completo e prolisso","candidates":[{}]}}}',
            encoding="utf-8",
        )
        source = Source()
        payload = discover_image_candidates(
            [{"id": "chunk-1", "text": "turismo sostenibile famiglie locali autentiche"}],
            root,
            sources=[source],
        )
        assert source.calls == ["tourism sustainable families local", "tourism sustainable families local documentary photography", "tourism sustainable families local editorial image"]
        assert payload["chunks"]["chunk-1"]["candidates"] == []
    finally:
        shutil.rmtree(root)


def test_existing_editorial_artifacts_skip_expensive_upstream():
    root = Path.cwd() / ".test-debug-cli" / uuid.uuid4().hex
    root.mkdir(parents=True)
    try:
        assert has_editorial_artifacts(root) is False
        for name in ("online-candidates.json", "edit-plan.json", "review.html"):
            (root / name).write_text("{}", encoding="utf-8")
        assert has_editorial_artifacts(root) is True
    finally:
        shutil.rmtree(root)


def test_concrete_visual_video_artifact_requires_diagnostics_for_every_chunk():
    root = Path.cwd() / ".test-debug-cli" / uuid.uuid4().hex
    root.mkdir(parents=True)
    try:
        (root / "visual-plan.json").write_text(
            '{"chunks":{"chunk-1":{"shots":[]},"chunk-2":{"shots":[],"video_search":{}}}}',
            encoding="utf-8",
        )
        assert has_concrete_visual_video_artifact(root) is False
        (root / "visual-plan.json").write_text(
            '{"chunks":{"chunk-1":{"shots":[],"video_search":{}},"chunk-2":{"shots":[],"video_search":{}}}}',
            encoding="utf-8",
        )
        assert has_concrete_visual_video_artifact(root) is True
    finally:
        shutil.rmtree(root)


def test_build_short_outline_preserves_words_and_uses_eight_second_safety_cap():
    transcript = {"segments": [
        {"start": 0.0, "end": 5.8, "text": "OpenAI ha scritto una cosa importante. Poi torna a parlare.",
         "words": [
             {"start": 0.0, "end": .7, "text": "OpenAI"},
             {"start": .7, "end": 1.3, "text": "ha"},
             {"start": 1.3, "end": 2.1, "text": "scritto"},
             {"start": 2.1, "end": 2.8, "text": "una"},
             {"start": 2.8, "end": 3.4, "text": "cosa"},
             {"start": 3.4, "end": 3.9, "text": "importante."},
             {"start": 4.1, "end": 4.6, "text": "Poi"},
             {"start": 4.6, "end": 5.0, "text": "torna"},
             {"start": 5.0, "end": 5.3, "text": "a"},
             {"start": 5.3, "end": 5.8, "text": "parlare."},
         ]},
    ]}
    outline, chunks = build_short_outline(transcript)
    assert len(chunks) == 2
    assert max(row["duration"] for row in chunks) <= 8.0
    assert " ".join(word for row in chunks for word in row["text"].split()) == (
        "OpenAI ha scritto una cosa importante. Poi torna a parlare."
    )
    assert outline["beats"][0]["broll_queries"]
    assert outline["beats"][1]["broll_queries"] == []


def test_normalize_faster_whisper_preserves_segment_and_word_timestamps():
    segments = [SimpleNamespace(
        start=0.2,
        end=1.4,
        text=" Ciao mondo",
        words=[
            SimpleNamespace(start=0.2, end=0.7, word=" Ciao"),
            SimpleNamespace(start=0.7, end=1.4, word=" mondo"),
        ],
    )]
    transcript = normalize_faster_whisper(
        segments,
        language="it",
        duration_seconds=1.6,
    )
    assert transcript == {
        "language": "it",
        "duration": 1.6,
        "segments": [{
            "start": 0.2,
            "end": 1.4,
            "text": "Ciao mondo",
            "words": [
                {"start": 0.2, "end": 0.7, "text": "Ciao"},
                {"start": 0.7, "end": 1.4, "text": "mondo"},
            ],
        }],
    }


def test_run_asr_stage_uses_italian_word_timestamps_and_vad():
    calls = {}

    class FakeModel:
        def transcribe(self, video, **kwargs):
            calls["video"] = video
            calls["kwargs"] = kwargs
            segment = SimpleNamespace(
                start=0.0,
                end=0.8,
                text=" Prova",
                words=[SimpleNamespace(start=0.0, end=0.8, word=" Prova")],
            )
            return iter([segment]), SimpleNamespace(language="it", duration=0.8)

    transcript, mode = run_asr_stage(
        Path("input.mp4"),
        model_factory=lambda **_: FakeModel(),
        model_name="turbo",
        cache_dir=Path("model-cache"),
        timeline_fps=30,
    )
    assert mode == "cuda/float16"
    assert transcript["timeline_fps"] == 30
    assert transcript["segments"][0]["words"][0]["text"] == "Prova"
    assert calls == {
        "video": "input.mp4",
        "kwargs": {"language": "it", "word_timestamps": True, "vad_filter": True},
    }


def test_build_short_outline_queries_substantive_lowercase_chunk():
    words = [
        {"start": index * 0.4, "end": (index + 1) * 0.4, "text": word}
        for index, word in enumerate("turismo sostenibile voli barche impatto ambientale".split())
    ]
    outline, _ = build_short_outline({"segments": [{"words": words}]})
    assert outline["beats"][0]["broll_queries"][0] == (
        "tourism sustainable flights boats impact environmental"
    )
