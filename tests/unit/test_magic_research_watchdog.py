"""The MAGICO research worker must never block progress indefinitely."""
import asyncio


def test_magic_beat_research_times_out_and_records_failure(tmp_path, monkeypatch):
    import backend.app.curation_server as server
    from backend.app.debug_server import RunState

    state = RunState("test-research", tmp_path / "source.mp4", tmp_path / "run")
    state.research_options = {"magic_exact_query": True}
    monkeypatch.setattr(server, "MAGIC_RESEARCH_TIMEOUT_SECONDS", 0.01)

    async def stalled_research(_state, _beat, _mode):
        await asyncio.sleep(3600)

    asyncio.run(server._run_research_state(
        state, "beat-1", "append", ("youtube_shorts",), stalled_research
    ))
    assert state.status == "FAILED"
    assert "Ricerca MAGICO scaduta" in state.last_message
    assert state.process is None


def test_manual_beat_research_is_not_capped_by_magic_deadline(tmp_path, monkeypatch):
    import backend.app.curation_server as server
    from backend.app.debug_server import RunState

    state = RunState("test-manual", tmp_path / "source.mp4", tmp_path / "run")
    state.research_options = {"magic_exact_query": False}
    monkeypatch.setattr(server, "MAGIC_RESEARCH_TIMEOUT_SECONDS", 0.01)

    async def manual_research(_state, _beat, _mode):
        await asyncio.sleep(0.02)

    asyncio.run(server._run_research_state(
        state, "beat-1", "append", ("youtube_shorts",), manual_research
    ))
    assert state.status == "SUCCEEDED"
