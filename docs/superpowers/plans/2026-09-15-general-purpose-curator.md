# General purpose curator implementation

User request and Issue #3 comment 5684036167 authorize continuous sequential execution and publication to feat/curation-ui-v1. Base: b7e82ef3c817e7f0a124c79acb3f99ea07c54caf. Local tracked files verified byte-identical to remote.

## Design
Reuse the stage split, local Qwen generator/embedding adapters, provider adapters, asset cache, safe media routes and ordered selection store. Replace template selection with strict generated visual-plan JSON. Cache each chunk using global topic, neighbouring speech, timing, model and prompt version. Invalid model output is repaired once, then reported as a planning failure with no fabricated search intent. KURA belongs in fixtures only.

## Execution checklist
- [ ] Planner: first add regression tests for context, strict JSON, repair, model roles, cache and three unrelated domains. Implement generative planning and a dedicated local Director subprocess. Verify focused tests and actual model output; publish the completed planner integration.
- [ ] Sourcing: test image dimensions, perceptual duplicates, cross-chunk repetition and provider changes invalidating cache. Add configured official Google adapter, HD filtering, preview hashes and explicit empty states. Rank concrete shots; retain fewer results rather than fill shelves.
- [ ] Video/UI: test thumbnail discovery versus verified playable local clips. Reuse ffmpeg materialization for 3-second MP4 previews, render discovery cards with provenance links, keep inspection separate from selection. Implement bounded console/transcript split.
- [ ] Analyze: test unique atomic writes with sharing-violation retries and project exclusion. Run ASR in the existing pipeline runtime, preflight CUDA locally and report mode before transcription.
- [ ] Acceptance: run focused and full tests, compile backend, generate KURA plus cybersecurity/cooking/personal-finance plans, run cached-media sourcing, measure coverage/duplicates, verify media MIME/duration, publish and verify exact remote file set and launcher command.

## Constraints
resolve_calls=0; source media read-only; no ComfyUI, global Python/PATH/CUDA changes, credentials in artifacts, merge to main or destructive workspace operations. Runtime/model artifacts remain outside Git under approved Z: roots. One worker. API publication checks expected parent before non-forced ref update.
