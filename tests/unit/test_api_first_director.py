import json

import pytest


def package_fixture():
    return {
        "schema_version": "rambla-editorial-input-1",
        "project_id": "abc123def456",
        "duration": 6.0,
        "language": "it",
        "transcript_signature": "sig-123",
        "chunks": [
            {"id": "c0", "start": 0.0, "end": 2.0, "text": "Arriviamo al porto"},
            {"id": "c1", "start": 2.0, "end": 4.0, "text": "e salgono tutti sul traghetto"},
            {"id": "c2", "start": 4.0, "end": 6.0, "text": "in pochi minuti"},
        ],
        "full_transcript": "Arriviamo al porto e salgono tutti sul traghetto in pochi minuti",
        "word_timestamps": [{"word": "NEVER_SEND_WORD_TIMESTAMPS", "start": 0.0, "end": 0.1}],
        "source_video_path": "Z:/PRIVATE/NEVER_SEND_SOURCE_VIDEO.mp4",
    }


def valid_decisions():
    return {
        "global_topic": "Crowded ferry boarding",
        "beats": [
            {
                "chunk_id": "c0",
                "action": "BROLL",
                "editorial_function": "Show arrival at the ferry",
                "core_meaning": "Passengers arrive at the ferry",
                "subtext": "",
                "visual_mode": "single",
                "shots": [
                    {
                        "description": "Passengers walking toward a ferry boarding ramp",
                        "image_queries": ["passengers approaching ferry"],
                        "video_queries": ["passengers approaching ferry"],
                    }
                ],
                "avoid": ["empty ferry", "cruise ship interior"],
            },
            {
                "chunk_id": "c1",
                "action": "CONTINUE_PREVIOUS_VISUAL",
                "editorial_function": "Continue the same boarding action",
                "core_meaning": "Passengers board the ferry",
                "subtext": "",
                "visual_mode": "single",
                "shots": [],
                "avoid": [],
            },
            {
                "chunk_id": "c2",
                "action": "CONTINUE_PREVIOUS_VISUAL",
                "editorial_function": "Let the action finish quickly",
                "core_meaning": "The boarding happens quickly",
                "subtext": "",
                "visual_mode": "single",
                "shots": [],
                "avoid": [],
            },
        ],
    }


def test_director_prompt_uses_whole_chunk_ledger_without_video_or_word_timestamps():
    from backend.app.api_first_director import build_director_prompt

    prompt = build_director_prompt(package_fixture())

    assert "Arriviamo al porto" in prompt
    assert "e salgono tutti sul traghetto" in prompt
    assert "in pochi minuti" in prompt
    assert prompt.index("Arriviamo al porto") < prompt.index("in pochi minuti")
    assert "NEVER_SEND_SOURCE_VIDEO" not in prompt
    assert "NEVER_SEND_WORD_TIMESTAMPS" not in prompt


def test_director_cache_signature_includes_planner_contract_version(monkeypatch):
    import backend.app.api_first_director_cli as cli

    first = cli._request_signature(package_fixture(), "test", "model", "high")
    monkeypatch.setattr(cli, "DIRECTOR_SCHEMA_VERSION", "rambla-api-first-director-test-next")
    second = cli._request_signature(package_fixture(), "test", "model", "high")

    assert first != second


def test_director_prompt_keeps_full_context_and_names_coverage_allowlist():
    from backend.app.api_first_director import build_director_prompt

    package = package_fixture()
    package["coverage_selected_chunk_ids"] = ["c1"]
    prompt = build_director_prompt(package)

    assert all(row["text"] in prompt for row in package["chunks"])
    assert 'COVERAGE_SELECTED_CHUNK_IDS=["c1"]' in prompt
    assert "Only selected chunk IDs may use BROLL" in prompt


def test_compile_rejects_visual_action_for_unselected_chunk():
    from backend.app.api_first_director import compile_director_decisions

    package = package_fixture()
    package["coverage_selected_chunk_ids"] = ["c0"]
    decisions = valid_decisions()

    with pytest.raises(ValueError, match="not selected for Coverage"):
        compile_director_decisions(package, decisions)


def test_selected_orphaned_continuation_becomes_searchable_broll():
    from backend.app.api_first_director import compile_director_decisions

    package = package_fixture()
    package["coverage_selected_chunk_ids"] = ["c1"]
    decisions = valid_decisions()
    decisions["beats"][0].update(action="KEEP_TALKING_HEAD", shots=[])
    decisions["beats"][2].update(action="KEEP_TALKING_HEAD", shots=[])

    plan = compile_director_decisions(package, decisions)

    beat = plan["visual_beats"][1]
    assert beat["action"] == "BROLL"
    assert beat["visual_mode"] == "single"
    assert len(beat["shots"]) == 1
    assert beat["shots"][0]["video_queries"] == ["Passengers board the ferry"]


def test_selected_talking_head_is_forced_to_searchable_broll():
    from backend.app.api_first_director import compile_director_decisions

    package = package_fixture()
    package["coverage_selected_chunk_ids"] = ["c0"]
    decisions = valid_decisions()
    decisions["beats"][0].update(action="KEEP_TALKING_HEAD", shots=[])
    decisions["beats"][1].update(action="KEEP_TALKING_HEAD", shots=[])
    decisions["beats"][2].update(action="KEEP_TALKING_HEAD", shots=[])

    beat = compile_director_decisions(package, decisions)["visual_beats"][0]

    assert beat["action"] == "BROLL"
    assert beat["original_text"] == "Arriviamo al porto"
    assert beat["shots"][0]["video_queries"] == ["Passengers arrive at the ferry"]


def test_manual_import_validation_rejects_visual_action_for_unselected_chunk():
    from backend.app.api_first_director import compile_director_decisions
    from backend.app.editorial_import import validate_import

    legacy = package_fixture()
    plan = compile_director_decisions(legacy, valid_decisions())
    selected = package_fixture()
    selected["coverage_selected_chunk_ids"] = ["c0"]

    with pytest.raises(ValueError, match="not selected for Coverage"):
        validate_import(plan, selected)


def test_compile_director_decisions_reconstructs_canonical_timeline_and_ids():
    from backend.app.api_first_director import compile_director_decisions

    plan = compile_director_decisions(package_fixture(), valid_decisions())

    assert plan["schema_version"] == "rambla-visual-plan-1"
    assert plan["project_id"] == "abc123def456"
    assert plan["transcript_signature"] == "sig-123"
    assert [b["id"] for b in plan["visual_beats"]] == ["beat_001", "beat_002", "beat_003"]
    first, second, third = plan["visual_beats"]
    assert first["start"] == 0.0
    assert first["end"] == 2.0
    assert first["covered_chunk_ids"] == ["c0"]
    assert first["original_text"] == "Arriviamo al porto"
    assert first["shots"][0]["shot_id"] == "beat_001_shot_01"
    assert second["continuation_from"] == "beat_001"
    assert third["continuation_from"] == "beat_002"


def test_compile_rejects_wrong_chunk_order():
    from backend.app.api_first_director import compile_director_decisions

    decisions = valid_decisions()
    decisions["beats"][0]["chunk_id"] = "c1"

    with pytest.raises(ValueError, match="chunk_id must be c0"):
        compile_director_decisions(package_fixture(), decisions)


def test_compile_rejects_query_reused_by_another_visual_beat():
    from backend.app.api_first_director import compile_director_decisions

    decisions = valid_decisions()
    decisions["beats"][1].update(
        action="BROLL",
        visual_mode="single",
        shots=[{
            "description": "A second view of passengers approaching the ferry",
            "image_queries": ["passengers approaching ferry"],
            "video_queries": ["passengers approaching ferry"],
        }],
    )

    with pytest.raises(ValueError, match="reused by another visual beat"):
        compile_director_decisions(package_fixture(), decisions)


def test_compile_rewrites_generic_ambience_as_historical_evidence_queries():
    from backend.app.api_first_director import compile_director_decisions

    package = package_fixture()
    package["chunks"] = [{
        "id": "history", "start": 0.0, "end": 3.0,
        "text": "Negli anni 90 questa zona fu colpita dalla violenza dei gruppi jihadisti",
    }]
    decisions = {"global_topic": "Minya history", "beats": [{
        "chunk_id": "history", "action": "BROLL",
        "editorial_function": "Show the historical context",
        "core_meaning": "Minya was affected by jihadist violence in the 1990s",
        "subtext": "The past explains the present security",
        "visual_mode": "single",
        "shots": [{
            "description": "A quiet Minya public road",
            "image_queries": ["Minya Egypt town street", "quiet Minya public area"],
            "video_queries": ["Minya Egypt street life", "Minya Egypt town road"],
        }],
        "avoid": ["graphic injury"],
    }]}

    plan = compile_director_decisions(package, decisions)

    shot = plan["visual_beats"][0]["shots"][0]
    assert shot["video_queries"] == [
        "Minya Egypt 1990s jihad archive",
        "jihad Egypt archive",
        "jihad Egypt",
    ]


def test_compile_accepts_precise_to_broad_historical_query_ladder():
    from backend.app.api_first_director import compile_director_decisions

    package = package_fixture()
    package["chunks"] = [{
        "id": "history", "start": 0.0, "end": 3.0,
        "text": "Negli anni 90 questa zona fu colpita dalla violenza dei gruppi jihadisti",
    }]
    decisions = {"global_topic": "Minya history", "beats": [{
        "chunk_id": "history", "action": "BROLL",
        "editorial_function": "Show literal historical evidence",
        "core_meaning": "Minya was affected by jihadist violence in the 1990s",
        "subtext": "The past explains the present security",
        "visual_mode": "single",
        "shots": [{
            "description": "Archival news imagery about jihadist violence in 1990s Minya",
            "image_queries": ["Minya 1990s jihadist attacks archive", "jihadist violence Egypt", "jihad Egypt"],
            "video_queries": ["Minya 1990s jihadist news", "Egypt jihadist violence archive", "jihad Egypt"],
        }],
        "avoid": ["graphic injury", "unrelated wars", "wrong country footage"],
    }]}

    plan = compile_director_decisions(package, decisions)

    assert plan["visual_beats"][0]["shots"][0]["video_queries"][-1] == "jihad Egypt"


def test_compile_adds_findable_broad_variant_to_historical_queries():
    from backend.app.api_first_director import compile_director_decisions

    package = package_fixture()
    package["chunks"] = [{
        "id": "history", "start": 0.0, "end": 3.0,
        "text": "Negli anni 90 questa zona fu colpita dalla violenza dei gruppi jihadisti",
    }]
    decisions = {"global_topic": "Minya history", "beats": [{
        "chunk_id": "history", "action": "BROLL",
        "editorial_function": "Show literal historical evidence",
        "core_meaning": "Minya was affected by jihadist violence in the 1990s",
        "subtext": "The past explains the present security",
        "visual_mode": "single",
        "shots": [{
            "description": "Archival news imagery about jihadist violence in 1990s Minya",
            "image_queries": ["Minya Egypt 1990s jihadist attacks archive"],
            "video_queries": ["Minya Egypt 1990s jihadist news archive"],
        }],
        "avoid": ["graphic injury", "unrelated wars"],
    }]}

    plan = compile_director_decisions(package, decisions)

    shot = plan["visual_beats"][0]["shots"][0]
    assert shot["image_queries"][-1] == "jihad Egypt"
    assert shot["video_queries"][-1] == "jihad Egypt"


def test_compile_allows_unselected_historical_talking_head_without_queries():
    from backend.app.api_first_director import compile_director_decisions

    package = package_fixture()
    package["chunks"] = [{
        "id": "history", "start": 0.0, "end": 3.0,
        "text": "Negli anni 90 questa zona fu colpita dalla violenza dei gruppi jihadisti",
    }]
    package["coverage_selected_chunk_ids"] = []
    decisions = {"global_topic": "Minya history", "beats": [{
        "chunk_id": "history", "action": "KEEP_TALKING_HEAD",
        "editorial_function": "Keep the presenter visible",
        "core_meaning": "Minya was affected by jihadist violence in the 1990s",
        "subtext": "",
        "visual_mode": "single",
        "shots": [],
        "avoid": [],
    }]}

    plan = compile_director_decisions(package, decisions)

    assert plan["visual_beats"][0]["action"] == "KEEP_TALKING_HEAD"


def test_compile_removes_avoid_items_that_erase_spoken_historical_subject():
    from backend.app.api_first_director import compile_director_decisions

    package = package_fixture()
    package["chunks"] = [{
        "id": "history", "start": 0.0, "end": 3.0,
        "text": "La zona fu colpita dalle attività dei gruppi jihadisti",
    }]
    decisions = {"global_topic": "Minya history", "beats": [{
        "chunk_id": "history", "action": "BROLL",
        "editorial_function": "Show historical evidence",
        "core_meaning": "The area was affected by jihadist activity",
        "subtext": "Historical context",
        "visual_mode": "single",
        "shots": [{
            "description": "Archival report about jihadist activity in Egypt",
            "image_queries": ["jihadist activity Egypt archive", "jihad Egypt"],
            "video_queries": ["jihadist activity Egypt news", "jihad Egypt"],
        }],
        "avoid": [
            "jihadist footage", "terrorism archive", "news footage",
            "violent conflict footage", "gunfire", "wars or rebel activities", "graphic injury",
        ],
    }]}

    plan = compile_director_decisions(package, decisions)

    assert plan["visual_beats"][0]["avoid"] == ["graphic injury"]


def test_director_uses_stateful_second_call_only_for_validation_repair():
    from backend.app.api_first_director import generate_director_plan
    from backend.app.gemini_interactions import GeminiJSONReply

    invalid = valid_decisions()
    invalid["beats"][0]["chunk_id"] = "c1"

    class Provider:
        provider_name = "gemini"
        model = "gemini-3.8-flash"

        def __init__(self):
            self.calls = []

        def generate_json(self, prompt, schema, *, previous_interaction_id=None):
            self.calls.append((prompt, schema, previous_interaction_id))
            if len(self.calls) == 1:
                return GeminiJSONReply(invalid, "int-first", self.model)
            return GeminiJSONReply(valid_decisions(), "int-repair", self.model)

    provider = Provider()
    result = generate_director_plan(package_fixture(), provider)

    assert result.attempts == 2
    assert result.validation_errors
    assert len(provider.calls) == 2
    assert provider.calls[0][2] is None
    assert provider.calls[1][2] == "int-first"
    assert "TRANSCRIPT_CHUNKS=" in provider.calls[0][0]
    assert "TRANSCRIPT_CHUNKS=" not in provider.calls[1][0]
    assert "chunk_id must be c0" in provider.calls[1][0]


def test_gemini_interactions_client_sends_structured_schema_and_parses_final_text():
    from backend.app.gemini_interactions import GeminiInteractionsClient

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "id": "int-123",
                "status": "completed",
                "usage": {
                    "total_input_tokens": 120,
                    "total_output_tokens": 30,
                    "total_thought_tokens": 20,
                    "total_tokens": 170,
                },
                "steps": [
                    {"type": "user_input", "content": [{"type": "text", "text": "prompt"}]},
                    {
                        "type": "model_output",
                        "content": [{"type": "text", "text": '{"global_topic":"x","beats":[]}'}],
                    },
                ],
            }

    class HTTP:
        def __init__(self):
            self.call = None

        def post(self, url, **kwargs):
            self.call = (url, kwargs)
            return Response()

    http = HTTP()
    client = GeminiInteractionsClient("placeholder", http_client=http)
    reply = client.generate_json(
        "hello",
        {
            "type": "object",
            "properties": {"name": {"type": "string", "minLength": 1, "pattern": ".+"}},
            "required": ["name"],
            "allOf": [{"type": "object"}],
        },
    )

    assert reply.interaction_id == "int-123"
    assert reply.data["global_topic"] == "x"
    assert reply.usage["total_tokens"] == 170
    url, kwargs = http.call
    assert url == "https://generativelanguage.googleapis.com/v1beta/interactions"
    assert kwargs["headers"]["x-goog-api-key"] == "placeholder"
    assert "placeholder" not in json.dumps(kwargs["json"])
    assert kwargs["json"]["response_format"][0]["mime_type"] == "application/json"
    assert kwargs["json"]["generation_config"]["thinking_level"] == "high"
    sent_schema = kwargs["json"]["response_format"][0]["schema"]
    assert sent_schema == {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }


def test_api_first_cli_writes_visual_plan_without_source_video_input(tmp_path):
    from backend.app.api_first_director_cli import run_api_first_director
    from backend.app.gemini_interactions import GeminiJSONReply

    project = tmp_path / "abc123def456"
    run = project / "run"
    run.mkdir(parents=True)
    (run / "semantic-chunks.json").write_text(
        json.dumps(
            [
                {"id": "c0", "start": 0.0, "end": 2.0, "text": "Arriviamo al porto"},
                {"id": "c1", "start": 2.0, "end": 4.0, "text": "e salgono tutti sul traghetto"},
                {"id": "c2", "start": 4.0, "end": 6.0, "text": "in pochi minuti"},
            ]
        ),
        encoding="utf-8",
    )
    (run / "transcript-raw.json").write_text(
        json.dumps({"language": "it", "segments": []}),
        encoding="utf-8",
    )
    (run / "analysis-signature.json").write_text(
        json.dumps({"analysis_signature": "analysis"}),
        encoding="utf-8",
    )

    class Provider:
        provider_name = "fake-cloud"
        model = "test-model"

        def __init__(self):
            self.calls = 0

        def generate_json(self, prompt, schema, *, previous_interaction_id=None):
            self.calls += 1
            assert "source_video" not in prompt
            return GeminiJSONReply(valid_decisions(), "int-test", self.model)

    provider = Provider()
    summary = run_api_first_director(run_dir=run, provider=provider)

    assert summary["source_video_sent_to_ai"] is False
    assert summary["activated"] is False
    assert summary["cache_status"] == "generated"
    assert provider.calls == 1
    assert not (run / "visual-plan.json").exists()

    candidate = run / "api-first" / "visual-plan.json"
    plan = json.loads(candidate.read_text(encoding="utf-8"))
    assert len(plan["visual_beats"]) == 3

    reused = run_api_first_director(run_dir=run, provider=provider)
    assert reused["cache_status"] == "reused"
    assert reused["attempts"] == 0
    assert reused["api_calls_this_run"] == 0
    assert provider.calls == 1

    activated = run_api_first_director(run_dir=run, provider=provider, activate=True)
    assert activated["activated"] is True
    assert activated["cache_status"] == "reused"
    assert provider.calls == 1
    assert (run / "visual-plan.json").is_file()

    audit = json.loads((run / "api-first" / "director-run.json").read_text(encoding="utf-8"))
    assert audit["source_video_sent_to_ai"] is False
    assert audit["word_timestamps_sent_to_director"] is False
    assert audit["activated"] is True


def test_ab_review_compares_same_transcript_without_declaring_a_winner(tmp_path):
    from backend.app.api_first_review import build_review, comparison_payload

    baseline = {
        "schema_version": "rambla-visual-plan-1",
        "project_id": "abc123def456",
        "transcript_signature": "same-transcript",
        "global_topic": "ferry",
        "visual_beats": [
            {
                "id": "old_1", "start": 0.0, "end": 3.0,
                "covered_chunk_ids": ["c0"], "original_text": "first",
                "action": "BROLL", "editorial_function": "show",
                "core_meaning": "ferry boarding", "subtext": "",
                "visual_mode": "single",
                "shots": [{"shot_id": "old_s1", "description": "people boarding ferry",
                           "image_queries": ["people boarding ferry"],
                           "video_queries": ["people boarding ferry"]}],
                "avoid": [],
            },
            {
                "id": "old_2", "start": 3.0, "end": 6.0,
                "covered_chunk_ids": ["c1"], "original_text": "second",
                "action": "KEEP_TALKING_HEAD", "editorial_function": "delivery",
                "core_meaning": "punchline", "subtext": "",
                "visual_mode": "single", "shots": [], "avoid": [],
            },
        ],
    }
    candidate = json.loads(json.dumps(baseline))
    candidate["visual_beats"][1]["action"] = "CONTINUE_PREVIOUS_VISUAL"
    candidate["visual_beats"][1]["continuation_from"] = "old_1"

    comparison = comparison_payload(baseline, candidate)
    assert comparison["action_agreement_ratio"] == 0.5
    assert "winner" not in comparison

    run = tmp_path / "run"
    (run / "api-first").mkdir(parents=True)
    (run / "visual-plan.json").write_text(json.dumps(baseline), encoding="utf-8")
    (run / "api-first" / "visual-plan.json").write_text(json.dumps(candidate), encoding="utf-8")
    result = build_review(run)
    html = (run / "api-first" / "ab-review.html").read_text(encoding="utf-8")
    assert "V4 BASELINE" in html
    assert "V5 API-FIRST" in html
    assert "No automatic winner" in html
    assert result["candidate"]["continue_beats"] == 1


def test_gemini_retries_overload_then_falls_back_to_37_and_sticks_for_repair():
    from backend.app.gemini_interactions import GeminiInteractionsClient

    success_payload = {
        "id": "int-fallback",
        "status": "completed",
        "steps": [
            {
                "type": "model_output",
                "content": [{"type": "text", "text": '{"global_topic":"x","beats":[]}'}],
            }
        ],
    }

    class Response:
        def __init__(self, status, payload):
            self.status_code = status
            self._payload = payload
            self.headers = {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"http {self.status_code}")

        def json(self):
            return self._payload

    class HTTP:
        def __init__(self):
            self.calls = []
            self.responses = [
                Response(503, {"error": {"message": "high demand"}}),
                Response(503, {"error": {"message": "high demand"}}),
                Response(503, {"error": {"message": "high demand"}}),
                Response(200, success_payload),
                Response(200, {**success_payload, "id": "int-repair"}),
            ]

        def post(self, url, **kwargs):
            self.calls.append(kwargs["json"]["model"])
            return self.responses.pop(0)

    delays = []
    http = HTTP()
    client = GeminiInteractionsClient(
        "placeholder",
        http_client=http,
        sleeper=delays.append,
    )

    reply = client.generate_json("hello", {"type": "object"})

    assert http.calls[:4] == [
        "gemini-3.8-flash",
        "gemini-3.8-flash",
        "gemini-3.8-flash",
        "gemini-3.7-flash",
    ]
    assert delays == [1.5, 4.0]
    assert reply.model == "gemini-3.7-flash"
    assert reply.requested_model == "gemini-3.8-flash"
    assert reply.fallback_used is True
    assert reply.transport_attempts == 4

    repair = client.generate_json(
        "repair",
        {"type": "object"},
        previous_interaction_id=reply.interaction_id,
    )
    assert http.calls[-1] == "gemini-3.7-flash"
    assert repair.model == "gemini-3.7-flash"
    assert repair.transport_attempts == 1


def test_gemini_read_timeout_moves_directly_to_fallback():
    import httpx
    from backend.app.gemini_interactions import GeminiInteractionsClient

    success_payload = {
        "id": "int-timeout-fallback",
        "status": "completed",
        "steps": [
            {
                "type": "model_output",
                "content": [{"type": "text", "text": '{"global_topic":"x","beats":[]}'}],
            }
        ],
    }

    class Response:
        status_code = 200
        headers = {}

        def raise_for_status(self):
            return None

        def json(self):
            return success_payload

    class HTTP:
        def __init__(self):
            self.calls = []

        def post(self, url, **kwargs):
            model = kwargs["json"]["model"]
            self.calls.append(model)
            if len(self.calls) == 1:
                raise httpx.ReadTimeout("model took too long")
            return Response()

    http = HTTP()
    client = GeminiInteractionsClient(
        "placeholder",
        http_client=http,
        sleeper=lambda _seconds: None,
    )
    reply = client.generate_json("hello", {"type": "object"})

    assert http.calls == ["gemini-3.8-flash", "gemini-3.7-flash"]
    assert reply.model == "gemini-3.7-flash"
    assert reply.fallback_used is True
    assert reply.transport_attempts == 2


def test_director_prompt_explicitly_targets_short_fast_cut_beats():
    from backend.app.api_first_director import build_director_prompt

    package=package_fixture()
    package["coverage_selected_chunk_ids"]=["c0"]
    prompt = build_director_prompt(package)
    normalized = " ".join(prompt.split())
    assert "one transcript chunk equals one visual beat" in normalized
    assert "Never merge chunks" in normalized
    assert "Return exactly one decision per transcript chunk" in normalized
    assert "BROLL is NOT a topical explainer search" in normalized
    assert "Every selected chunk must use BROLL so it remains independently searchable" in normalized


def test_cli_configures_utf8_stdio_without_crashing_on_windows_style_streams(monkeypatch):
    import backend.app.api_first_director_cli as cli

    class Stream:
        def __init__(self):
            self.calls = []
        def reconfigure(self, **kwargs):
            self.calls.append(kwargs)

    out = Stream()
    err = Stream()
    monkeypatch.setattr(cli.sys, "stdout", out)
    monkeypatch.setattr(cli.sys, "stderr", err)

    cli._configure_utf8_stdio()

    assert out.calls == [{"encoding": "utf-8", "errors": "replace"}]
    assert err.calls == [{"encoding": "utf-8", "errors": "replace"}]


def test_gemini_429_skips_same_model_retries_and_falls_back_immediately():
    from backend.app.gemini_interactions import GeminiInteractionsClient

    success_payload = {
        "id": "int-quota-fallback",
        "status": "completed",
        "steps": [
            {
                "type": "model_output",
                "content": [{"type": "text", "text": '{"global_topic":"x","beats":[]}'}],
            }
        ],
    }

    class Response:
        def __init__(self, status, payload):
            self.status_code = status
            self._payload = payload
            self.headers = {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"http {self.status_code}")

        def json(self):
            return self._payload

    class HTTP:
        def __init__(self):
            self.calls = []
            self.responses = [
                Response(429, {"error": {"message": "rate limit exceeded"}}),
                Response(200, success_payload),
            ]

        def post(self, url, **kwargs):
            self.calls.append(kwargs["json"]["model"])
            return self.responses.pop(0)

    events = []
    http = HTTP()
    client = GeminiInteractionsClient(
        "placeholder",
        http_client=http,
        sleeper=lambda _seconds: None,
        event_callback=lambda event, data: events.append((event, data)),
    )

    reply = client.generate_json("hello", {"type": "object"})

    assert http.calls == ["gemini-3.8-flash", "gemini-3.7-flash"]
    assert reply.model == "gemini-3.7-flash"
    assert reply.fallback_used is True
    assert any(event == "quota_exhausted" for event, _data in events)


def test_gemini_quota_cooldown_persists_across_client_runs(tmp_path):
    from backend.app.gemini_interactions import GeminiInteractionsClient

    state_path = tmp_path / "provider-health.json"

    class Response:
        def __init__(self, status, payload, headers=None):
            self.status_code = status
            self._payload = payload
            self.headers = headers or {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"http {self.status_code}")

        def json(self):
            return self._payload

    success = {
        "id": "int-ok",
        "status": "completed",
        "steps": [{
            "type": "model_output",
            "content": [{"type": "text", "text": '{"global_topic":"x","beats":[]}'}],
        }],
    }

    class HTTP1:
        def __init__(self):
            self.calls = []
        def post(self, url, **kwargs):
            model = kwargs["json"]["model"]
            self.calls.append(model)
            if model == "gemini-3.8-flash":
                return Response(429, {"error": {"message": "Rate limit. Please retry in 120s"}})
            return Response(200, success)

    first_http = HTTP1()
    first = GeminiInteractionsClient(
        "placeholder",
        http_client=first_http,
        cooldown_state_path=state_path,
        sleeper=lambda _seconds: None,
    )
    first.generate_json("hello", {"type": "object"})
    assert first_http.calls == ["gemini-3.8-flash", "gemini-3.7-flash"]
    assert state_path.is_file()

    class HTTP2:
        def __init__(self):
            self.calls = []
        def post(self, url, **kwargs):
            self.calls.append(kwargs["json"]["model"])
            return Response(200, success)

    events = []
    second_http = HTTP2()
    second = GeminiInteractionsClient(
        "placeholder",
        http_client=second_http,
        cooldown_state_path=state_path,
        event_callback=lambda event, data: events.append((event, data)),
    )
    reply = second.generate_json("hello again", {"type": "object"})

    assert second_http.calls == ["gemini-3.7-flash"]
    assert reply.model == "gemini-3.7-flash"
    assert any(
        event == "model_skipped" and data.get("model") == "gemini-3.8-flash"
        for event, data in events
    )


def test_groq_director_uses_qwen_high_reasoning_and_strict_structured_output():
    from backend.app.groq_api import GroqDirectorClient

    class Response:
        status_code = 200
        headers = {}

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "id": "chatcmpl-test",
                "choices": [{
                    "message": {
                        "content": '{"global_topic":"x","beats":[]}'
                    }
                }],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                    "total_tokens": 120,
                },
            }

    class HTTP:
        def __init__(self):
            self.call = None

        def post(self, url, **kwargs):
            self.call = (url, kwargs)
            return Response()

    http = HTTP()
    client = GroqDirectorClient("placeholder", http_client=http)
    reply = client.generate_json(
        "hello",
        {
            "type": "object",
            "properties": {"name": {"type": "string", "minLength": 1}},
            "required": ["name"],
        },
    )

    url, kwargs = http.call
    assert url == "https://api.groq.com/openai/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer placeholder"
    body = kwargs["json"]
    assert body["model"] == "qwen/qwen3.8-27b"
    assert body["reasoning_effort"] == "high"
    assert body["reasoning_format"] == "hidden"
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["response_format"]["json_schema"]["schema"]["properties"]["name"] == {"type": "string"}
    assert reply.model == "qwen/qwen3.8-27b"
    assert reply.usage["total_tokens"] == 120


def test_groq_repair_resends_original_transcript_context():
    from backend.app.groq_api import GroqDirectorClient

    class Response:
        status_code = 200
        headers = {}

        def __init__(self, completion_id):
            self.completion_id = completion_id

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "id": self.completion_id,
                "choices": [{
                    "message": {
                        "content": '{"global_topic":"x","beats":[]}'
                    }
                }],
            }

    class HTTP:
        def __init__(self):
            self.calls = []

        def post(self, url, **kwargs):
            self.calls.append(kwargs["json"])
            return Response(f"chat-{len(self.calls)}")

    http = HTTP()
    client = GroqDirectorClient("placeholder", http_client=http)

    first = client.generate_json("WHOLE_TRANSCRIPT_SENTINEL", {"type": "object"})
    client.generate_json(
        "repair only this error",
        {"type": "object"},
        previous_interaction_id=first.interaction_id,
    )

    repair_prompt = http.calls[1]["messages"][0]["content"]
    assert "WHOLE_TRANSCRIPT_SENTINEL" in repair_prompt
    assert "repair only this error" in repair_prompt


def test_auto_provider_falls_from_gemini_to_groq():
    from backend.app.director_provider import FailoverDirectorProvider
    from backend.app.gemini_interactions import GeminiAPIError, GeminiJSONReply

    class Gemini:
        provider_name = "gemini"
        model = "gemini-3.8-flash"
        thinking_level = "high"

        def generate_json(self, prompt, schema, *, previous_interaction_id=None):
            raise GeminiAPIError("Gemini request failed (429)")

    class Groq:
        provider_name = "groq"
        model = "qwen/qwen3.8-27b"
        thinking_level = "high"

        def generate_json(self, prompt, schema, *, previous_interaction_id=None):
            return GeminiJSONReply(
                {"global_topic": "x", "beats": []},
                "groq-1",
                self.model,
            )

    events = []
    auto = FailoverDirectorProvider(
        [Gemini(), Groq()],
        event_callback=lambda event, data: events.append((event, data)),
    )
    reply = auto.generate_json("hello", {"type": "object"})

    assert reply.model == "qwen/qwen3.8-27b"
    assert auto.provider_name == "groq"
    assert any(event == "provider_fallback" for event, _data in events)


def test_director_schema_can_lock_exact_chunk_count():
    from backend.app.api_first_director import director_schema

    schema = director_schema(3)
    beats = schema["properties"]["beats"]
    assert beats["minItems"] == 3
    assert beats["maxItems"] == 3
    assert "chunk_id" in beats["items"]["required"]


def test_compile_requires_exactly_one_decision_per_chunk():
    from backend.app.api_first_director import compile_director_decisions

    decisions = valid_decisions()
    decisions["beats"] = decisions["beats"][:2]

    with pytest.raises(ValueError, match="expected exactly 3 chunk decisions, got 2"):
        compile_director_decisions(package_fixture(), decisions)


def test_groq_uses_model_specific_completion_limits():
    from backend.app.groq_api import GroqDirectorClient

    assert GroqDirectorClient._max_completion_tokens("qwen/qwen3.8-27b") == 16384
    assert GroqDirectorClient._max_completion_tokens("openai/gpt-oss-120b") == 65536

def test_groq_repair_truncation_uses_configured_larger_fallback():
    from backend.app.groq_api import GroqDirectorClient
    class Response:
        headers={}
        def __init__(self,failed):self.failed=failed;self.status_code=400 if failed else 200
        def raise_for_status(self):
            if self.failed:raise RuntimeError('HTTP400')
        def json(self):
            if self.failed:return {'error':{'message':'max completion tokens reached before generating a valid document: output was truncated'}}
            return {'id':'x','choices':[{'message':{'content':'{"ok":true}'}}]}
    class HTTP:
        def __init__(self):self.calls=[]
        def post(self,url,**kwargs):
            self.calls.append(kwargs['json']);return Response(len(self.calls)==2)
    http=HTTP();client=GroqDirectorClient('placeholder',http_client=http)
    first=client.generate_json('FULL CORRECTED TRANSCRIPT',{'type':'object'})
    reply=client.generate_json('repair',{'type':'object'},previous_interaction_id=first.interaction_id)
    assert reply.data=={'ok':True}
    assert len(http.calls)==3
    assert http.calls[-1]['model']=='openai/gpt-oss-120b'
    assert 'FULL CORRECTED TRANSCRIPT' in http.calls[-1]['messages'][0]['content']

def test_groq_rejects_length_finish_even_when_partial_json_parses():
    from backend.app.groq_api import GroqDirectorClient,GroqAPIError
    class Response:
        status_code=200;headers={}
        def raise_for_status(self):pass
        def json(self):return {'choices':[{'finish_reason':'length','message':{'content':'{"partial":true}'}}]}
    class HTTP:
        def post(self,*args,**kwargs):return Response()
    client=GroqDirectorClient('placeholder',http_client=HTTP(),fallback_models=())
    with pytest.raises(GroqAPIError,match='truncated'):client.generate_json('prompt',{'type':'object'})


@pytest.mark.parametrize("failure", [
    {"code": "json_validate_failed", "message": "Failed to generate JSON. Please adjust your prompt."},
    {"message": "Generated JSON does not match the expected schema. Please adjust your prompt."},
])
def test_groq_json_generation_failure_uses_fallback(failure):
    from backend.app.groq_api import GroqDirectorClient
    class Response:
        headers = {}
        def __init__(self, failed): self.status_code = 400 if failed else 200
        def raise_for_status(self):
            if self.status_code == 400: raise RuntimeError('HTTP400')
        def json(self):
            if self.status_code == 400: return {'error': failure}
            return {'id': 'ok', 'choices': [{'message': {'content': '{"ok":true}'}}]}
    class HTTP:
        def __init__(self): self.calls = []
        def post(self, url, **kwargs):
            self.calls.append(kwargs['json'])
            return Response(len(self.calls) == 1)
    http = HTTP()
    reply = GroqDirectorClient('placeholder', http_client=http).generate_json('FULL TRANSCRIPT', {'type': 'object'})
    assert reply.data == {'ok': True}
    assert reply.fallback_used and reply.transport_attempts == 2
    assert http.calls[-1]['model'] == 'openai/gpt-oss-120b'
    assert http.calls[-1]['messages'][0]['content'] == 'FULL TRANSCRIPT'


def test_director_wire_schema_avoids_large_exact_array_decoder_constraint():
    from backend.app.api_first_director import generate_director_plan
    from backend.app.gemini_interactions import GeminiJSONReply
    class Provider:
        model = 'fake'
        provider_name = 'test'
        def generate_json(self, prompt, schema, **kwargs):
            beats = schema['properties']['beats']
            assert 'minItems' not in beats and 'maxItems' not in beats
            assert '3' in beats['description']
            assert 'Arriviamo al porto' in prompt
            return GeminiJSONReply(valid_decisions(), 'ok', self.model)
    assert len(generate_director_plan(package_fixture(), Provider()).plan['visual_beats']) == 3


@pytest.mark.parametrize("message, expected_calls", [
    ("Invalid API Key", 1),
    ("Request contains an invalid argument", 1),
    ("Failed to generate JSON. Please adjust your prompt.", 3),
])
def test_groq_recovery_is_bounded_and_does_not_retry_bad_requests(message, expected_calls):
    from backend.app.groq_api import GroqDirectorClient, GroqAPIError
    class Response:
        headers = {}
        status_code = 400
        def raise_for_status(self): raise RuntimeError('HTTP400')
        def json(self): return {'error': {'message': message}}
    class HTTP:
        calls = 0
        def post(self, *args, **kwargs):
            self.calls += 1
            return Response()
    http = HTTP()
    client = GroqDirectorClient('placeholder', http_client=http, fallback_models=(), retry_delays=(0,), max_retries_per_model=2)
    with pytest.raises(GroqAPIError): client.generate_json('prompt', {'type':'object'})
    assert http.calls == expected_calls
