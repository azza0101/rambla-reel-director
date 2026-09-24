# Visible social sessions — local patch, 2026-09-23

Status: implementation tested locally; real RAMBLA session acceptance pending.

## Evidence

The authenticated TikTok search page for `airplane window` contains 36 search
cards. The previous selectors match zero. Current cards use
`data-e2e="search_video-item"`; the scroll container is `main#grid-main`.
Card innerText can contain only a like count; image alt carries the description.

## Changes

- UI server owns one visible Playwright page per social profile.
- OPEN, VERIFY and search reuse that page. Keep its window open.
- Sourcing workers forward queries to the owning local server using an
  ephemeral token inherited from the launcher; credentials/cookies are not copied.
- Browser closes on server shutdown. Closing it manually causes the next
  operation to create a new visible context with the saved profile.
- FIND SOCIAL opens only the dialog; OPEN buttons explicitly open browsers.
- Unknown login state remains unknown, rather than claiming login failure.
- Current TikTok card selector, image descriptions and nested scrolling supported.

## Verification

554 tests passed; backend and launcher compiled. Tests cover page reuse,
reopening after manual close, worker forwarding, endpoint authentication,
current grid scope excluding notification links, and descriptions vs like counts.
Live DOM inspection confirmed 36 matching cards and thumbnail URLs.
This does not prove end-to-end RAMBLA sourcing or Instagram support.

## Remaining acceptance

Restart using RUN_RAMBLA_V5.cmd. Close old RAMBLA provider windows once.
OPEN TIKTOK, log in if required, KEEP the managed window open. VERIFY should
navigate that same window. Run one TikTok-only beat and inspect attempt rows.
No ASR or plan import is needed. Do not claim TESTABLE or publish a success SHA
until this real runtime gate passes.
