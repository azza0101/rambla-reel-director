from pathlib import Path


def _fake_media_runner(command):
    Path(command[-1]).parent.mkdir(parents=True, exist_ok=True)
    Path(command[-1]).write_bytes(b"generated")


def _probe(_path):
    return {
        "duration": 8.0,
        "fps": 25.0,
        "width": 360,
        "height": 640,
        "has_audio": False,
    }


def test_text_source_builds_server_timeline_without_asr(tmp_path):
    from backend.app.curation_project import ProjectStore

    store = ProjectStore(tmp_path / "projects", probe_runner=_probe)
    project = store.create("Text only")
    updated = store.write_text_source(
        project.project_id,
        "Questa è una trascrizione completa già pronta.",
        command_runner=_fake_media_runner,
    )

    assert updated.source_video is not None
    assert Path(updated.source_video.path).name == "text-timeline.mp4"
    source = store.source_input(project.project_id)
    assert source["kind"] == "text"
    assert Path(source["text_path"]).read_text(encoding="utf-8") == "Questa è una trascrizione completa già pronta."


def test_audio_source_builds_server_timeline_and_guide(tmp_path):
    from backend.app.curation_project import ProjectStore

    store = ProjectStore(
        tmp_path / "projects",
        probe_runner=_probe,
        audio_probe_runner=lambda _path: 7.25,
    )
    project = store.create("Audio only")
    updated = store.write_primary_audio(
        project.project_id,
        "voice.m4a",
        [b"audio-bytes"],
        command_runner=_fake_media_runner,
    )

    assert updated.source_video is not None
    assert updated.guide_audio is not None
    assert Path(updated.source_video.path).name == "audio-timeline.mp4"
    assert updated.guide_audio.duration == 7.25
    assert Path(updated.guide_audio.path).is_file()
    assert store.source_input(project.project_id)["kind"] == "audio"


def test_direct_text_analysis_produces_word_timing_and_chunks(tmp_path):
    from backend.app.cloud_analyze_cli import transcript_from_text
    from backend.app.debug_run_cli import build_short_outline

    transcript = transcript_from_text("Prima frase. Seconda frase più lunga!")
    outline, chunks = build_short_outline(transcript)

    assert transcript["provider"] == "direct-text"
    assert transcript["timing_basis"] == "synthetic_text_timing"
    assert transcript["segments"][0]["words"]
    assert transcript["segments"][0]["start"] == 0.0
    assert transcript["segments"][-1]["end"] > transcript["segments"][0]["end"]
    assert outline["beats"]
    assert chunks
    assert all(row["end"] > row["start"] for row in chunks)


def test_groq_verbose_json_normalizes_word_timestamps():
    from backend.app.cloud_analyze_cli import _normalize_groq

    transcript = _normalize_groq({
        "language": "it",
        "segments": [
            {
                "start": 0.0,
                "end": 1.0,
                "text": "ciao mondo",
                "words": [
                    {"word": "ciao", "start": 0.0, "end": 0.4},
                    {"word": "mondo", "start": 0.4, "end": 1.0},
                ],
            }
        ],
    })

    assert transcript["provider"] == "groq"
    assert transcript["segments"][0]["words"][1]["text"] == "mondo"
    assert transcript["source_duration_seconds"] == 1.0


def test_groq_asr_multipart_form_encodes_repeated_timestamp_fields_as_bytes():
    import httpx

    from backend.app.cloud_analyze_cli import _groq_asr_form

    request = httpx.Request(
        "POST",
        "https://api.groq.com/openai/v1/audio/transcriptions",
        data=_groq_asr_form("whisper-large-v3-turbo", language="it"),
        files={"file": ("voice.flac", b"audio", "audio/flac")},
    )

    body = b"".join(request.stream)
    assert body.count(b'name="timestamp_granularities[]"') == 2
    assert b"word" in body
    assert b"segment" in body
    assert b'name="language"' in body


def test_cloud_analysis_provenance_matches_analysis_reuse_contract():
    from backend.app.cloud_analyze_cli import _analysis_provenance
    from backend.app.debug_run_cli import analysis_input_signature

    video = Path(__file__)
    guide = Path(__file__).parents[2] / "backend" / "app" / "cloud_analyze_cli.py"

    assert _analysis_provenance(video, guide) == analysis_input_signature(video, guide)


def test_cloud_worker_command_never_points_at_local_model_runtime(tmp_path, monkeypatch):
    from backend.app.debug_server import RunState, _command

    video = tmp_path / "timeline.mp4"
    video.write_bytes(b"video")
    run = tmp_path / "run"
    run.mkdir()
    monkeypatch.setenv("RAMBLA_RUNTIME_MODE", "cloud")

    analyze = RunState("abc", video, run, stage_type="analyze")
    analyze_command = _command(analyze)
    assert "backend.app.cloud_analyze_cli" in analyze_command
    assert "--model" not in analyze_command
    assert "--model-cache" not in analyze_command

    sourcing = RunState("def", video, run, stage_type="videos")
    sourcing_command = _command(sourcing)
    assert "backend.app.debug_run_cli" in sourcing_command
    assert sourcing_command[sourcing_command.index("--model-cache") + 1] == str(run / ".cloud-model-cache")


def test_cloud_ui_offers_video_audio_text_and_disables_local_gpu(monkeypatch):
    from backend.app.curation_ui_v2 import render_curation_page_v2

    monkeypatch.setenv("RAMBLA_RUNTIME_MODE", "cloud")
    html = render_curation_page_v2("cloud-test")

    assert 'id="choose">VIDEO<' in html
    assert 'id="chooseAudio">AUDIO<' in html
    assert 'id="audioSourceFile" type="file" accept="audio/*,video/*"' in html
    assert "VIDEO USATO COME AUDIO" in html
    assert "encodeURIComponent(g?.signature||Date.now())" in html
    assert "$('audioSource').load()" in html
    assert "sorgente attiva per l'analisi" in html
    assert 'id="originalGuide"' not in html
    assert 'id="replaceGuide"' not in html
    assert 'id="guideFile"' not in html
    assert 'class="sourcePreview"' in html
    assert 'id="pasteText">TEXT<' in html
    assert 'id="sourceText"' in html
    assert "CLOUD · GPU FREE" in html
    assert 'id="path" hidden' in html
    assert 'id="socialQwenV2" disabled' in html
    assert "visual_verify:false" in html


def test_desktop_api_uses_api_workers_but_keeps_local_social_controls(monkeypatch):
    from backend.app.curation_ui_v2 import render_curation_page_v2
    from backend.app.debug_server import RunState, _command

    monkeypatch.setenv('RAMBLA_RUNTIME_MODE','desktop_api')
    video=Path('video.mp4')
    command=_command(RunState('desktop',video,Path('run'),stage_type='analyze'))
    html=render_curation_page_v2('desktop-build')

    assert 'backend.app.cloud_analyze_cli' in command
    assert 'DESKTOP · GPU FREE' in html
    assert 'id="socialConnectionsV5" hidden' not in html
    assert 'id="path" hidden' not in html
