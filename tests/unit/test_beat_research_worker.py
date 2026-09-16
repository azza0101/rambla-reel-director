from pathlib import Path


def test_scoped_video_command_targets_one_beat_and_research_mode():
    from backend.app.debug_research_cli import video_sourcing_command

    command = video_sourcing_command(Path("run"), Path("transcript.json"), Path("outline.json"), "client", 300, beat_id="beat-7", research_mode="append")
    assert "--beat-ids" in command
    assert command[command.index("--beat-ids") + 1] == "beat-7"
    assert "analyze" not in command


def test_scoped_image_command_targets_one_beat_and_research_mode():
    from backend.app.debug_research_cli import image_sourcing_command

    command = image_sourcing_command(Path("run"), Path("chunks.json"), Path("outline.json"), "client", beat_id="beat-7", research_mode="replace")
    assert "--beat-ids" in command
    assert command[command.index("--beat-ids") + 1] == "beat-7"
    assert "analyze" not in command


def test_research_stage_name_encodes_beat_and_mode_without_analyze():
    from backend.app.debug_research_cli import research_stage_type, parse_research_stage

    stage = research_stage_type("beat-12", "append")
    assert stage == "research:append:beat-12"
    assert parse_research_stage(stage) == ("beat-12", "append")
    assert "analyze" not in stage
