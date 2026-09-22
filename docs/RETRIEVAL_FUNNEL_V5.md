# Retrieval funnel V5 — measured acceptance, 22 September 2026

## Cause and resulting behavior

The quality retrieval branch never populated proposals. It also acquired alternatives inside each provider/shot loop, blocked the event loop during synchronous YouTube search and Qwen calls, and discarded process-only caches between CLI invocations. Envato relied on fragile HTML/browser extraction; Google consent/parser failures became apparent empty searches. Discovery cards lacked shot IDs needed for shelf balancing.

The flow is now: imported shot -> bounded query expansion -> concurrent provider discovery -> cheap physical-target gate -> one primary verified clip per shot -> proposals rebuilt after dedupe -> shot-balanced curation shelves. Envato and Google stay discovery-only. TikTok/Instagram remain explicit social actions; Shorts has its own one-query lane. No automatic alternatives are acquired in this first-coverage pass.

Limits: 4 active shots, 6 discovery tasks, per-adapter diagnostic serialization, 2 clip downloads, 1 Qwen call. Each query returns at most 5 candidates; at most 2 acquisition attempts per provider/shot. Provider query budgets: Pexels 2, Envato 1, Google 1, YouTube 2, Shorts 1. YouTube long uses up to six storyboard cells, one ranking batch, one timestamp and one 3.5-second window. A storyboard no-match prevents a download; a missing storyboard permits one fallback window.

## Real benchmark

| Video sourcing for beat_002 | Before | After |
|---|---:|---:|
| Application-cache-cold isolated run | 29.4732 s baseline | 10.5630 s |
| Real product research worker, cold | — | 10.3604 s |
| Isolated warm run, new process | — | 0.0637 s |
| Verified candidates | 3 (2 airplane, 1 bus, 0 ferry) | 3 (1 per shot) |
| Proposals | 0 | 3, NEEDS_REVIEW |
| Envato cards in curation shelf | 0 useful reported | 3, one per shot |
| Resolve calls | 0 | 0 |

Cold means a fresh application cache and a new Python/model process; OS/CDN caches are not cleared. Timings measure the sourcing function, excluding Python process startup and image sourcing. Earlier diagnostic runs are retained locally, including the 33.1908-second run without Pexels. Pexels was missing from V5 configuration; the already-authorized project key was restored locally, never committed.

Cold model load: 6.4617 seconds, included in Qwen work. Per-shot work, seconds:

| Shot | Search | Metadata | Storyboard | Qwen | Clip | Final frame extraction | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| Airplane | 1.9354 | .0020 | 0 | 7.4456 | .3576 | .1640 | 10.0316 |
| Bus | 4.0178 | .0018 | 0 | .2884 | .3871 | .1715 | 10.3276 |
| Ferry | 5.8104 | .0017 | 0 | .1980 | .3228 | .1948 | 10.5320 |

These shots selected Pexels, so no YouTube storyboard/download was needed in this final run. The preceding real YouTube run exercised storyboard localization and no-match rejection. Stage work overlaps; queue waits and poster I/O explain differences from total wall time. Qwen time includes final-frame ranking and is reported separately from frame extraction. Full 20–25-shot cold latency has **not** been measured; do not extrapolate a full-reel SLA from this beat.

Final candidates are borderline, explicitly NEEDS_REVIEW (approximately .599, .538, .503). The ferry shows an aerial crossing; visible luggage is not established. A docked ferry was caught in manual preview inspection and now fails the moving-versus-stationary metadata regression. These are review suggestions, not assertions that every requested detail is present.

## Envato and Google evidence

Official documentation: https://elements.envato.com/learn/envato-mcp-server . The published endpoint https://mcp.envato.com/mcp returned HTTP 200 for initialize, tools/list and search_stock_video. RAMBLA now uses this structured search directly with the existing HTTP client; no additional installation, LLM dependency, authentication-profile scraping or automated licensing/download.

Real cards passed through curation and their thumbnails returned HTTP 200 image/jpeg:

- View From Window of an Airplane During Takeoff or Landing — https://elements.envato.com/view-from-window-of-an-airplane-during-takeoff-or--3XSG54X
- close up of a downtown area shuttle bus — https://elements.envato.com/close-up-of-a-downtown-area-shuttle-bus-SWUFLER
- Top Down Aerial View of Car Ferry Crossing Calm River — https://elements.envato.com/top-down-aerial-view-of-car-ferry-crossing-calm-ri-Y8WPRJZ

Envato discovery relevance is metadata-based, not a verified clip. Its official service is documented as a proof of concept and may change. The API has a 60-character query limit; longer queries are truncated at that boundary. Raw/parsed/valid/retained/surfaced counts and method/parser/error are recorded per query. Surfaced counts follow the three-card shot-balanced UI shelf.

Google's actual HTTP response was inspected and saved locally: a 200 consent page with no video-result anchors; other searches produced parser mismatches. The scoped pipeline browser fallback is unavailable. These are explicit request/method failures, not zero provider hits. Browser fallback remains at most once per run. No claim is made that Google is currently working.

## Cache and checks

Client/project-local caches: search queries 1 hour; YouTube metadata 1 hour; direct media URLs 15 minutes; embedding vectors 30 days with file size/mtime keys; verified shot outcome 5 minutes. Shot keys include full intent, queries, providers and ranking mode. Cached attempts are marked as cached and current-run request/download counts are zero. Failures in a cached shot remain visible. Existing thumbnail/storyboard/clip files are reused.

524 tests pass, backend compile passes, rendered V5 JavaScript passes node --check. Regression coverage includes stale queries, storyboard rejection without download, three-shot coverage/proposals, discovery shelf identity, explicit zero diagnostics, default social exclusion, changed-intent cache invalidation, diegetic signs and moving/stationary contradictions. Test runner temporarily maps mkdir mode 0700 to ordinary Windows directory mode because this sandbox otherwise makes pytest-created directories unreadable; no system permissions/configuration were changed.

The real product worker used the current imported plan and cached transcript. Input hashes for visual-plan.json, semantic-chunks.json and transcript-raw.json were unchanged. Existing other beats were retained by the normal research merge. PR #10 stays draft; no merge.

Changed implementation: quality_video.py, funnel_runtime.py, funnel_cache.py, online_sourcing.py, online_sourcing_cli.py, youtube_source.py, vertical_social.py, qwen_stack.py, retrieval_quality.py, envato_source.py, web_video_source.py, curation_ui.py, curation_ui_v2.py, curation_server.py. Tests and this report accompany the change.
