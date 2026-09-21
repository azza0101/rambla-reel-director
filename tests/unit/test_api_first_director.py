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
                "first_chunk_id": "c0",
                "last_chunk_id": "c1",
                "action": "BROLL",
                "editorial_function": "Show the concrete travel action",
                "core_meaning": "Passengers arrive and board a ferry",
                "subtext": "",
                "visual_mode": "single",
                "shots": [
                    {
                        "description": "Passengers walking up a ferry boarding ramp",
                        "image_queries": ["passengers boarding ferry"],
                        "video_queries": ["passengers boarding ferry", "crowd entering ferry"],
                    }
                ],
                "avoid": ["empty ferry", "cruise ship interior"],
            },
            {
                "first_chunk_id": "c2",
                "last_chunk_id": "c2",
                "action": "CONTINUE_PREVIOUS_VISUAL",
                "editorial_function": "Let the same action finish",
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


def test_compile_director_decisions_reconstructs_canonical_timeline_and_ids():
    from backend.app.api_first_director import compile_director_decisions

    plan = compile_director_decisions(package_fixture(), valid_decisions())

    assert plan["schema_version"] == "rambla-visual-plan-1"
    assert plan["project_id"] == "abc123def456"
    assert plan["transcript_signature"] == "sig-123"
    assert [b["id"] for b in plan["visual_beats"]] == ["beat_001", "beat_002"]
    first, second = plan["visual_beats"]
    assert first["start"] == 0.0
    assert first["end"] == 4.0
    assert first["covered_chunk_ids"] == ["c0", "c1"]
    assert first["original_text"] == "Arriviamo al porto e salgono tutti sul traghetto"
    assert first["shots"][0]["shot_id"] == "beat_001_shot_01"
    assert second["continuation_from"] == "beat_001"


def test_compile_rejects_gap_in_model_chunk_grouping():
    from backend.app.api_first_director import compile_director_decisions

    decisions = valid_decisions()
    decisions["beats"][0]["first_chunk_id"] = "c1"

    with pytest.raises(ValueError, match="first_chunk_id must be c0"):
        compile_director_decisions(package_fixture(), decisions)


def test_director_uses_stateful_second_call_only_for_validation_repair():
    from backend.app.api_first_director import generate_director_plan
    from backend.app.gemini_interactions import GeminiJSONReply

    invalid = valid_decisions()
    invalid["beats"][0]["first_chunk_id"] = "c1"

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
    assert "first_chunk_id must be c0" in provider.calls[1][0]


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
    assert len(plan["visual_beats"]) == 2

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


def test_director_rejects_overlong_multi_chunk_beats():
    from backend.app.api_first_director import compile_director_decisions

    package = package_fixture()
    package["chunks"] = [
        {"id": "c0", "start": 0.0, "end": 2.0, "text": "uno"},
        {"id": "c1", "start": 2.0, "end": 4.0, "text": "due"},
        {"id": "c2", "start": 4.0, "end": 6.0, "text": "tre"},
    ]
    decisions = {
        "global_topic": "x",
        "beats": [
            {
                "first_chunk_id": "c0",
                "last_chunk_id": "c2",
                "action": "BROLL",
                "editorial_function": "x",
                "core_meaning": "x",
                "subtext": "",
                "visual_mode": "single",
                "shots": [{
                    "description": "x",
                    "image_queries": ["real world action"],
                    "video_queries": ["real world action"],
                }],
                "avoid": [],
            }
        ],
    }

    with pytest.raises(ValueError, match="at most 2 transcript chunks"):
        compile_director_decisions(package, decisions)


def test_director_prompt_explicitly_targets_short_fast_cut_beats():
    from backend.app.api_first_director import build_director_prompt

    prompt = build_director_prompt(package_fixture())
    assert "roughly 2.0-3.5 seconds per beat" in prompt
    assert "never more than 2" in prompt
    assert "<=4.5 seconds" in prompt


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
