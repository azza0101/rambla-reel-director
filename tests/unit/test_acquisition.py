from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.acquisition import (
    AcquisitionError,
    AcquisitionRequest,
    YtDlpAcquisitionAdapter,
    build_ffmpeg_trim_command,
    trim_with_ffmpeg,
)


def test_ytdlp_fetches_only_bounded_window_with_margin(tmp_path: Path) -> None:
    request = AcquisitionRequest(
        source_url="https://www.youtube.com/watch?v=abc",
        start_seconds=452.0,
        end_seconds=456.0,
        margin_seconds=2.0,
        mode="video_window",
    )

    cmd = YtDlpAcquisitionAdapter().build_command(request, tmp_path / "window.mp4")

    assert cmd[0] == "yt-dlp"
    assert "--download-sections" in cmd
    section_index = cmd.index("--download-sections") + 1
    assert cmd[section_index] == "*450.000-458.000"
    assert "--merge-output-format" in cmd
    assert "mp4" in cmd
    assert "--force-keyframes-at-cuts" not in cmd
    assert cmd[-1] == "https://www.youtube.com/watch?v=abc"


def test_ytdlp_window_margin_never_goes_before_zero(tmp_path: Path) -> None:
    request = AcquisitionRequest(
        source_url="https://www.youtube.com/watch?v=abc",
        start_seconds=0.5,
        end_seconds=4.0,
        margin_seconds=2.0,
        mode="video_window",
    )

    cmd = YtDlpAcquisitionAdapter().build_command(request, tmp_path / "window.mp4")

    section = cmd[cmd.index("--download-sections") + 1]
    assert section == "*0.000-6.000"


def test_ffmpeg_trim_command_uses_exact_local_window(tmp_path: Path) -> None:
    source = tmp_path / "wide.mp4"
    output = tmp_path / "trim.mp4"

    cmd = build_ffmpeg_trim_command(source, output, start_seconds=2.0, end_seconds=5.5)

    assert cmd == [
        "ffmpeg", "-y", "-ss", "2.000", "-to", "5.500", "-i", str(source),
        "-c", "copy", str(output),
    ]


def test_trim_with_ffmpeg_uses_injected_runner_and_requires_output(tmp_path: Path) -> None:
    source = tmp_path / "wide.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "trim.mp4"
    seen: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        seen.append(cmd)
        Path(cmd[-1]).write_bytes(b"trimmed")

    result = trim_with_ffmpeg(
        source,
        output,
        start_seconds=2.0,
        end_seconds=5.5,
        runner=runner,
    )

    assert seen
    assert result == output
    assert output.read_bytes() == b"trimmed"


def test_acquisition_errors_do_not_echo_signed_or_secret_url(tmp_path: Path) -> None:
    request = AcquisitionRequest(
        source_url="https://example.com/video?id=abc&token=SUPERSECRET",
        start_seconds=10.0,
        end_seconds=14.0,
        margin_seconds=1.0,
        mode="video_window",
    )

    def fail(_cmd: list[str]) -> None:
        raise RuntimeError("runner failure containing SUPERSECRET")

    adapter = YtDlpAcquisitionAdapter(runner=fail)

    with pytest.raises(AcquisitionError) as exc:
        adapter.acquire(request, tmp_path / "out.mp4")

    assert exc.value.code == "process_failed"
    assert "SUPERSECRET" not in str(exc.value)
    assert "token=" not in str(exc.value)


def test_request_rejects_bad_ranges() -> None:
    with pytest.raises(ValueError, match="time range"):
        AcquisitionRequest(
            source_url="https://www.youtube.com/watch?v=abc",
            start_seconds=5.0,
            end_seconds=5.0,
            margin_seconds=1.0,
            mode="video_window",
        )
