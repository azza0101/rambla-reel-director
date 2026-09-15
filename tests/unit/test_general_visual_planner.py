import json
from pathlib import Path
import uuid

import pytest

from backend.app.visual_planner import ConcreteVisualPlanner, load_or_create_visual_plan


def response(subject="chef chopping onions"):
    return {"editorial_function": "explanation", "core_meaning": "Prepare ingredients", "subtext": "Show the practical step", "visual_mode": "single", "shots": [{"shot_id": "s1", "description": subject, "image_queries": [subject, subject + " kitchen"], "video_queries": [subject, subject + " closeup"]}], "avoid": ["unrelated stock"]}


def test_local_generator_uses_chat_tokenizer_terminator():
    from types import SimpleNamespace
    from backend.app.qwen_stack import LocalQwenDirectorGenerator, QwenConfig
    class Inputs(dict):
        def to(self, device):
            return self
    calls = []
    generator = LocalQwenDirectorGenerator(QwenConfig(Path('unused')))
    generator.model = SimpleNamespace(device='cpu', generate=lambda **kwargs: calls.append(kwargs) or [[1, 2, 3]])
    generator.processor = SimpleNamespace(
        tokenizer=SimpleNamespace(eos_token_id=248046),
        apply_chat_template=lambda *args, **kwargs: Inputs(input_ids=SimpleNamespace(shape=(1, 1))),
        decode=lambda *args, **kwargs: '{}',
    )
    assert generator('context') == '{}'
    assert calls[0]['eos_token_id'] == 248046
    assert generator.completed_calls == 1


def test_analysis_query_helper_has_no_domain_translation_templates():
    from backend.app.debug_run_cli import semantic_query_variants
    queries = semantic_query_variants("turismo sostenibile elefanti")
    assert all("documentary photography" not in q and "sanctuary" not in q and "tourism" not in q for q in queries)


@pytest.mark.parametrize("description", ["A montage of an airport, a bus, and a boat", "A split view of two login forms"] )
def test_composite_shots_require_regeneration(description):
    from backend.app.visual_planner import validate_plan
    with pytest.raises(ValueError, match="separate"):
        value = response()
        value["shots"][0]["description"] = description
        validate_plan(value)

