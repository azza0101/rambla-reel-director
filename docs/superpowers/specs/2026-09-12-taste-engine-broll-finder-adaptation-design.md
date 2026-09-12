# RAMBLA Taste Engine + B-Roll-Finder Adaptation — Design

Status: **APPROVED IN CHAT on 2026-09-12; written-spec review pending**

Date: 2026-09-12

## 1. Goal

Add a persistent **Taste Engine** to RAMBLA so sourcing and editorial decisions are guided by what a client actually publishes and accepts, not only by semantic similarity or generic rules.

This design explicitly adapts ideas and, where useful, MIT-licensed implementation patterns from `louisedesadeleer/b-roll-finder`. The upstream repository is MIT licensed. If RAMBLA copies or substantially adapts upstream code, the required copyright/license notice must be preserved in an attribution file or source header.

The Taste Engine does **not** replace RAMBLA Director, Qwen retrieval/reranking, online sourcing, CoverageSlot, SceneLocator, partial acquisition, or Resolve Apply. It sits across them as a policy/profile layer.

## 2. Core principle: revealed taste outranks stated taste

RAMBLA should model two types of preference separately:

1. **Revealed taste** — measured from videos the client actually published or explicitly marks as exemplars.
2. **Declared taste / guardrails** — preferences and bans the user explicitly states.

Declared guardrails always win when they conflict with historical behavior. Example: if past videos contain memes but the user says “no memes”, the route is disabled immediately.

Taste is client-scoped. No profile data may leak across clients.

## 3. TasteProfile data model

Introduce a versioned `TasteProfile` persisted per client. It should include at minimum:

- `client_id` and profile version;
- confirmed/approved state;
- fingerprint source list and analysis timestamps;
- pacing metrics: cuts/minute, median visual hold, short-insert frequency, coverage density, hook-vs-body density;
- route mix: Receipts, Entity, Product/UI, Historical/Archival, Concept, Social/Cultural, Stock fallback;
- preferred evidence classes by topic/genre;
- still-image behavior: static / subtle zoom / blur-fill preference;
- B-roll audio policy;
- source-attribution preference;
- crop/reframe tolerance;
- default proposal count;
- trusted-source registry tagged by topic;
- blocked sources/categories/topics;
- explicit user guardrails;
- style notes / brand voice metadata;
- optional reference/exemplar IDs;
- profile provenance: `measured`, `declared`, `imported`, `approved`.

Profile updates are deterministic and inspectable. RAMBLA must retain the previous version when a new one is approved.

## 4. Fingerprint extraction from finished reels

Introduce a `TasteFingerprintAnalyzer` that can analyze finished reference videos selected by the user.

The first implementation should combine:

1. FFmpeg scene-cut detection to identify shot/cut boundaries;
2. representative frame extraction around cuts and holds;
3. Qwen visual/text classification of each cutaway into route/type classes;
4. optional transcript/context alignment when the source transcript is available;
5. aggregate metrics across the reel and across multiple exemplars.

Measured outputs include:

- total duration;
- shot count and cuts/minute;
- median/mean shot duration;
- distribution of sub-second, 1–2 s, 2–4 s, and long holds;
- estimated B-roll coverage percentage;
- route/type distribution;
- where visual density occurs (hook, early body, middle, ending);
- recurrence of receipts, screenshots, faces, products, archive, stock, cards, etc.;
- common crop/layout behavior when measurable.

The analyzer must store evidence for its conclusions: cut timestamps, representative-frame paths, classifications and confidence. The user can inspect or reject misclassified exemplars before profile approval.

## 5. Exemplars and client onboarding

RAMBLA should support two ways to seed taste:

- **Published-client reels** — strongest signal. The user selects several good finished edits and RAMBLA derives the fingerprint.
- **External exemplars** — used when the client has no reliable history or wants a new direction. The user can provide references such as Olimpia Peroni / Factanza-style reels or other chosen examples.

The first product version should not require a long questionnaire. It should infer measurable behavior first, then ask only for high-impact guardrails that cannot be safely inferred, such as:

- keep or strip sourced audio;
- allow/ban memes/reaction clips;
- allow/ban AI-generated visuals;
- source attribution on/off/style;
- categories or topics off-limits.

## 6. Persistent user overrides

Explicit user overrides are first-class profile events.

Examples:

- “no memes”;
- “more receipts, less stock”;
- “never show newspaper screenshots”;
- “keep B-roll around 3 seconds”;
- “always give me two choices”.

The active session must honor the override immediately.

RAMBLA may record the override as a proposed profile update, but **must not silently retrain or permanently alter the approved TasteProfile**. The UI presents the proposed change and the user approves it before it becomes the next profile version. This preserves the existing project rule against opaque automatic learning.

## 7. Semantic routing before search

Adopt the strongest B-Roll-Finder idea: **classify what kind of visual evidence a line needs before searching**.

For each CoverageSlot, add a `VisualRoute` decision. Initial routes:

- `RECEIPT` — posts, articles, comments, documents, search results, prices, statistics, claims;
- `ENTITY` — named person, event, place, physical thing, historical moment;
- `PRODUCT_UI` — app/product/interface/demo;
- `ARCHIVAL` — historical/repertory material;
- `CONCEPT` — abstract process, comparison, model, chart, explanatory visual;
- `CULTURAL` — reaction, meme, creator clip, stylistic cultural reference;
- `STOCK` — semantic stock fallback when specific evidence is unavailable or intentionally generic.

Routing is based on the whole local transcript context, not bare keywords.

Examples:

- direct quote -> authentic post/article/speaker moment before generic face footage;
- number/stat -> the actual chart, dashboard, pricing page, paper, or stat receipt before stock;
- named person -> that person doing/saying the relevant thing, not a generic portrait;
- “went viral” -> original viral artifact/metrics before generic phone footage;
- abstract mechanism -> explanatory graphic/authoritative demo before unrelated stock.

## 8. Taste-aware sourcing policy

The sourcing engine should receive a `TasteContext` derived from the active profile and CoverageSlot.

Taste affects:

- which routes are allowed;
- provider/source priority;
- target duration and density;
- number of proposals;
- trusted sources for the topic;
- penalty for repeated/overused source styles;
- preferred still/video behavior;
- whether a candidate should be auto-selected or require user review.

Taste must **not** make a semantically wrong clip win. Ranking order is:

1. factual/evidence correctness and relevance;
2. rights/provenance acceptability;
3. crop/technical usability;
4. taste compatibility;
5. diversity/novelty.

## 9. Trusted Source Registry

Introduce a client-scoped `TrustedSourceRegistry`.

Each entry stores:

- source/channel/account ID and canonical URL;
- provider/platform;
- topic tags;
- trust/authority level;
- optional notes;
- enabled/disabled state;
- provenance of how it entered the registry.

RAMBLA may optionally support B-Roll-Finder’s **import-then-prune** workflow for YouTube subscriptions or other user-authorized source lists. Imported entries are not automatically “trusted”: they start as candidates and are categorized/pruned before activation.

The registry is a search preference, not a hard prison. Exact script-referenced sources and authoritative sources may outrank it. Open-web/YouTube search remains available when configured, but should be visibly flagged when it leaves trusted territory.

## 10. Source-by-source batching

Adopt the B-Roll-Finder optimization of grouping sourcing by **source**, not performing every fetch independently per beat.

After the Edit Plan has candidate intents:

1. cluster slots that reference the same article/page/video/channel/source;
2. fetch metadata/page/video source once;
3. derive multiple screenshots, frames, or time windows from the same source;
4. cache the raw source metadata/artifact once;
5. store per-slot derived assets separately.

This should reduce network requests, duplicate downloads and social/API fragility.

For long videos, SceneLocator can identify several useful 3–4 s windows from one source while Acquisition downloads only the required windows.

## 11. Candidate policy: objective vs taste-heavy routes

RAMBLA should not copy B-Roll-Finder’s strict “agent never picks final B-roll” rule unchanged.

Use a hybrid policy:

- objective route + high confidence + strong evidence -> RAMBLA may preselect proposal A automatically;
- low confidence, ambiguous cultural/taste-heavy route, or conflicting signals -> explicit review required;
- every normal successful slot still retains proposal A/B as already defined in V2;
- “no visual” remains better than a wrong visual.

The review UI must show *why* a candidate was selected: route, evidence relevance, Qwen score, crop score, taste score, source trust and provenance.

## 12. Taste scoring

Add `taste_score` as a bounded component of candidate ranking.

Possible factors:

- route matches client route distribution;
- candidate duration close to profile pacing;
- source appears in trusted registry;
- candidate type fits genre/topic preferences;
- profile prefers/avoids screenshot, stock, talking-head, archival, etc.;
- recent selected slots have not overused the same source/type;
- still/video motion behavior matches profile.

The final score must retain component values rather than collapsing into an opaque single number.

## 13. Verification feedback loop

After RAMBLA builds a review plan or edit, add a lightweight visual verification pass similar to B-Roll-Finder’s “render -> inspect -> targeted fixes” philosophy.

For each selected slot, verify at minimum:

- a midpoint representative frame;
- entry and exit junction frames when useful;
- crop safety / subject survival;
- no accidental black/empty/failed capture;
- expected source/type actually appears;
- expected duration/range is plausible.

Verification failures target only the affected slot. Avoid global reruns.

## 14. Still/screenshot handling

B-Roll-Finder contains MIT-licensed patterns for:

- browser/CDP screenshot capture with consent handling;
- cutaway rendering;
- sub-pixel still zoom with optional blur-fill.

RAMBLA should evaluate and selectively adapt these patterns instead of automatically rewriting them.

Important platform adaptation: upstream `cdp_capture.py` hardcodes the macOS Chrome path, so RAMBLA must wrap/port the behavior behind a platform-neutral `PageCaptureAdapter` rather than copy that assumption.

The subtle still-zoom technique is useful because it avoids visibly stepped integer zoom behavior. It should become a configurable TasteProfile option rather than a universal default.

## 15. Interaction with current V2 architecture

This design extends, rather than replaces, `2026-09-12-resolve-panel-evidence-sourcing-v2-design.md`.

Existing components stay responsible for:

- `CoveragePlanner` -> where/when visual coverage is useful;
- `VisualRoutePlanner` / Taste Engine -> what kind of evidence belongs there;
- provider adapters -> discovery;
- `SceneLocator` -> best source range inside long media;
- Qwen embedding/reranking -> semantic/visual relevance;
- `CropSafetyEvaluator` -> 9:16 usability;
- `CandidateSelector` -> A/B/C proposal set;
- `AcquisitionAdapter` -> bounded local acquisition;
- Resolve panel -> review/override/profile controls;
- Resolve Apply -> deterministic execution only after approval.

TasteProfile is loaded before planning/sourcing and passed by value/snapshot into each run so the Edit Plan is reproducible.

## 16. Edit Plan additions

Every run stores a `taste_snapshot` reference/hash.

Each CoverageSlot additionally records:

- `visual_route`;
- `route_reason`;
- `taste_profile_version`;
- applicable guardrails;
- trusted-source scope used;
- per-candidate `taste_score` and score components;
- source-classification confidence;
- whether selection was auto-eligible or review-required;
- any user override applied during the run.

The frozen approved plan must remain reproducible even if the client’s TasteProfile later changes.

## 17. Learning and corrections

RAMBLA should record user decisions as structured events:

- selected A vs B;
- rejected candidate;
- disabled slot;
- changed route;
- changed duration;
- source preference/ban;
- explicit style instruction.

These events are useful evidence for a future profile revision but do **not** mutate the profile automatically.

A later “Update Taste Profile” action can summarize repeated corrections and propose a new version for approval.

## 18. Source/license/provenance handling

Taste preference never overrides source rights/provenance policy.

Every online candidate keeps provider/source URL, creator/source account, timestamp/range, discovery route and rights/provenance state.

B-Roll-Finder code reuse is permitted under MIT. Any copied/substantially adapted implementation must keep the upstream copyright/license notice as required by MIT.

## 19. Implementation sequence after written-spec approval

1. Add `TasteProfile`, versioning, snapshot/hash and guardrail schema.
2. Add `VisualRoute` model and deterministic route-planner fallback.
3. Thread `TasteContext` through CoverageSlot -> sourcing -> CandidateSelector without changing current provider contracts unnecessarily.
4. Add route/taste fields to Edit Plan and review HTML/panel.
5. Implement `TasteFingerprintAnalyzer` on local finished reels using FFmpeg scene cuts + representative frames + Qwen classification.
6. Add profile review/approve flow; never auto-commit profile changes.
7. Add `TrustedSourceRegistry` and optional import-then-prune ingestion.
8. Add source-by-source batching/cache reuse.
9. Add targeted visual verification pass.
10. Evaluate/adapt B-Roll-Finder MIT utilities for page capture and still motion where they outperform current/future RAMBLA code.
11. Run a benchmark using reference reels and measure whether taste-aware routing improves candidate acceptance versus semantic-only ranking.

Resolve mutation remains frozen during steps 1–11 unless separately re-enabled by the user.

## 20. Acceptance criteria

Taste Engine V1 is demonstrated when RAMBLA can:

- analyze at least 3 finished reference reels and produce an inspectable fingerprint;
- derive pacing and route-mix metrics from those reels;
- persist an approved client-scoped TasteProfile version;
- honor a new explicit guardrail immediately and propose, rather than silently commit, a profile update;
- classify real CoverageSlots into evidence routes before search;
- use trusted-source/topic preferences during sourcing;
- expose semantic score, crop score, taste score and source trust separately;
- retain at least A/B proposals for normal successful slots;
- show that taste-aware routing improves or at minimum does not reduce factual relevance compared with semantic-only ranking;
- batch repeated use of the same source instead of refetching it per beat;
- retain provenance and profile snapshot in the frozen Edit Plan;
- complete analysis and review with zero Resolve mutation.

## 21. Explicit non-goals for V1

- no autonomous permanent learning from every click;
- no fine-tuning a model on the client’s videos;
- no global cross-client taste model;
- no requirement to import browser subscriptions;
- no mandatory meme/cultural sourcing;
- no replacement of Qwen ranking with hand-written taste heuristics;
- no coupling of Taste Engine to MCP or Resolve runtime.
