from pathlib import Path


def test_register_local_video_persists_read_only_source_metadata(tmp_path):
    from backend.app.curation_project import ProjectStore

    source = tmp_path / "input.mp4"
    source.write_bytes(b"video")
    store = ProjectStore(tmp_path / "projects", probe_runner=lambda _: {
        "duration": 12.5, "fps": 25.0, "width": 1920, "height": 1080, "has_audio": True,
    })
    project = store.create("Demo")
    updated = store.register_local_video(project.project_id, source)
    assert updated.source_video.path == str(source.resolve())
    assert updated.source_video.duration == 12.5
    assert updated.source_video.has_audio is True
    assert source.read_bytes() == b"video"


def test_source_audio_extracts_once_for_unchanged_source(tmp_path):
    from backend.app.curation_project import ProjectStore

    source = tmp_path / "input.mp4"
    source.write_bytes(b"video")
    calls = []
    store = ProjectStore(tmp_path / "projects", probe_runner=lambda _: {"duration": 2, "fps": 25, "width": 1, "height": 1, "has_audio": True}, audio_probe_runner=lambda _: 2.0)
    project = store.register_local_video(store.create("Demo").project_id, source)
    def runner(command):
        calls.append(command)
        Path(command[-1]).write_bytes(b"wav")
    first = store.extract_source_audio(project.project_id, command_runner=runner)
    second = store.extract_source_audio(project.project_id, command_runner=runner)
    assert first.path == second.path
    assert len(calls) == 1
    assert ["-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le"] == calls[0][calls[0].index("-ac"):calls[0].index("-c:a") + 2]
