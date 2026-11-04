# Evidence-first dialogue director implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline. The user explicitly requested autonomous research and experiments; no intermediate design confirmation or agent swarm is needed.

**Goal:** Establish which local changes improve real dialogue-camera selection, and implement a bounded whole-sequence selector without claiming that source-interval validity proves narrative correctness.

**Architecture:** Keep transcription, audio identity, audiovisual visibility, face identity, performed-story selection and camera sequencing as distinct evidence. Reuse the current worker, cached source data and renderer. Add an opt-in sequence planner after candidate verification; it must preserve all observed events and source chronology. Keep model experiments and private benchmarks on Z: outside the repository.

**Approaches:** (1) Replace the director with an agent/VLM: rejected as the initial step because of latency, inference cost and unconstrained timing. (2) Improve evidence and optimize the candidate sequence locally: selected for measurement. (3) Replace the ASD model: benchmark LR-ASD ONNX before accepting a change. These choices are implementation judgments under the user's autonomous-work authorization, not an approval claimed for measured quality.

## Tasks

- [x] Pin research sources and licenses. Separate executable local algorithms from agent skills requiring external reasoning. Study dialogue-editing sequence models, LR-ASD and low-cost transcript/visual QA.
- [x] Benchmark existing face-identity gating, a strict ASD-only spike and conservative combined evidence. Discard variants that merely increase cuts while producing errors.
- [x] Compare LR-ASD ONNX with Light-ASD on identical real source windows, with reconciled speaker labels. Report proxy-label agreement separately from human accuracy and warm/cold timing.
- [x] Test-first sequence selector: no event omission, no backwards/reused source intervals, bounded work, deterministic choices, preference for a coherent last good performance, and avoidance of exposed same-field take splices. Do not force a master or invent reaction shots.
- [x] Integrate the sequence selector as an opt-in observed-editor mode, retaining the existing default and independent audio/video compilation. Replay the frozen real scene and an additional excerpt; persist diagnostics. No new preview promoted: no visual improvement demonstrated over the existing independent-AV preview.
- [x] Run full Python/JavaScript suites and review the final diff. Commit/push only product code, synthetic tests and non-private evidence. Publish a draft PR; no stable release or native Resolve apply is implied.

## Ledger

- Base: d6ddddd, branch feat/omnicut-evidence-first-director-20261104, clean starting tree; upstream fetched.
- User wants local/fast autonomous research, no GUI control, no changes to other products. No cloud inference on private footage authorized by this task.
- Initial spike: strict ASD-only gating reduced useful choices and is rejected. A combined spike changed opening coverage incorrectly; a lower unresolved count is not sufficient acceptance evidence.
- LR-ASD candidate assets: two pinned MIT-derived ONNX graphs, about 3.4 MB, downloaded only to the private research directory. Existing ONNX CPU runtime suffices; no new global environment.
- Local Qwen3-VL 4B benchmark: official pinned GGUF/projection, about 2.95 GB on Z:, reused existing Vulkan runtime. Two actual image probes; no cloud inference or model daemon left running. Not wired to automatic checks.
- Review found a false acoustic-sync certification across a mismatching middle region. Reproduced red, added overlapping local checks, cache v2, green. Real paired test now certifies zero of thirteen alternatives; preliminary positive is explicitly superseded.
- Other red/green corrections: invalidate rejected visual columns across all repeated turns; audit physical contiguous holds instead of treating every short voice turn as a flash cut.
- Final automatic verification: Python 392/392, JavaScript 262/262. Real scene replay after candidate fix retains the same ten unresolved turns; do not claim quality gains from passing interval tests.
- Public evidence and source links: docs/performance/2026-11-04-evidence-first-director.md. No native timeline apply, installer or stable update in this research branch.
- Delivery: draft PR https://github.com/azza0101/rambla-reel-director/pull/47, stacked on #37. Remote head verified against the tested local code; no merge.
