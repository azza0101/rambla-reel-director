# RAMBLA Resolve Panel + Evidence Sourcing V2 — Design

Status: **APPROVED IN CHAT on 2026-09-12; written-spec review pending**

Date: 2026-09-12

## 1. Product direction

RAMBLA should feel like a **DaVinci Resolve plugin/panel** to the editor, while keeping the heavy intelligence in a separate local backend process.

The product split is:

- **Resolve Panel**: thin UI for Analyze, progress, A/B candidate review, disable/replace/regenerate, approval, Apply, and Undo/rollback visibility.
- **RAMBLA Engine**: transcript, semantic understanding, coverage-slot planning, online discovery, scene localization, visual ranking, crop analysis, partial acquisition, caching, Edit Plan generation, and benchmarking.
- **Resolve Apply Adapter**: interchangeable final execution backend. MCP is supported as one adapter; native Resolve scripting/API remains another adapter. The Director and sourcing engine never depend on MCP.

Analysis must complete into an inspectable Edit Plan before any Resolve mutation occurs.

## 2. Editorial target

Reference direction: high-density evidence/storytelling reels in the style family discussed by the user (for example Olimpia Peroni / Factanza), where visual inserts usually illustrate the exact person, event, post, place, product, document, statistic, or source being discussed rather than relying mainly on generic stock footage.

The engine therefore plans **coverage slots**, not one B-roll per semantic beat.

Default coverage behavior:

- target visual insertion duration: **about 3–4 seconds**;
- configurable soft range: approximately **2.5–4.5 seconds**;
- a longer semantic beat may contain multiple coverage slots separated by talking-head intervals;
- the speaker remains the narrative spine; RAMBLA must not cover the whole reel continuously;
- every proposed coverage slot should retain **at least two usable alternatives** when sourcing succeeds;
- no requirement that source media be vertical.

These values are Style DNA parameters, not hard-coded universal constants.

## 3. Source priority: evidence first, stock later

Provider priority is based on editorial specificity, not provider convenience.

Preferred source classes:

1. **Exact evidence / exact subject** — original or directly relevant social post, interview, article, public video, event footage, product/person/place imagery, screenshots, documents, charts.
2. **Closely related editorial/repertory material** — footage that directly illustrates the named subject or event.
3. **Semantic stock footage** — Pexels, Pixabay, Coverr and similar providers as useful fallback when exact evidence is unavailable or inappropriate.

The Query Planner may generate multiple query families for one slot: exact-entity search, event/context search, and generic visual fallback.

## 4. Coverage-slot planning

A new `CoveragePlanner` sits downstream of transcript/semantic beats and upstream of sourcing.

For each beat it decides:

- whether visual coverage is justified;
- one or more `[start, end)` coverage slots;
- target duration and acceptable duration range;
- visual intent;
- evidence class preference;
- search queries;
- whether still/screenshot evidence is acceptable;
- crop constraints and subject importance;
- minimum number of alternatives desired (default 2).

Example:

```text
Beat 18.0–27.0 s
Narration: ...
Coverage slot A: 19.1–22.6 s, target 3.5 s
Coverage slot B: 24.0–27.0 s, target 3.0 s
```

The Edit Plan stores coverage slots explicitly instead of treating the whole beat as a single B-roll interval.

## 5. Aspect ratio and crop safety

Online search must **not filter to portrait-only media**.

Landscape, square, 4:3, portrait, and other practical source formats may all enter the candidate pool.

A `CropSafetyEvaluator` estimates whether a candidate can be used inside a 9:16 deliverable. It records:

- source dimensions/aspect;
- likely important subject region;
- proposed 9:16 crop window;
- crop-safety score;
- whether subject tracking/reframing is likely needed;
- hard rejection only when the important content cannot reasonably survive the crop.

Crop safety participates in final ranking but does not override semantic relevance blindly. Resolve Apply later receives the chosen crop/scale/position metadata.

## 6. At least two proposals per coverage slot

`CandidateSelector` returns a small **proposal set**, not one hidden winner.

Default persisted result per slot:

- `proposal_A`: recommended choice;
- `proposal_B`: strongest meaningfully different alternative;
- optional `proposal_C`: fallback/reserve when available.

Diversity rules should avoid returning two near-identical clips from the same source when a useful alternative exists.

The review UI must allow A/B switching without rerunning discovery.

## 7. Long-video scene localization

RAMBLA must avoid downloading or decoding an entire long video merely to find a 3–4 second insert.

Introduce `SceneLocator` with a coarse-to-fine strategy:

1. obtain inexpensive remote metadata, thumbnails, storyboard frames, preview frames, captions/transcript snippets, or other source-supported lightweight evidence;
2. identify promising coarse time regions;
3. sample/refine only around those regions;
4. use Qwen visual/text similarity and available metadata to score candidate windows;
5. return one or more source time ranges, e.g. `07:32.0–07:36.5`;
6. acquire only a bounded window around the selected range.

Exact frame-perfect remote cuts are not required. A practical strategy is to fetch a slightly wider interval and trim locally with FFmpeg.

## 8. Partial acquisition and screengrabs

Introduce an `AcquisitionAdapter` per source type.

Capabilities may include:

- `fetch_time_window(source, start, end, margin)`;
- `fetch_preview_frames(source, timestamps)`;
- `capture_still(source, timestamp)`;
- `fetch_page_screenshot(source)` where permitted;
- `fetch_selected_asset(...)` for normal stock providers.

For YouTube/social/web sources, RAMBLA should prefer **partial acquisition** or still/screenshot evidence where technically and policy-wise permitted, rather than full-video downloads.

Fallback hierarchy for a promising source:

1. short local video window;
2. short preview/transcoded window;
3. frame grab / screenshot with provenance;
4. source link only, marked review-required;
5. next candidate/provider.

Every acquired artifact preserves source URL, timestamp/range, discovery query, provider/extractor, and rights/provenance state. No credentials or signed URLs are persisted.

## 9. Social and web adapters

Social/web sources are pluggable and failure-tolerant.

Initial architecture supports adapters for:

- YouTube discovery / scene acquisition;
- Instagram/Reels discovery where access is available;
- TikTok discovery where access is available;
- generic web/article/image/screenshot evidence;
- Pexels/Pixabay/Coverr stock fallback.

Social adapters must not be foundational dependencies because authentication, extractor support, platform changes, and rights vary. If a source cannot be fetched, RAMBLA records the failure and continues with alternatives.

The system does not assume that every discovered online asset is automatically publishable. Provenance and rights state remain first-class review fields.

## 10. Ranking model

Candidate scoring becomes multi-factor:

- semantic/evidence relevance;
- entity/event specificity;
- Qwen visual embedding score;
- optional reranker/judge score;
- crop-safety score;
- temporal-window quality;
- technical quality;
- source/rights policy;
- diversity penalty;
- prior user acceptance/rejection signals later.

Qwen3-VL-Embedding-2B remains the currently validated visual-semantic model. It ranks preview frames/window representatives before large media is acquired.

## 11. Transcription strategy

Transcription is a replaceable provider, not tied permanently to one model.

At minimum RAMBLA supports two candidate paths:

- **Resolve transcription** when accessible through the installed Resolve/API/workflow path;
- **RAMBLA local ASR** (current faster-whisper artifact path and/or benchmarked Qwen ASR + aligner).

A benchmark gate decides the preferred default using the same consented reel fixtures. Measure:

- word/segment accuracy;
- punctuation/text usability;
- word-level/timing accuracy;
- handling of Italian names/English technical words;
- runtime;
- ability to run with Resolve closed;
- API/export reliability.

If Resolve transcription is materially better and programmatically retrievable, it can be the default when Resolve is open, while local ASR remains an offline/fallback provider. If local ASR is better or more reliable, the panel simply calls the local backend.

## 12. Resolve panel architecture

The official UX target is a Resolve Workflow Integration / panel, but the backend remains independently runnable.

Panel responsibilities:

- choose current timeline/source;
- Analyze;
- show progress by stage;
- show each 3–4 s coverage slot on the reel timeline;
- preview proposal A and B;
- switch A/B;
- disable coverage;
- regenerate only one slot;
- optionally adjust slot boundaries;
- approve/freeze Edit Plan;
- Apply;
- surface Apply verification/errors and Undo/rollback metadata.

The panel talks to the RAMBLA Engine over localhost. It does not load Qwen, scrape/download assets, or contain editorial logic.

## 13. Resolve Apply strategy

`ResolveApplyPort` consumes only an approved/frozen Edit Plan.

Adapters:

- `MCPResolveApplyAdapter` — preferred experimental route once the user's MCP setup is stable;
- `NativeResolveApplyAdapter` — direct official scripting/API route where capabilities are reliable;
- fake adapter for CI/tests.

The same plan must be executable by either real adapter without changing sourcing/director logic.

Apply rules:

- never mutate `REEL_MASTER` directly;
- duplicate/create target timeline first;
- import only selected/acquired assets;
- place short clips/stills at exact coverage-slot intervals;
- apply crop/scale/position metadata;
- captions/punch-ins/other approved interventions remain separate operations;
- every operation records an idempotency key and postcondition;
- analysis and search never call Apply.

## 14. Performance design

Performance priority is to avoid unnecessary bytes and heavy-model work.

For each slot:

- remote searches run concurrently;
- use metadata/thumbnails/storyboards before media download;
- batch Qwen preview ranking;
- local cache embeddings and acquisition artifacts;
- acquire only proposal A/B short windows when useful for review, or only A until B is requested when bandwidth is constrained;
- download full stock video only when the provider cannot expose a practical partial asset and the candidate is selected;
- keep model lifecycle lazy and benchmark whether hot residency is worth VRAM cost.

A one-minute reel may contain multiple 3–4 s coverage slots, but cost should scale with the number of slots/candidates rather than full source-video durations.

## 15. Review/Edit Plan schema changes

Each `CoverageSlot` persists:

- slot ID;
- beat ID;
- timeline start/end and target duration;
- transcript/context;
- visual intent and evidence class;
- generated queries;
- proposals A/B/(C);
- for each proposal: source page, source type, source time range if any, preview/still paths, acquired local window path if any, Qwen score, crop score, final score, rights/provenance, creator/attribution, cache state;
- selected proposal;
- review state;
- crop/reframe parameters;
- Apply state/result only after execution.

This replaces the assumption that a single beat owns one selected B-roll.

## 16. Failure behavior

- no usable candidate -> leave talking head, mark `NO_VISUAL_FOUND`;
- only one candidate -> allow it but mark `SINGLE_PROPOSAL`;
- weak ranking -> preserve alternatives and mark `REVIEW_REQUIRED_LOW_CONFIDENCE`;
- social fetch failure -> keep discovery evidence and continue other providers;
- crop unsafe -> demote or reject candidate depending on severity;
- partial-download imprecision -> acquire a wider bounded interval and trim locally;
- Resolve/MCP unavailable -> analysis/review remains fully usable; Apply is disabled only.

## 17. First implementation sequence after written-spec approval

1. Replace portrait-only search assumptions with aspect-agnostic candidates + crop-safety metadata.
2. Add `CoverageSlot` model with default 2.5–4.5 s range and A/B proposal contract.
3. Update existing Pexels path to populate A/B proposals and short-slot Edit Plan/review UI.
4. Add `SceneLocator` and acquisition interfaces with fake/test adapters.
5. Implement YouTube discovery + bounded time-window acquisition as the first long-video source.
6. Add still/frame-grab fallback.
7. Add social/web adapters incrementally behind the same interfaces.
8. Benchmark Resolve transcription vs local ASR on the real reel fixtures.
9. Build the Resolve panel as the official thin frontend.
10. Implement MCP Apply adapter only after the user's MCP/Resolve state is stable; keep native adapter available.

No Resolve mutation is re-enabled merely by implementing steps 1–9.

## 18. Acceptance criteria

The V2 architecture is demonstrated when RAMBLA can process a real one-minute talking-head reel and:

- plan short evidence coverage slots rather than covering whole beats;
- source mixed-aspect media;
- present at least A/B alternatives for normal successful slots;
- locate a useful 3–4 s section inside at least one longer online video without requiring the entire source to be downloaded;
- use a still/screengrab fallback for at least one eligible source type;
- show Qwen relevance, crop safety, provenance, source timestamp/range, and alternatives in review;
- generate a frozen Edit Plan independent of Resolve;
- display/review that plan from the Resolve panel;
- Apply the approved plan through a replaceable Resolve adapter only when explicitly requested.
