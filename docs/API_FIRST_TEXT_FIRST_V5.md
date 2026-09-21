# APP REEL V5 — API-first, text-first architecture

Status: first vertical slice implemented on `feat/api-first-text-first-v1`.

## Product rule

The source reel is **not** sent to the editorial model.

The editorial Director receives only the complete spoken transcript as one chronological
chunk ledger containing:

- chunk id;
- start/end time;
- spoken text.

It does **not** receive source-video pixels, source-video path, thumbnails, or word-level
timestamps. The model reads the whole transcript before deciding any visual beat.

Vision is reserved for a later, separate **candidate judge** that sees only retrieved
B-roll thumbnails / sampled candidate frames.

## Why this is the minimum that preserves intelligence

The Director needs global semantic context, not source-video pixels. To avoid quality loss:

1. the whole reel transcript is sent in one request, never one isolated phrase at a time;
2. the model sees neighboring and distant context before grouping beats;
3. the editorial prompt preserves the existing rules about truth, negation, irony,
   literal/retrievable visuals, repetition and dense short-form coverage;
4. mechanical fields are not delegated to the model;
5. canonical validation remains deterministic and unchanged.

The model returns only:

- global topic;
- first/last chunk id for each beat;
- BROLL / KEEP_TALKING_HEAD / CONTINUE_PREVIOUS_VISUAL;
- editorial function, core meaning and subtext;
- visual mode;
- shot descriptions;
- image/video queries;
- avoid list.

Python reconstructs:

- beat ids;
- shot ids;
- exact start/end;
- exact original transcript text;
- covered chunk ids;
- continuation links;
- project id;
- transcript signature;
- canonical schema version.

The result then passes the existing `rambla-visual-plan-1` validator before it is
allowed to replace `visual-plan.json`.

## Call budget

Normal path:

1. **one** Director request for the entire reel;
2. zero repair requests when the structured result validates.

Failure path:

- maximum one stateful repair request, reusing the previous Gemini interaction context.
  The transcript is not resent in the repair prompt.

This keeps cost/latency bounded without using a weaker editorial model.

## Provider

First provider: Gemini Interactions API.

Default Director model:

`gemini-3.8-flash`

Override without code changes:

`RAMBLA_DIRECTOR_MODEL=<model>`

Credential:

`GEMINI_API_KEY=...`

The credential is read from process environment or the existing local `.env.local`
allowlist and is never serialized into project artifacts.

The transport uses `httpx` directly; no Google SDK or new local model dependency is
required.

## Current vertical slice

Input:

- existing `transcript-raw.json`;
- existing `semantic-chunks.json`;
- existing `analysis-signature.json`.

Command:

```powershell
python -m backend.app.api_first_director_cli --run-dir "<PROJECT>\run"
```

Output:

- canonical `run/visual-plan.json`;
- canonical hashed editorial import root;
- `run/api-first/director-decisions.json`;
- `run/api-first/director-run.json`.

The audit explicitly records:

- provider/model;
- number of attempts;
- validation errors repaired;
- `source_video_sent_to_ai: false`;
- `word_timestamps_sent_to_director: false`.

Existing retrieval and Curation UI can consume the generated plan unchanged.

## Next gates — do not skip A/B quality proof

### Gate 1 — Director quality

Run the same KURA transcript through:

- current accepted/manual or local baseline;
- API-first Director.

Compare, without changing retrieval:

- beat grouping;
- B-roll coverage;
- literal correctness;
- context/reference resolution;
- query quality;
- visual repetition;
- hallucinated facts;
- human preference.

Only if API-first is equal/better does it become the default Director.

### Gate 2 — Cloud ASR

Candidate: Gemini 3.5 Transcribe.

Do **not** switch blindly. Its word-timestamp mode is useful for the timeline, but the
provider documentation warns that word-level timestamps can reduce transcription
accuracy. Benchmark it against the current faster-whisper transcript on KURA and at
least two materially different reels.

Measure:

- word errors / proper names;
- punctuation and clause boundaries;
- timing drift;
- resulting Director plan, not transcription alone.

If cloud ASR wins or is equivalent, remove faster-whisper from the standard path and
leave it as fallback.

### Gate 3 — Multimodal candidate judge

Do not send the source reel.

For each retrieval candidate, initially send only:

- thumbnail;
- candidate metadata;
- target shot description;
- target core meaning;
- avoid list.

Use one batched multimodal call across many candidates. Only ambiguous finalists may
receive 3 sampled frames. Download/cut full media only after shortlist selection.

The first judge implementation should replace local embedding/Qwen ranking without
changing provider discovery.

### Gate 4 — Query retry

Only weak beats get another AI call.

If the first search has no visually strong candidates, ask a cheap text model to produce
alternative concrete queries from the already-known shot intent. Do not rerun the global
Director.

## Deliberately absent from V5 standard path

- source-reel vision;
- local Qwen editorial generation;
- local text/image embeddings as a requirement;
- one LLM call per transcript phrase;
- one LLM call per candidate;
- AI-generated timestamps or transcript copying;
- automatic silent repair of semantic coverage.

## Privacy / deployment note

The API-first mode is opt-in while benchmarking. Free cloud tiers may have different
data-use terms than paid tiers, so provider/tier choice must remain visible and
configurable before this becomes the default for client material.
