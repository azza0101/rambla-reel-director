import json
from pathlib import Path
import uuid

import pytest

from backend.app.visual_planner import ConcreteVisualPlanner, load_or_create_visual_plan


def response(subject="chef chopping onions"):
    return {"editorial_function": "explanation", "core_meaning": "Prepare ingredients", "subtext": "Show the practical step", "visual_mode": "single", "shots": [{"shot_id": "s1", "description": subject, "image_queries": [subject, subject + " kitchen"], "video_queries": [subject, subject + " closeup"]}], "avoid": ["unrelated stock"]}


@pytest.mark.parametrize("text,subject", [("Attiva l'autenticazione a due fattori.", "person typing authentication code"), ("Taglia la cipolla prima di soffriggerla.", "chef chopping onions"), ("Confronta entrate e spese ogni mese.", "person checking household bills")])
def test_director_generates_without_domain_templates(text, subject):
    prompts = []
    def generate(prompt):
        prompts.append(prompt)
        return json.dumps(response(subject))
    result = ConcreteVisualPlanner(generate=generate).plan([{"id": "c1", "text": text, "start": 0, "end": 3}], {})
    row = result["chunks"]["c1"]
    assert row["planner_provider"] == "Qwen3.5-4B"
    assert row["shots"][0]["description"] == subject
    assert "template_id" not in row
    assert row["image_queries"] == response(subject)["shots"][0]["image_queries"]
    assert text in prompts[0]


def test_context_repair_and_cache():
    root = Path.cwd() / ".test-debug-cli" / uuid.uuid4().hex
    root.mkdir(parents=True)
    chunks = [{"id": "a", "text": "The owner will not explain worker pay."}, {"id": "b", "text": "Silence."}, {"id": "c", "text": "Ask where the money goes."}]
    prompts = []
    def generate(prompt):
        prompts.append(prompt)
        return "invalid" if len(prompts) == 1 else json.dumps(response())
    result = load_or_create_visual_plan(chunks, {}, root, generate=generate)
    assert len(prompts) == 4
    assert all(text in prompts[2] for text in [chunks[0]["text"], "Silence.", chunks[2]["text"]])
    cached = load_or_create_visual_plan(chunks, {}, root, generate=lambda _: pytest.fail("valid plan not reused"))
    assert result["input_signature"] == cached["input_signature"]


def test_invalid_output_fails_without_template_fallback():
    with pytest.raises(ValueError, match="visual plan"):
        ConcreteVisualPlanner(generate=lambda _: '{"shots": []}').plan([{"id": "x", "text": "Unknown topic"}], {})
