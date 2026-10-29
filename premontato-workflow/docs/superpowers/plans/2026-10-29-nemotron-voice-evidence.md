# Nemotron Voice Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task; single-agent execution requested.

**Goal:** add a cacheable local diarization second opinion and verify its effect on the observed-performance editor.
**Architecture:** a native adapter normalizes anonymous source-local turns; a pure fusion module accepts only independently supported fallback identities; worker actions and the experimental editor expose provenance and progress.
**Tech Stack:** existing Python/NumPy, official NeMo-Speech.cpp v0.2.0 portable runtime, Nemotron-3-Diarization Q8_0.
**Spec:** ../specs/2026-10-29-nemotron-voice-evidence-design.md

## Global Constraints
- No cloud calls, private media uploads, global dependencies, GUI automation, source mutation, or stable release.
- Preserve speech, frame coordinates, independent-take support and installed product behavior.
- A mapped voice is not visible-speaker proof; fallback-only identities cannot enrol faces.

## Review Focus
- Long recordings must use the bounded preset and bounded child-process lifetime.
- Repeated/overlapping anchors must not certify a cluster.
- Anonymous IDs from different recordings must never be conflated.
- Corrupt outputs/cache must not be cached or turned into confident identities.
- Missing CUDA/model/runtime must preserve baseline voices and explain the fallback.

### Task 1: native diarization adapter
- [x] Add failing tests in tests/unit/test_diarization.py for validation, frames, cache, failure and CPU fallback.
- [x] Implement worker/diarization.py with explicit model/runtime discovery and validated success-only cache.
- [x] Run focused tests; verify actual model and process outputs on real WAVs.

### Task 2: conservative fusion
- [x] Add failing tests in tests/unit/test_voice_fusion.py for independent anchors, unknowns and contradictions.
- [x] Implement worker/voice_fusion.py; preserve primary voices and original units, attach provenance.
- [x] Expose analyze_voice_evidence in worker/protocol.py and optional hybrid evidence in worker/observed_editor.py.
- [x] Exclude fallback-only voices from face enrolment; test the protocol and integration.

### Task 3: real replay and delivery
- [x] Replay the frozen 5 clips and problematic observed excerpt; record timing/cache, speaker attribution, frame consistency and quality failures.
- [x] Render a diagnostic preview if the interval audit permits it; do not claim an editorial pass from that alone.
- [x] Run full Python and JavaScript suites; inspect the intended diff, commit, push a separate PR without merge/release.
- [x] Document research findings from Ghost Editor, ffmpeg-skill and OpenMontage as references, not runtime requirements.
