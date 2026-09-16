"""Visible login helper for a RAMBLA-owned persistent browser profile."""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path


async def _run(profile_dir: Path, url: str) -> None:
    from playwright.async_api import async_playwright

    profile_dir.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        context = None
        failures: list[str] = []
        for channel in ("msedge", "chrome", None):
            try:
                kwargs = {
                    "user_data_dir": str(profile_dir),
                    "headless": False,
                    "accept_downloads": True,
                }
                if channel:
                    kwargs["channel"] = channel
                context = await playwright.chromium.launch_persistent_context(**kwargs)
                break
            except Exception as exc:
                failures.append(f"{channel or 'chromium'}:{type(exc).__name__}")
        if context is None:
            raise SystemExit("No supported Chromium browser available (" + ", ".join(failures) + ")")
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        print("RAMBLA social login browser opened. Log in normally, then close this browser window.", flush=True)
        try:
            while context.pages:
                await asyncio.sleep(0.5)
        except Exception:
            pass
        finally:
            try:
                await context.close()
            except Exception:
                pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("tiktok", "instagram"), required=True)
    parser.add_argument("--profile-dir", type=Path, required=True)
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    asyncio.run(_run(args.profile_dir.resolve(), args.url))


if __name__ == "__main__":
    main()
