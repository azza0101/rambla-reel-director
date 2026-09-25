# Per-shot retrieval funnel implementation plan

Goal: make APP REEL V5 sourcing bounded, observable and reusable, preserving the imported plan.

## Inspection before edits

Baseline: detached V5 checkout 8863de3, remote branch feat/api-first-text-first-v1. Working tree initially clean. Latest commits changed Envato from user-profile browsing to public browsing and bypassed the relevance gate for its cards. Benchmark artifact in project fea7fff128ef confirms 29.4732 seconds, three candidates, zero proposals.

Flow: editorial_import.retrieval_bundle -> coverage.plan_coverage_slots (one imported shot per slot) -> editorial_relevance.build_retrieval_spec -> quality_video query sanitation/expand_queries -> OnlineSourcingEngine._search_one -> provider adapters -> metadata gate -> cached poster -> YouTube storyboard -> bounded clip -> three frame QualityRanker -> per-slot candidates -> cross-slot diversity -> coverage proposals -> online-candidates/edit-plan -> curation_artifacts.load_curation_run -> curation shelf -> curation_ui_v2.

Root causes:
- quality_video initializes empty proposals and never fills them; review counts cannot reflect accepted clips.
- provider discovery is interleaved with downloads, and two accepted alternatives are sought per provider before completing other slots.
- search, YouTube metadata and Qwen vectors are process-only caches; CLI workers lose them on every NEW SEARCH.
- Envato swallows HTTP errors, falls back to a serialized browser, and bypasses relevance entirely. Google similarly collapses failures into zero rows.
- shared mutable provider last_attempt and vertical attempt buffers can associate one shot's diagnostics with another query.
- discovery rows do not receive shot_id, so curation balancing cannot preserve shot coverage.
- UI Envato empty copy has no attempt state.
- existing storyboard already uses six frames, one positive inference and one selected timestamp. Keep this working path; the unused two-window helper is not the active bottleneck.

## Approved implementation sequence

- [ ] Regression tests: proposals, first coverage, persistent cache, provider diagnostics and official MCP parsing; retain storyboard rejection and no-social/no-Resolve tests.
- [ ] Official Envato MCP search adapter (HTTP 200/tools schema and real stock-video response verified Sept 22); explicit error/zero/count diagnostics. Discovery only, no licensing/download.
- [ ] Shared bounded discovery, download and serialized Qwen lanes; first verified clip per shot, no automatic alternatives. Durable client-scoped query/metadata/vector/verification caches with versioning and TTL.
- [ ] Proposals reconstructed after dedupe; shot IDs on all rows; diagnostics and Envato UI copy carry actual execution counts.
- [ ] Real beat_002 cold/warm runs using cached transcript/plan, full pytest, backend compile, rendered JS syntax; publish verified file set to existing branch via API, keep PR draft and do not merge.

No ASR, plan regeneration, installs, Resolve calls or system/runtime changes. Timing sums are work time, not necessarily wall time when lanes overlap. A discovery card does not prove a clip is visually verified.
