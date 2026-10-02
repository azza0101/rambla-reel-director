# Transcript Intent Workflow Design

## Goal

Turn the transcript into the authoritative editing workspace. A user can correct the full text, tag any semantic phrase as **Coverage**, **Animation**, and/or **Highlight**, generate B-roll only for Coverage phrases, and export timestamped Animation, Resolve Text+ and compact SRT artifacts.

## Product flow

1. Analysis creates a timestamped transcript and semantic phrases.
2. The full transcript appears in one editable, newline-delimited box. Each line is a semantic phrase.
3. Saving corrections preserves the source interval, redistributes word timings inside it, rebuilds semantic phrase artifacts, remaps intent tags by time overlap, and marks the current editorial plan stale. Existing plans and media remain on disk until replaced.
4. Three independent tags can be combined without validation errors:
   - **Coverage**: the only phrases eligible for Director B-roll and provider search.
   - **Animation**: phrases included in the animation handoff JSON.
   - **Highlight**: short text spans, normally at most three words, exported as one Resolve Text+ item per selected phrase.
5. The Director still receives the full transcript for global context. Unselected phrases are deterministically constrained to `KEEP_TALKING_HEAD`; they cannot create shots or searches.
6. The left phrase rail remains the navigation surface and exposes the three tags after analysis and after a plan is generated.

## Persistent contract

`run/phrase-intents.json` uses schema `rambla-phrase-intents-1`:

```json
{
  "schema_version": "rambla-phrase-intents-1",
  "transcript_signature": "...",
  "phrases": {
    "chunk_001": {"coverage": true, "animation": false, "highlight": false}
  }
}
```

All three flags are booleans and may be true together. Projects without this file keep their existing plan and retrieval behavior. The first explicit tag change creates the file; old B-roll beats seed Coverage when their chunk mapping is available.

## Transcript correction and timing

The editor shows one semantic phrase per line. Text changes within an existing line keep that phrase's original start/end interval. Words are tokenized and distributed evenly inside that interval. If lines are added or removed, their intervals are distributed proportionally across the original transcript duration. A revision digest prevents overwriting a newer transcript.

Saving rebuilds `transcript-raw.json`, `semantic-chunks.json`, and `semantic-beats.json` atomically. Intent tags are remapped by strongest time overlap, then text similarity. The old visual plan and retrieval artifacts are preserved but marked stale until a new plan is generated or imported.

## Director behavior

The editorial input adds `coverage_selected_chunk_ids`. The full chronological transcript remains present for theme and reference resolution. The prompt states that only selected IDs may use B-roll. Compilation rejects provider output that assigns B-roll or continuation to an unselected chunk, so the restriction does not rely on prompt compliance alone.

The generated plan still covers every chunk exactly once. Unselected chunks become `KEEP_TALKING_HEAD` with no shots. Provider sourcing continues to consume B-roll beats from the validated plan, so no provider routing change is required.

## Exports

- **Animation JSON**: `rambla-animation-selection-2`, selected phrases in timeline order, real seconds, duration, concatenation flag and separators.
- **Resolve Text+ JSON**: `rambla-resolve-textplus-1`, one `TEXT_PLUS` item per Highlight phrase with joined text, start/end seconds, frame range and track hint. It is the stable contract for the future Resolve bridge; no effect preset is applied.
- **SRT**: semantic phrases split into cues of no more than three words. Punctuation may close a two-word cue. Timings use the first and last word timestamps.

## UI

The transcript review panel appears after analysis and contains the full editor, save status, three colored selection modes, counts and export actions. Phrase cards use compact tag controls while preserving normal phrase navigation. Coverage is violet, Animation cyan and Highlight amber. Overlap displays multiple active chips instead of an error.

Controls are disabled only while a conflicting project stage is running. Successful save/export actions receive the same green completion treatment as the existing workflow steps. Existing sourcing, social, image and curation controls remain in place.

## Compatibility and failure behavior

- Existing projects without intents continue to load.
- An empty Coverage selection blocks Director generation with a clear instruction; it never silently analyzes every phrase.
- Invalid or stale revision saves return a conflict without modifying artifacts.
- Exports with no selected phrases return a clear validation error.
- All writes are atomic and restore prior bytes if a multi-file save fails.
- No new package, model, GPU, PATH, CUDA, ComfyUI or system configuration change is required.
