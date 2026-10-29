# Conservative Nemotron voice evidence

User request: proceed with the next step after the local Nemotron benchmark, autonomously; preserve the installed editor until the complete editorial test is convincing.

Use Nemotron-3-Diarization Q8_0 as an optional local second opinion after WeSpeaker source profiles have been reconciled. Keep existing identified voices. Fill only unknown units when a recording-local cluster has at least two independent, unambiguous acoustic anchors and strong temporal dominance. Exclude the query and overlapping anchors. Never treat a Nemotron cluster ID as a cross-recording identity or a visible face. Nemotron-only predictions cannot enrol new face identities.

Alternatives: replacing WeSpeaker loses reliable coverage on the frozen corpus; cloud video reasoning adds costs and uploads. The measured local hybrid is the selected continuation. It remains an experimental observed-performance capability; no stable release or change to other products.

Native adapter: pinned official 100M model, local CLI in a child process, 16 kHz mono PCM reuse, source-frame intervals, strict finite/range validation, fingerprints and versioned cache, explicit GPU/CPU fallback and sanitized errors/progress. Use the bounded v3-offline preset: full-attention rejects long recordings. No runtime downloading or global installation during analysis.

Validation: test first for interval conversion, duplicate/overlap anchors, ambiguity, disagreement, corrupt cache, timeout and missing runtime; run real frozen recordings and voice-to-face excerpt replay. Report semantic/visual/editorial defects independently from interval integrity. The agent supplies rules, never file-specific cut decisions.
