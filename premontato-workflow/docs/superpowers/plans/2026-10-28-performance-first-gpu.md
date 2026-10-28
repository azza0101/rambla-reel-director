# Performance-first sequence planning and optional GPU reader

Implementation approved in the conversation, 28 October 2026. Product channel: Omni-Cut test only. No merge to main and no changes to existing timelines.

1. Reproduce user feedback against the saved source ranges and native timeline. Separate content selection, role/face consistency and camera continuity errors.
2. Test and integrate optional persistent NVDEC reader. Calibrate Sony preroll, verify retained-frame timestamps, batch sparse samples, preserve speaker sampling at 25 fps, and fall back to the original decoder. Include pinned dependency and vendor notices/source asset.
3. Choose scene performances per camera field before individual edit windows. Last substantially complete performance wins; recover earlier whole beats only when later coverage is absent or materially partial. Keep diagnostics of selected ranges.
4. Require equivalent content for alternate camera windows, reject reuse of overlapping spoken source, deduplicate repeated moments and reject adjacent cuts between equivalent fields.
5. Learn conservative face/role references only from distinctive screenplay-grounded speech anchors. Uncertain faces remain uncertain; no person names are inferred from appearance.
6. Include catalogued silent action scenes in automatic scope and planning even if a spoken line is missing. Preserve real source extent and flag missing speech/action timing instead of inventing times.
7. Run Python and JavaScript suites, real scene planning, then native Resolve application on a newly named versioned timeline. Verify source ranges and preserve all existing objects. Publish a test package only after successful native verification; report remaining quality limits explicitly.

A rendered low-resolution preview alone is not a narrative quality check. This increment validates the internal scene plan and real source evidence; it does not claim human-level judgment or automatic verification of completed gestures.
