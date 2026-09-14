# Legacy RMBL-CercaCoperture — acceleration notes

Source reviewed locally from the user-supplied legacy HTML. The source file itself MUST NOT be committed because it contains plaintext API credentials.

## Verdict

Do not port the old app wholesale. Reuse three ideas only, adapted to the current evidence-first architecture.

### 1. Batch query planning after timed semantic chunking

The old app makes one LLM request for the entire script and asks for all short scenes plus multiple search queries in a single response. RAMBLA should not reuse the old segmentation because current timed-ASR semantic phrase boundaries are more reliable and preserve source timing. However, after semantic chunks/EvidenceIntent already exist, query generation can be batched across many slots in one planner call instead of one model call per slot.

Recommended shape: `plan_query_bundle(slots, intents, source_strategies) -> per-slot query families`.

Keep a deterministic literal/exact query and an optional creative/editorial query family per slot. Provider/source-class adapters can then transform those families as needed.

Potential win: fewer model round-trips and lower repeated prompt/context cost while keeping timing/semantic segmentation deterministic.

### 2. Dual literal + creative search lanes

The old tool exposes both an AI-generated creative search and a literal keyword search. Preserve this concept, but reinterpret it using EvidenceIntent:

- exact/literal lane: entity, product, event, quote, document, UI labels;
- creative/editorial lane: visual metaphor, context, cultural reference, source-native social;
- generic stock lane only as the final fallback.

Do not let creative similarity outrank exact evidence when specificity is required.

### 3. Cheap preview fan-out before acquisition

The old app fetches Pexels metadata/thumbnails first and lets the editor inspect several candidates without downloading media. Generalize this into a provider-agnostic `discover -> lightweight preview/metadata -> score -> bounded acquire only finalists` path.

This is already conceptually aligned with RAMBLA's YouTube storyboard coarse pass; extend the same principle to stock/web/social adapters where possible.

## What NOT to reuse

- Client-side API secrets or embedded keys.
- Gemini-based scene segmentation: it discards exact source timing and can conflict with timed ASR phrase boundaries.
- Provider-specific query fields baked into the Director core.
- Raw literal tokenizer from the HTML: its ASCII-only regex damages Italian accented words and makes its stop-word list inconsistent.
- Sequential per-scene provider fetch loop; use bounded concurrency across slots/providers.
- Pexels-first/default stock behavior; current hierarchy remains exact evidence -> source-native/editorial -> stock fallback.
- No ranking/quality floor: old thumbnails are discovery only, never final selection.

## Suggested implementation impact

Task 2 / source strategy: add two inspectable query families (`exact_literal`, `creative_editorial`) plus provider/source-class transforms.

Task 4 / sourcing escalation: fan out lightweight discovery concurrently with a semaphore; score metadata/previews first; acquire only finalists. Cache discovery results by normalized query + provider + source-class + policy version.

Task 7 / benchmark: measure query-planning round-trips, discovery latency, preview bytes, acquisitions avoided, and editor keep-rate.

## Security note

The supplied legacy HTML includes live-looking Gemini and Pexels keys in plaintext. Treat them as compromised: revoke/rotate them and never copy them into RAMBLA, Git, logs, issues, or test fixtures.
