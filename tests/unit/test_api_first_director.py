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
    reply = client.generate_json("hello", {"type": "object"})

    assert reply.interaction_id == "int-123"
    assert reply.data["global_topic"] == "x"
    _, kwargs = http.call
    assert kwargs["headers"]["x-goog-api-key"] == "placeholder"
    assert "placeholder" not in json.dumps(kwargs["json"])
    assert kwargs["json"]["response_format"][0]["mime_type"] == "application/json"
    assert kwargs["json"]["response_format"][0]["schema"] == {"type": "object"}


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

        def generate_json(self, prompt, schema, *, previous_interaction_id=None):
            assert "source_video" not in prompt
            return GeminiJSONReply(valid_decisions(), "int-test", self.model)

    summary = run_api_first_director(run_dir=run, provider=Provider())

    assert summary["source_video_sent_to_ai"] is False
    plan = json.loads((run / "visual-plan.json").read_text(encoding="utf-8"))
    assert len(plan["visual_beats"]) == 2
    audit = json.loads((run / "api-first" / "director-run.json").read_text(encoding="utf-8"))
    assert audit["source_video_sent_to_ai"] is False
    assert audit["word_timestamps_sent_to_director"] is False
