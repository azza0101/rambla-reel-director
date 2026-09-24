# Animation phrase export — 2026-09-23

Local implementation: animation_export_ui.py, injected into curation_ui_v2.py.
- Explicit animation-selection mode above the left phrase rail; turquoise multi-selection independent from active beat/media choices.
- COPY JSON and EXPORT JSON use identical pretty-printed rambla-animation-phrases-1 payloads.
- Timeline order; source start/end; duration calculated from end minus start (including pauses inside each beat), never estimated from text.
- Adjacent selected timeline entries share a concatenation group. Separators are valid JSON objects; pauses/overlaps have explicit signed gap_seconds. Skipping an intervening beat starts a separate group.
- Invalid selected timing blocks export with an error. Project selections are isolated and retained during the page session; reload resets them.
- Transcript/plan/ASR/media selections unchanged. No inference, provider requests, new dependencies or GPU work.
Validation: 595 tests passed, Python compile and generated JavaScript syntax passed. Node tests cover ordering, timing, adjacency, selection toggles, redraw, clearing, project isolation. Actual browser download/clipboard and visual rendering not exercised this turn.
Delivery: local files updated, no remote publication; restart RAMBLA to load changes.
