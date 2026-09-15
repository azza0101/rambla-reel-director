import asyncio
from types import SimpleNamespace

from backend.app.online_sourcing_cli import _source_outline, _YtDlpLogger


def test_ytdlp_logger_suppresses_only_python_notice(capsys):
    logger = _YtDlpLogger()
    logger.warning(logger.exact_notice + ".")
    logger.error("real provider failure")
    assert capsys.readouterr().err.strip() == "real provider failure"


def test_video_sourcing_emits_structured_slot_progress_with_truthful_providers():
    class Engine:
        max_queries = 3
        sources = [SimpleNamespace(provider_name="youtube"), SimpleNamespace(provider_name="pexels")]
        async def source_beat(self, **kwargs):
            return {"candidates": [{"id": "v1", "score": .8, "preview_path": "preview.mp4"}], "rejected_candidates": [{"id": "v2"}], "errors": [], "preview_cache_hits": 1, "proposals": {"proposal_A": {"id": "v1"}}}

    events = []
    def event(stage, progress, message, **data): events.append((stage, progress, message, data))
    outline = {"beats": [{"id": "beat-1", "start_seconds": 0, "end_seconds": 3, "intent": "artisan work", "broll_queries": ["artisan workshop"]}]}
    _, results, _ = asyncio.run(_source_outline(outline, Engine(), client_id="c", event_callback=event))
    assert results
    assert events[0][0] == "coverage" and events[0][3]["providers"] == ["youtube", "pexels"]
    assert {row[0] for row in events} >= {"online_search", "qwen_final", "bounded_acquisition", "review"}
    search = next(row for row in events if row[0] == "online_search")
    assert search[3]["query"] == ["artisan workshop"]
    assert search[3]["raw"] == 2 and search[3]["accepted"] == 1 and search[3]["rejected"] == 1
