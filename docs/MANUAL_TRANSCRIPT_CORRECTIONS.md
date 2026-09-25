# Manual phrase corrections — 2026-09-23

Local patch, no remote publication.
- MODIFICA TRASCRIZIONE above the active phrase opens an editor for its covered semantic chunks. Save validates non-empty bounded text and expected old text; busy projects reject edits.
- Canonical semantic-chunks text is updated, preserving IDs/start/end and source media. Original chunk snapshot/history is saved in transcript-corrections.json; raw ASR remains intact. Edited word alignments are removed; editorial export suppresses raw ASR word timestamps after corrections rather than falsely aligning new words.
- Imported plan original_text and transcript signature updated consistently. Validated editorial-location pointer retains the existing retrieval root and asset paths/selections without copying media.
- UI/read transcript, animation exports and future Director/export input consume corrected text. Existing semantic plans/queries are explicitly stale; all product sourcing routes reject new searches until the user generates/imports a reviewed plan. Animation context ignores the old global topic while stale.
- Individual atomic writes with synchronous-error rollback; no claims of crash-proof multi-file transactions. Concurrent edits use expected-text conflict detection. No ASR/model/provider run initiated on save.
- Validation: 606 tests passed, backend compilation and generated JS syntax passed before final context-only argument adjustment. Tests cover correction, timings, selection/root preservation, source ASR preservation, reimport, blank/conflicting input, busy API, corrected transcript endpoint, stale search block and write-failure rollback.
- No real user transcript changed during tests. Restart server for UI changes.
