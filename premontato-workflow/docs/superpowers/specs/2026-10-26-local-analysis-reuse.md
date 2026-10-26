# Premontato: reuse local analysis resources

## Scope and authorization

The user authorized a parallel, integrable optimization commit after the performance audit. Initial snapshot: `80ee38de59342e78eac7d3f92d95178ee362522e` (v0.11.6). During implementation the product branch advanced; integration base is now `219b91dd07344370806ebac29dbb106216b275ee` (v0.11.7), preserving its camera-availability changes and regression cases. Work is isolated on `perf/premontato-local-reuse-20261026`; the integration target is `feat/premontato-workflow`. Only `premontato-workflow/` changes. Coordination is recorded on PR #19.

## Required behavior

1. Local alignment and Groq-classified staged editing share one lazily initialized semantic encoder per worker process. Initial model integrity validation remains mandatory. Initialization failures remain retryable; worker restart resets the instance. Embeddings, cache limits and editorial decisions retain their existing rules.
2. Valid existing PCM cache files are opened as read-only memory maps. Active-speaker analysis can slice the original 16 kHz samples without allocating an entire clip on each hit. Invalid mapped files are closed before atomic replacement, including on Windows. Source fingerprints, sample values, extraction and cache format remain unchanged.
3. Initial analysis requests RMS silence measurements only when pacing is enabled and the local planner needs them. The current Groq staged engine does not consume this measurement. Progress explicitly marks the omitted audio phase as skipped. Audio required by active-speaker verification remains available through its existing lazy PCM loading.

When a saved Groq project is reopened with Groq disabled, or local pacing is enabled after an analysis, fill missing RMS data before pacing the actual local plan. Use each original full media source once, including alternative cameras needed by reactions. Keep measurements and unavailable results for subsequent replans; a Groq plan or an empty plan must not trigger this work.

No ASR/provider/model replacement, new network calls, timeline-rule changes, proxy pipeline, release or installer change is included. Original transcript words and timing remain authoritative. The v0.11.6 scene-selection and v0.11.7 camera-availability behaviors must remain intact.

## Acceptance and limits

Regression tests must demonstrate encoder reuse across both planning paths and retry after failure; actual PCM cache hits with identical slices, feature extraction and invalid-cache recovery; Groq/local/pacing-disabled orchestration with preserved source data. Run the existing product JavaScript and Python suites. No speedup percentage or native Resolve acceptance is claimed without a timed run on the user's media and Windows runtime.
