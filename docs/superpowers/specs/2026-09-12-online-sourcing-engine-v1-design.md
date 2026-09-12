# RAMBLA Online Sourcing Engine V1 — Design

Status: **awaiting explicit user approval**

Date: 2026-09-12

## 1. Goal

Turn RAMBLA from a local-asset-first proof into an **online-sourcing-first AI reel director** that can take a 9:16 talking-head reel, understand where visuals help, search permitted online sources, evaluate candidates semantically and visually, persist an inspectable Edit Plan, and later apply approved choices to a duplicated Resolve timeline.

The engine remains the priority. The Resolve GUI is a thin client and may lag behind the backend as long as the backend is fast, inspectable, deterministic where possible, and safe.

## 2. Product behavior

For each semantic beat of the transcript, RAMBLA should decide whether to keep the speaker or add a visual intervention. When B-roll is appropriate, the normal path is:

1. understand the beat and generate concrete visual queries;
2. search enabled online providers in parallel;
3. normalize remote results into `VisualAsset` candidates with provenance;
4. cheaply filter by format, duration, aspect, availability, duplication, and basic metadata relevance;
5. fetch only the lightweight preview/keyframe material needed for visual ranking;
6. rank candidates with Qwen3-VL-Embedding-2B;
7. optionally rerank a small shortlist with Qwen3-VL-Reranker-2B or another compatible visual judge when benchmarked and enabled;
8. download the full-resolution selected asset only after selection;
9. cache metadata, preview, embedding, and selected media for reuse;
10. persist query, candidates, scores, provenance, selected asset, timing, and rationale in the Edit Plan and HTML review surface.

Local client assets remain supported, but as a **cache/reuse source**, not as a prerequisite for a useful run.

## 3. Open-source references and reuse policy

### B-Roll-Finder

Reference architecture only. Its public repository describes the exact useful pattern: transcript -> AI shot list -> Pexels/Pixabay/YouTube candidate fetch -> ranking -> human review/auto-select -> cached downloads -> editor export. It currently exposes no repository license, therefore RAMBLA must **not copy source code** from it unless a compatible license is later added. We may reuse concepts and independently implement them.

Useful ideas to reproduce independently:

- context-aware query generation anchored to the active subject;
- parallel fan-out to multiple providers;
- reviewable alternatives per shot;
- auto-selection with a variety guard;
- local cache/library built from previously confirmed downloads;
- one-click end-to-end mode plus step-by-step mode;
- optional final QA pass over the selected timeline.

### MoneyPrinterTurbo

MIT licensed. It already implements provider normalization for Pexels/Pixabay/Coverr, API-key handling, search/download caching, aspect filtering, public-source provenance records, and secret redaction. RAMBLA may reuse or adapt small MIT-compatible implementation patterns with attribution where code is copied substantially.

Useful ideas:

- provider-neutral normalized material records;
- safe public source records that never persist signed download URLs or credentials;
- deterministic aspect/orientation filtering;
- provider-specific rendition selection;
- cache/dedupe before re-downloading;
- robust timeout/error handling and secret redaction.

### AutoBroll

MIT licensed. Useful reference for the interaction model: AI chooses B-roll moments, Pexels supplies candidates, alternatives remain swappable, and remote/local media share one editing model. RAMBLA may adapt compatible patterns while keeping editorial intelligence and provider logic in the backend rather than the Resolve panel.

## 4. Architecture

Keep the approved **modular monolith with ports and adapters**.

New/expanded domain boundaries:

- `QueryPlanner`: produces 2–4 concrete visual search queries per B-roll-capable beat.
- `AssetSource`: provider-neutral async search interface.
- `RemoteCandidate`: normalized remote result before download.
- `CandidateFilter`: policy, duration, aspect, quality, duplicate, and metadata prefilter.
- `PreviewMaterializer`: downloads thumbnail/keyframe/low-bandwidth preview only.
- `EmbeddingProvider`: Qwen3-VL-Embedding-2B adapter.
- `RerankProvider`: optional Qwen3-VL-Reranker-2B adapter.
- `CandidateSelector`: score fusion, diversity guard, confidence threshold, and fallback.
- `AssetCache`: metadata + preview + embedding + full selected asset cache outside Git.
- `ProvenancePolicy`: provider/source/license/attribution and reuse eligibility.

The existing `ResolveAdapter`, Plan Service, Artifact Store, and review HTML remain downstream consumers. Analysis never mutates Resolve.

## 5. Provider interface

V1 online providers:

1. **Pexels** — first real end-to-end provider slice.
2. **Pixabay** — same normalized contract after Pexels is green.
3. **Coverr** — same normalized contract after Pexels/Pixabay.

Later providers:

- **YouTube discovery**: search and preview metadata are allowed as a separate adapter, but the engine must not assume arbitrary YouTube media is legally reusable. Each candidate carries rights/provenance state and can be blocked before download/apply.
- **Instagram/Reels**: deferred optional adapter. Authentication, scraping fragility, source rights, and platform changes make it unsuitable as a V1 dependency.

Provider contract concept:

```text
search(query, orientation, min_duration, max_duration, limit) -> RemoteCandidate[]
materialize_preview(candidate) -> PreviewAsset
materialize_selected(candidate, rendition_policy) -> CachedAsset
health() -> ProviderHealth
```

Provider failures are isolated. One provider timing out must not fail the run when another source can satisfy the beat.

## 6. Normalized candidate record

Each candidate must carry at least:

- stable provider + provider asset ID;
- public source page URL;
- creator/attribution when available;
- license or rights status as reported/derived by provider policy;
- search query that discovered it;
- title/description/tags;
- width, height, duration, orientation;
- preview URL and preview cache path;
- candidate rendition metadata;
- provider rank/order;
- metadata relevance score;
- Qwen embedding score;
- optional reranker score;
- final fused score;
- content hash when materialized;
- selected/full-download state.

Secret-bearing or temporary signed URLs must never be persisted in durable public provenance artifacts.

## 7. Query generation

The Director decides **whether** a B-roll intervention is editorially justified. QueryPlanner decides **what to search**.

For each eligible beat it receives:

- local transcript context;
- beat intent;
- active macro-subject/context from the surrounding transcript;
- Style DNA constraints;
- previous selected visuals to avoid repetition.

It emits several varied, visual-first queries rather than literal transcript keyword copies. Queries should specify subject/action/setting/camera intent when useful.

Example:

Narration: `Passavo ore a fare tutto manualmente e ogni progetto ripartiva da zero.`

Possible queries:

- `frustrated creative working repetitive tasks on computer at night`
- `video editor overwhelmed by repetitive workflow workstation`
- `manual repetitive computer work close up hands keyboard`

The engine preserves every generated query for review/debugging.

## 8. Fast ranking strategy

Speed comes from **not running the heavy visual model over full downloaded videos**.

Pipeline per beat:

1. fetch up to a bounded number of remote results per query;
2. dedupe identical provider/source IDs and near-identical metadata;
3. metadata prefilter to a small pool;
4. download thumbnails or provider previews only;
5. batch query + preview images/keyframes into Qwen3-VL-Embedding-2B;
6. cosine-rank all survivors;
7. only if configured, send top-K to the reranker;
8. apply diversity and confidence rules;
9. download full media only for selected result(s) and a small explicit alternate reserve.

For videos, V1 may start from provider thumbnail/keyframe preview. A later quality step can sample 3–5 frames from the shortlisted preview/full clip when measurements prove that single-frame ranking misses important content.

Embeddings are cached by `(provider, asset_id, preview_content_hash, embedding_model_version)` so repeated assets are not re-embedded.

## 9. Qwen roles

The currently validated real model is `Qwen3-VL-Embedding-2B`. Its role is remote/local visual semantic retrieval and ranking, not transcription.

Planned capability roles remain independent and lazy-loaded:

- transcription: Qwen3-ASR-1.7B or measured alternative;
- alignment: Qwen3-ForcedAligner-0.6B or measured alternative;
- editorial Director/query planner: Qwen3.5-4B initially;
- embedding: Qwen3-VL-Embedding-2B;
- reranking: Qwen3-VL-Reranker-2B;
- visual judge: optional and disabled by default until measurements justify it.

The Model Manager may keep only the currently useful model in VRAM. Fast profile may keep frequently reused models resident when VRAM measurements justify it; Low-VRAM profile unloads between stages.

## 10. Cache and storage

All runtime media remains outside Git, under the configured data root, with heavy experimental/model data currently under `Z:\APP REEL TEST`.

Cache layers:

- provider response cache with TTL;
- durable public provenance metadata;
- preview/thumbnail cache;
- embedding cache;
- selected full-resolution B-roll cache;
- optional confirmed-clip library for reuse across future runs for the same client.

The local library therefore grows as a **result of online sourcing**, not as a prerequisite.

## 11. Review surface and future Resolve GUI

The current HTML report is promoted into the first real review surface. For every B-roll beat it should show:

- transcript range;
- Director decision and rationale;
- search queries;
- provider/source;
- candidate thumbnails;
- embedding/reranker/final scores;
- selected candidate;
- public source link;
- rights/provenance state;
- cached/downloaded state;
- alternatives.

The later Resolve panel remains thin: start run, progress, inspect/replace/disable/regenerate decisions, approve plan, Apply. No provider or AI logic belongs in the panel.

## 12. Performance goals

These are benchmark targets, not unverified promises.

For a one-minute 9:16 reel on the user's RTX 4090, warm cache/model state:

- online search fan-out should run concurrently across queries/providers;
- preview downloads should be concurrent and bounded;
- Qwen embedding should batch candidates;
- full media should download only after selection;
- online sourcing + visual ranking should aim for **tens of seconds, not minutes**, under normal provider/network conditions;
- the full transcript-to-review plan target is initially **<= 60 s warm** for a typical one-minute reel, then optimized from measurements.

Every run records per-stage wall time, model load time, inference time, network/download time, cache hit rate, RAM, VRAM, provider result counts, and selected-candidate confidence.

## 13. Safety and failure behavior

- no Resolve mutation during Analyze;
- `REEL_MASTER` remains untouched;
- no secrets in Git, logs, provenance JSON, or review HTML;
- provider credentials are explicit local configuration;
- client caches remain isolated by default;
- no silent use of a source with unknown/blocked rights policy;
- provider/network failure degrades to remaining providers/local cache/talking-head rather than inventing a B-roll;
- low-confidence visual selection remains review-required instead of silently applied.

## 14. First implementation slice after approval

The first code slice should be deliberately small and real:

**existing transcript beat -> generated semantic query -> Pexels API search -> normalized candidates -> preview materialization -> real Qwen3-VL-Embedding-2B ranking -> selected remote B-roll -> persisted Edit Plan -> enhanced `review.html`.**

No Resolve mutation in this slice.

Tests must cover:

- provider normalization;
- no-key/401/429/timeout behavior;
- secret redaction;
- orientation/duration filtering;
- deterministic dedupe;
- preview cache behavior;
- Qwen provider contract via injected doubles plus one isolated real smoke benchmark;
- provenance persistence;
- plan validation with remote candidate;
- HTML rendering of source/score/alternatives;
- zero network calls in ordinary unit tests.

## 15. Follow-on order

After the Pexels slice is green and reviewed:

1. Pixabay adapter;
2. Coverr adapter;
3. multi-provider parallel fan-out + score normalization;
4. remote-download cache/library reuse;
5. Qwen reranker benchmark/integration;
6. multiple keyframe visual verification for shortlisted videos;
7. Director/query-planner real-model benchmark;
8. YouTube discovery with explicit rights gate;
9. Resolve panel review controls;
10. approved-plan Apply back into Resolve duplicate timeline.

Instagram/Reels remains later and optional unless the user explicitly promotes it after the stable stock-provider path is working.

## 16. Success criteria

This slice is successful when, on the user's real reel, RAMBLA can show a review page where at least one B-roll beat was sourced online from Pexels, ranked by the real Qwen embedding model, selected with inspectable scores/provenance, cached locally, and represented in a complete valid Edit Plan without touching Resolve.

The next quality gate is not merely whether a clip was found, but whether the user considers the selected clip editorially appropriate. Replacement/disable decisions become the primary signal for improving query planning and ranking.
