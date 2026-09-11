# Project Brief — RAMBLA REEL DIRECTOR

## Mission

Build a professional, local-first AI Social Reel Director for 9:16 talking-head content. Its value is editorial judgment: it proposes a coherent modern edit using A-roll, B-roll, editorial inserts, images, documents, screenshots, archival material, stickers, callouts, captions, keyword emphasis, punch-ins, reframing, graphics, and optional SFX.

The system is not merely an automatic B-roll inserter. The primary product question is: **does the Director have taste?**

## Core safety contract

The AI never modifies DaVinci Resolve while reasoning. Analysis produces a structured, persisted, inspectable, editable Edit Plan. A dry run performs the complete pipeline without changing Resolve. Apply Plan runs only after user approval and only against a duplicate timeline:

- source: `REEL_MASTER`
- generated copy: `REEL_AI_v01`

## Product shape

- A lightweight, modern panel inside DaVinci Resolve handles selection, controls, progress, plan review, and approval.
- A separate local Python backend—the RAMBLA REEL ENGINE—owns analysis, orchestration, assets, AI providers, persistence, diagnostics, and Resolve adaptation.
- The backend must run with Resolve closed.
- Resolve remains the editing engine.
- Resolve integration is behind an interchangeable `ResolveAdapter`; no specific MCP is foundational.

## MVP V1

Only vertical 9:16 talking-head reels. The MVP must:

1. Read a selected timeline and obtain required audio/video metadata.
2. Transcribe and align speech precisely.
3. Apply an approved Style DNA.
4. Generate a reviewable Edit Plan.
5. Propose B-roll, editorial inserts, punch-ins, stickers, and caption emphasis.
6. Search client-local assets first, then permitted global/online sources.
7. Rank visual candidates semantically and retain provenance/licensing metadata.
8. Support per-decision preview, approve, disable, modify, replace, and regenerate.
9. Dry-run without Resolve mutation.
10. Duplicate the timeline and apply an approved plan.
11. Persist structured logs and inspectable intermediate JSON.
12. Measure latency, resource use, and editorial acceptance rate.

## Explicitly outside MVP

Automated music, complex sound design, heavy generated video, horizontal workflows, horizontal-to-vertical reframing, advanced rough cut, fine-tuning, automatic learning, cloud collaboration, multi-user support, render farms, and mobile apps.

## Quality and operating principles

- Editorial quality outranks small latency gains.
- Acceptance rate is the primary quality metric.
- Local-first with optional cloud providers.
- Small modules, explicit interfaces, strong schemas, type hints, controlled cache, and structured logging.
- No opaque monolithic pipeline or silent behavior.
- No automatic learning from corrections; future adaptation must be proposed and approved by the user.
- Every model and quantization choice must earn its place through benchmarks.

## Reference languages

- **Factanza-like:** centered talking head, editorial/document/newspaper/archival inserts, bold captions, colored keywords, informational pace, frequent return to face.
- **Creator/storytelling:** talking head plus narrative B-roll, emotional pacing, strong captions, visual storytelling.

Reference media remains local and must never be committed.

