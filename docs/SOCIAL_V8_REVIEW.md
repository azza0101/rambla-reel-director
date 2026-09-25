# Social V8 — local implementation and acceptance

Approved scope: individual TikTok/Instagram verification, six compact portrait
cards on one horizontally scrollable row, hover previews, explicit full video
download, per-shot semantic ranking and overlay/diversity filtering.

## Implemented

- Individual verification never contacts the other provider. Search still uses
  only checked, verified providers; existing managed browser sessions are reused.
- Native portrait thumbnail preferred; landscape fallback is cropped, not
  stretched. Six columns remain one row on narrow screens via horizontal scroll.
- Hover after 500 ms prepares a bounded 3.5 s muted looping preview, cached by
  source URL. Leaving pauses playback. Failures remain visible, no automatic retry.
- Full downloads are explicit and separate from verified localized clip downloads.
  Asset ID resolves to a project-owned candidate; arbitrary media URLs are rejected.
  Existing pipeline Python/yt-dlp is used, no dependencies installed.
- Connected browser cookies are read without navigation, restricted to the provider,
  written temporarily for yt-dlp and removed in finally. They are never returned to UI.
- Two acquisition jobs maximum concurrently; duplicate requests serialize/cache.
- Qwen thumbnail evidence filters likely superimposed captions before clip acquisition;
  actual sampled clip frames have the same negative visual comparison. Physical signs
  are distinguished in the negative prompt. This is a heuristic, not OCR certification.
- Perceptual thumbnail duplicates removed; different creators prioritized;
  concrete shot relevance weighted above query similarity. No filler quota.
- Preview/download availability does not grant semantic verification or selectability.

## Evidence and limitations

569 tests passed, rendered JavaScript syntax passed, Python compilation passed.
New tests cover individual verification, portrait selection, bounded vs full
download, cookie cleanup/cache, project asset routes, overlays and visual duplicates.

A real unauthenticated yt-dlp request for the previously inspected TikTok clip
7490090345464630535 reached TikTok but returned login_required. Installed runtime
also warns no impersonation target exists; no package was installed. Authenticated
download and hover still require a live test on the updated user-launched server.
Do not label this TESTABLE or publish a success SHA for that unpassed gate.

Existing server 8817 owns the working TikTok browser. Its Python modules do not
hot-reload. Normal launcher reuses it intentionally. Do not start a competing server.
For one explicit version update, close RAMBLA provider windows once and run
RESTART_RAMBLA_V5.ps1 in user PowerShell. It stops only the exact project UI runtime's
curation servers on loopback ports 8810–8819; other Python and Chrome are untouched.
The agent cannot execute this restart: Win32_Process inspection is access denied.
After restart, open TikTok once, keep that window open, verify only TikTok and test
one existing beat. No ASR or reimport needed. Instagram remains optional.
