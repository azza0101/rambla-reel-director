# Contextual CUT selection and local reconciliation

Problem: grammar-only rejection kept all takes, fragment review left orphan tails, and residual review skipped grouped words. Provider token exhaustion was hidden behind generic JSON errors.

Production stays on Groq. Gemini was diagnostic only, timed out, and is not a runtime dependency. The reference was manually read for local regression comparison; no transcript or source-specific selection is published or hardcoded.

Classify every ASR block as keep/discard/trim, validate complete disjoint decisions, resolve trims against source words, then reconcile whole nearby retakes. A global exclusion set prevents nested-prefix reintroduction. Preserve unique premises, named-place differences and closing words. Save full editorial debug locally, GitHub diagnostics sanitized. Reuse measured ASR and version proposal caches separately.

Real pipeline exactly matched the reference at retained-word level: 414 words, 147.63 seconds, 11 segments, 8 alternate groups. Preview rendered. Original backed up before replacement and existing manual exclusion preserved. No Resolve mutations.

This is evidence for the reported video, not a guarantee of perfect editing on every recording. Manual review and alternatives remain available.
