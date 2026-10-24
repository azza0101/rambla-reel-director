# Complete lines and reactions implementation plan

Goal: integrate complete-line preference and verified silent reaction inserts in the local plugin.
Architecture: boundary evidence in transcript_align; editorial insertion after pacing in edit_selector; persisted validated reaction_before objects and user disable controls in session/renderer; expansion in resolve_adapter.
Spec: ../specs/2026-10-24-complete-lines-reactions-design.md

- [x] TDD semantic boundary evidence on complete earlier vs truncated later takes; real golden sample must retain the final discourse opening without borrowing another speaker.
- [x] TDD reaction search requires verified close, speaker, word-free RMS pause, take boundaries and minimum duration; no repeated insert on recalculation.
- [x] Validate saved reaction objects, support disable in panel, show still/motive, progress; preserve old project compatibility.
- [x] Native adapter inserts reaction AV on existing tracks; validates ranges and preserves original timeline and source mappings.
- [x] Full suites plus real-source pipeline and new versioned timeline; inspect readback and distinguish manual visual labels from automatic edit decisions.
- [ ] Review, build and verify package, publish dedicated prerelease from PR19 without merge/latest, keep credentials and footage excluded.

Review focus: wrong-speaker semantic false positives; partial re-takes inside one file; silence detections overlapping ASR; manual bounds invalidating reaction context; malicious saved ranges; disabled features or missing audio; repeated replan creating duplicate reactions.

Evidence: real scene12matches, recovered opening, automatic1.20s reaction; native timeline14AVsegments1788frames original preserved; UI exactstill/exclusion/reenable/replan/save/progress pass. 73Node+66Python+9package contracts pass. Review issues about exclusion persistence and replayed retained footage reproduced and fixed with regression tests.
