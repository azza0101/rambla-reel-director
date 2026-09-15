# Imported-plan retrieval milestone

## Behavior

- Independent Social/YouTube and Stock/Pexels shelves, up to three playable previews each. Per-shot budgets preserve sequence coverage before alternatives.
- YouTube inspects six distributed 3.5-second windows per promising source. Pexels inspects four. Two actual frames per window are ranked against the exact supplied description and that shot's own query. The best verified window is retained; failed discovery leads never become normal selectable videos.
- Bounded YouTube byte-range streaming avoids downloading entire long videos. The fixed upstream bridge lasts only for the cut, with an 8 MB / 45 second transfer budget. MP4 playback, codec and duration are probed. Local acquisition does not require a browser or a new runtime.
- Images use configured Pexels first, configured Google second, Wikimedia fallback. Original queries precede at most six retrieval aliases. A lower-confidence but plausible image remains reviewable; condition contradictions and duplicate visuals are rejected.
- Visual counters distinguish healthy vs wilted plants, actual talking heads vs requested footage, subject-specific diagrams vs real footage, and seated passengers vs boarding. These are retrieval checks, not editorial generation. Scores are cosine relevance measurements, not probabilities. Videos require a mean score of at least 0.50; images use 0.42 with a 0.45 visual floor.
- Empty states distinguish configuration, request, dimensions, preview, localization, ranker, visual rejection and duplicate failures. Expandable diagnostics retain query, provider, score, source URL and source timing.
- Source/guide provenance allows existing analysis to be reused across retrieval changes. Legacy invalidation recognizes imported plans. Marker migration preserves the original transcript anchor and imported JSON.
- Desktop visual-beat rail is sticky and viewport-sized. Its list scrolls independently and centers the selected beat within the list. Mobile falls back to a bounded non-sticky rail.

## Reproduce

Use the existing project runtimes; install nothing. Reuse the imported run and pass `--beat-ids` to the image/video sourcing CLIs to scope provider work without modifying the canonical plan.

A read-only report with every local preview and diagnostic can be produced with:

```powershell
& '<existing-python>' tools/review_imported_retrieval.py --retrieval-root '<run>/editorial/<import-hash>' --output '<local-proof>/review'
```

Launch the published branch using the existing launcher:

```powershell
& 'Z:\APP REEL TEST\qwen-embedding-smoke\curation-ui-plain\tools\start_curation_acceptance.ps1'
```

No model inference or provider call is performed by the review tool. Private media, plans, credentials, proof JSON and caches stay local and are not published.

## Acceptance evidence

Real imported KURA project, 19 visual beats preserved; provider work scoped to three beats / seven supplied shots. No generated replacement plan and no ASR run.

| Case | Visible Social clips | Visible Stock clips | Images | Inspection |
|---|---:|---:|---:|---|
| Transport | 1 | 3 | 4 | Stock covers airplane, bus and pedestrian ferry boarding; Social shows bus boarding. |
| Local ideal | 2 | 3 | 4 | Guesthouse check-in, guide with group, outdoor chickens in photos; clips show chickens/garden. No convincing guesthouse/guide clips survived. |
| Wilted basil | 0 | 0 | 1 | Pexels shows visibly wilted/dry basil in a terracotta pot. Indoor setting, so balcony specificity remains unfulfilled and the image is marked for review. |

Eleven final source clips pass ffprobe (eight Pexels, three YouTube); nine are visible after independent three-card shelf limits. Nine images survive (eight Pexels, one Wikimedia). All eighteen visible media URLs returned HTTP 206 with exactly 1024 requested bytes in the in-process real-project API audit.

Actual YouTube examples:
- `https://www.youtube.com/watch?v=2jqEWW1_fZc`: 5.130–8.6335 s, bus boarding, score 0.6088. Creator text overlays remain visible.
- `https://www.youtube.com/watch?v=K5RvpLZVQLw`: 156.780–160.246667 s, chickens next to garden beds, score 0.61705. A wire run is visible: this does not prove unrestricted free range.
- `https://www.youtube.com/watch?v=fbS27UIpJ6I`: 2.595–6.053333 s, chickens in garden, score 0.556, review required.

Actual Stock examples: Pexels 10691578 (airplane, 4.950–8.470 s, 0.5818), 38836992 (bus, 29.925–33.405 s, 0.56525), 34208077 (ferry, 0.525–4.045 s, 0.6317).

Measured image sourcing: **199.5391 s**. Video discovery/localization with the preceding counter pass: **270.3382 s** under competing GPU load. Final real-Qwen re-ranking of already downloaded frames: **8.9481 s**, zero new provider searches. Earlier byte-range localization probe: **1.8769 s** for a 3.52-second local MP4. These are observed timings, not isolated hardware benchmarks; the final re-rank does not claim to repeat temporal discovery.

The final video provider run logged four Pexels timeouts, one YouTube clip extraction failure and one YouTube poster failure. Google was not configured. These failures remain visible in diagnostics; missing clips were not replaced with discovery thumbnails.

Rejected examples include an animated airplane-boarding simulation, seated-cabin ambience, guesthouse skyline filler, vehicle/empty ferry ramps, healthy plant alternatives and talking-head tutorials. The vehicle/empty-scene correction was checked with real Qwen against existing downloaded frames before final acceptance artifacts were saved.

The real project API returned `analysis_ready=true`, `editorial_plan_ready=true`, and POST Analyze returned `status=reused`. SHA256 checks preserved raw transcript, semantic chunks, beat outline, imported visual plan, analysis signature and source/guide provenance. No selections existed in this project's baseline; selection-preservation behavior is covered separately by regression tests. `resolve_calls=0`.

Verification: 354 Python tests, compilation on the existing Python 3.12 and 3.10 runtimes, and JavaScript controller checks for scoped rail centering, separate shelves, clip ranges, diagnostics and pending selection gates. Actual browser layout/launcher verification is a separate final gate; do not infer it from the controller test.

Product validation remains separate. The remaining subject/location details above are explicit review limitations.
