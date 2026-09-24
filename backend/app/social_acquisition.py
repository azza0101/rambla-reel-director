"""Authenticated bounded acquisition helpers for TikTok and Instagram.

Cookie/profile values are process-local inputs only. Public exceptions and logs
must never reveal profile paths or cookie material.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


SOCIAL_PROVIDERS = {"tiktok", "instagram"}
ACQUISITION_STATES = {"CLIP_READY", "PREVIEW_ONLY", "MANUAL_LINK"}


class SocialAcquisitionError(RuntimeError):
    pass


def browser_cookie_specs(profile_dir: Path) -> tuple[str, ...]:
    directory = str(Path(profile_dir).resolve())
    # RAMBLA login prefers Edge, then Chrome, then bundled Chromium. Try the
    # corresponding yt-dlp cookie backends in the same order without exposing
    # the path outside this helper.
    return (
        f"edge:{directory}",
        f"chrome:{directory}",
        f"chromium:{directory}",
    )


def redact_sensitive_command(command: list[str]) -> str:
    output: list[str] = []
    redact_next = False
    for part in command:
        if redact_next:
            output.append("[REDACTED_BROWSER_PROFILE]")
            redact_next = False
            continue
        output.append(str(part))
        if part in {"--cookies-from-browser", "--cookies"}:
            redact_next = True
    return " ".join(output)


def profile_root_from_env() -> Path:
    value = os.environ.get("RAMBLA_BROWSER_PROFILE_ROOT", "").strip()
    if value:
        return Path(value)
    return Path.home() / ".rambla-reel-director" / "browser-profiles"


def download_authenticated_section(
    source_page: str,
    provider: str,
    output_path: Path,
    *,
    start: float,
    duration: float,
    profile_root: Path | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> Path:
    clean = str(provider or "").casefold().strip()
    if clean not in SOCIAL_PROVIDERS:
        raise ValueError("unsupported authenticated social provider")
    if not str(source_page).startswith(("https://", "http://")):
        raise ValueError("public source URL required")
    if start < 0 or duration <= 0:
        raise ValueError("invalid bounded social window")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    endpoint=os.environ.get('RAMBLA_SOCIAL_SESSION_URL','')
    if endpoint:
        # The UI server owns the live profile. Reading its SQLite cookie file
        # while Chrome is open fails; use the authenticated loopback bridge.
        from urllib.parse import urlsplit
        import httpx
        import tempfile
        parsed=urlsplit(endpoint)
        if parsed.scheme!='http' or parsed.hostname!='127.0.0.1':
            raise SocialAcquisitionError('invalid local session endpoint')
        cookie_path=None
        try:
            with httpx.Client(timeout=10,trust_env=False) as client:
                response=client.post(endpoint.rstrip('/')+f'/api/curation/social/{clean}/session-cookies',
                                     headers={'X-Rambla-Session':os.environ.get('RAMBLA_SOCIAL_SESSION_TOKEN','')})
                response.raise_for_status()
                cookies=response.json()['cookies']
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',suffix='.cookies',dir=output_path.parent,delete=False) as handle:
                cookie_path=Path(handle.name);handle.write('# Netscape HTTP Cookie File\n')
                for c in cookies:
                    domain=str(c.get('domain',''))
                    if domain.lstrip('.').removeprefix('www.')!=clean+'.com':continue
                    fields=[domain,'TRUE' if domain.startswith('.') else 'FALSE',str(c.get('path') or '/'),
                            'TRUE' if c.get('secure') else 'FALSE',str(max(0,int(c.get('expires') or 0))),str(c.get('name','')),str(c.get('value',''))]
                    if not any('\n' in v or '\r' in v or '\t' in v for v in fields):handle.write('\t'.join(fields)+'\n')
            runner([sys.executable,'-m','yt_dlp','--no-playlist','--no-warnings','--socket-timeout','12','--retries','0',
                    '--cookies',str(cookie_path),'--download-sections',f'*{start:.3f}-{start+duration:.3f}',
                    '--force-keyframes-at-cuts','-f','b[height<=1080]/best[height<=1080]/best','--merge-output-format','mp4',
                    '-o',str(output_path),source_page],check=True,capture_output=True,text=True,encoding='utf-8',timeout=55)
            if output_path.is_file() and output_path.stat().st_size:return output_path
            raise SocialAcquisitionError('provider did not supply a clip')
        except Exception:
            raise SocialAcquisitionError('live-session clip acquisition failed') from None
        finally:
            if cookie_path:cookie_path.unlink(missing_ok=True)
    profile_dir = Path(profile_root or profile_root_from_env()) / clean
    end = start + duration
    failures = 0
    for cookie_spec in browser_cookie_specs(profile_dir):
        command = [
            sys.executable, "-m", "yt_dlp",
            "--no-playlist", "--no-warnings", "--socket-timeout", "12", "--retries", "0",
            "--cookies-from-browser", cookie_spec,
            "--download-sections", f"*{start:.3f}-{end:.3f}",
            "--force-keyframes-at-cuts",
            "-f", "b[height<=1080]/best[height<=1080]/best",
            "--merge-output-format", "mp4",
            "-o", str(output_path),
            source_page,
        ]
        try:
            runner(
                command,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=55,
            )
            if output_path.is_file() and output_path.stat().st_size > 0:
                return output_path
        except Exception:
            failures += 1
            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                pass
    raise SocialAcquisitionError("authenticated social download failed")


def fallback_acquisition_state(*, has_preview: bool, reason: str | None = None) -> dict[str, Any]:
    return {
        "acquisition_state": "PREVIEW_ONLY" if has_preview else "MANUAL_LINK",
        "manual_reason": str(reason or ("automatic download unavailable" if has_preview else "preview unavailable; open source manually")),
        "clip_verified": False,
        "selectable": False,
    }
