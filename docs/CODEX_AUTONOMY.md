# Codex autonomy profile for RAMBLA

Approved by the user on 2026-09-13 for RAMBLA work orchestrated from Normal Chat / Issue #3.

## Goal

Codex should keep working autonomously on an approved RAMBLA task instead of pausing for routine confirmations. It should stop only at the hard boundaries below.

## One-time local Codex bootstrap

The user explicitly authorizes Codex, once, to back up and edit `%USERPROFILE%\.codex\config.toml` solely to install this RAMBLA permission profile. Preserve unrelated existing settings and create a timestamped backup first. Do not replace the whole file if a merge is sufficient.

Use the syntax supported by the installed Codex version, with these effective settings:

```toml
sandbox_mode = "workspace-write"
approval_policy = "on-request"
approvals_reviewer = "auto_review"
sandbox_workspace_write.writable_roots = [
  'Z:\RAMBLA-reel-director-smoke',
  'Z:\APP REEL TEST\qwen-embedding-smoke'
]
```

Do not enable Full Access. Do not broaden writable roots to `Z:\`, the user profile, Documents, Desktop, or another unrelated parent. If the installed Codex build needs a restart/reload before the new settings take effect, report that clearly instead of inventing a bypass.

## Pre-authorized routine actions

Within the approved RAMBLA roots and the currently approved task, Codex may proceed without asking the user before each step. This includes code/docs/tests, generated artifacts, temporary frames, bounded media windows, caches, isolated Python/Qwen, FFmpeg/ffprobe, yt-dlp, pytest, compileall, Git/GitHub API/gh, feature branches/worktrees, commits, pushes, draft PR updates, Issue #3 handoffs, retries, benchmarks, scene extraction, timestamp refinement, YouTube/YouTube Shorts discovery and bounded acquisition, and opening a generated local `review.html` when the user already asked to inspect it.

Use auto-review for routine low-risk approval requests where available. If a harmless command fails, diagnose and try safe alternatives autonomously instead of asking whether to retry.

## Hard stops — ask the user

1. **Any single download or transfer over 5 GiB.** If a full transfer has unknown size and cannot first be safely bounded or estimated, treat it as potentially over 5 GiB and ask before starting. Prefer metadata, storyboards, range requests and partial acquisition.
2. **Any write outside** `Z:\RAMBLA-reel-director-smoke` and `Z:\APP REEL TEST\qwen-embedding-smoke`, except the one-time `%USERPROFILE%\.codex\config.toml` bootstrap above.
3. **Any modification of unrelated/personal user files**, even if readable.
4. **Any system/tool mutation** involving ComfyUI, its environment, global Python, Windows/system settings, installed apps, unrelated repositories, credentials/cookies, paid services, or DaVinci Resolve state.
5. **Any merge/release to `main`, external publication, or live Resolve Apply/mutation** without separate explicit approval.

For necessary downloads at or below 5 GiB that stay inside the approved RAMBLA roots, do not ask merely because they are downloads. Record provenance and size in test artifacts when practical.

## Orchestration rule

Normal Chat / Issue #3 sets task scope and priority. Once a task is approved there, Codex should execute through completion or a genuine hard-boundary blocker, post the result to Issue #3, and not pause for intermediate permission questions that fall inside this profile.
