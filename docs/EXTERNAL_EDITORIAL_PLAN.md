# External editorial plan import

The primary product path is **Analyze → Copy/Export editorial input → Import editorial plan → Find B-roll / Find images → Curate visual beats**. RAMBLA consumes a JSON contract; it has no ChatGPT, OpenAI API, cloud-model or generative-model requirement.

## Contract and input

`visual-plan.schema.json` defines `rambla-visual-plan-1`. The contract includes project identity, transcript signature, topic, visual beats, exact start/end seconds, covered chunk IDs, original speech, editorial function/core meaning/subtext, action, visual mode, shot descriptions, image/video queries and avoid lists. CONTINUE requires `continuation_from` referencing the immediately preceding visual beat. Only BROLL carries shots.

Analyze retains faster-whisper word timings and semantic chunks. COPY EDITORIAL INPUT copies instructions plus the complete JSON package; EXPORT downloads it as JSON. The package contains duration, language, full speech, original chunks/times, word timestamps when available, project ID, transcript signature, instructions and the schema. It can be given to any planner or edited manually. RAMBLA itself does not send the transcript to a model.

The instructions require whole-reel beat grouping, current-meaning authority, no context leakage, factual restraint, respect for negations, one concrete visual by default, justified sequences, simple English queries and no forced symbolic filler/repetition.

## Import and isolation

IMPORT EDITORIAL PLAN accepts pasted JSON or a `.json` file. Errors identify the field or beat needing correction. Validation rejects malformed or duplicate JSON fields, unknown keys/enums, missing data, duplicate IDs, invalid/boolean/nonfinite times, wrong project/signature, missing/repeated/out-of-order chunks, incorrect spoken text/time boundaries, unbound continuity and invalid shot/query counts. Every transcript chunk must be covered once in order. Leading/trailing or repeated query whitespace and case-only duplicate queries are rejected, keeping supplied queries stable.

JSON Schema covers the structural contract. Cross-field and transcript-dependent checks run on import and before sourcing. Editorial truth, English fluency and search suitability remain the external planner/reviewer's responsibility; structural validation is not a claim of semantic verification.

Imports are atomic. `run/visual-plan.json` remains the unchanged imported contract. A SHA-256 plan digest selects `run/editorial/<digest>/` for candidates, retrieval diagnostics and selections. Reimporting identical JSON preserves selections. A changed plan gets an isolated version; previous results remain on disk. Changing source/guide requires fresh Analyze/export and a matching plan before sourcing. Project stages and imports share the project OS lock.

## Retrieval and curation

- Each imported BROLL shot searches its supplied queries directly. KEEP and CONTINUE generate no searches. There is no template or generative fallback.
- Image ranking uses the shot description. Optional Qwen3-VL video ranking also uses the supplied shot description, never the transcript as an editorial prompt.
- Default ranking uses provider order and labels the result as unscored by a model. `RAMBLA_RETRIEVAL_RANKING=qwen` explicitly enables the existing local embedding ranker; no automatic downloads/installations are added.
- Provider/source URL, rights state, available license/attribution and shot identity survive retrieval. Wikimedia images retain the actual reported license. YouTube discovery does not establish a reuse license.
- Exact-source/content hashes and perceptual hashes suppress repeated candidates across beats, including images versus video previews from the other completed stage. Same-beat alternatives remain available.
- The UI uses visual beats, with original speech/time range, covered chunks, action and intended shots. The shelf keeps up to three videos and four images, prioritizing coverage of each requested shot. Selection ordering persists as V2/V3/V4…; NO BROLL and continuity remain explicit.
- Video cards are playable only after probing an actual video preview. YouTube thumbnails stay labeled discovery; they are not represented as downloaded clips.
- `resolve_calls=0`. Retrieval reports preserve the imported action/timing and do not run the legacy RuleDirector.

## Optional local producer

The injected `generate(prompt)` Director and experimental local Qwen path remain available. `visual_planner_cli --editorial-input <exported-package.json>` can adapt a completed experimental result into `external-visual-plan.json`, using the same validation. Run it in a separate experimental output directory, then import the proposal normally. It is not invoked by sourcing. The earlier Qwen4B quality failure remains a limitation of that optional producer, not a dependency of import/retrieval.

## Acceptance: 2026-09-15

`tools/accept_external_editorial.py` is an explicit live-provider acceptance script. It uses an eight-second synthetic source and a manually supplied transcript/plan fixture, not new ASR or generated editorial output. It exercises real project API routes and real isolated video/image workers.

| Imported beat | Covered chunks | Exact range | Action |
|---|---|---|---|
| vb-1 | c1, c2 | 0–6 s | BROLL: hands slicing tomatoes |
| vb-2 | c3 | 6–8 s | KEEP_TALKING_HEAD |

Speech: “Slice the tomatoes. Keep the pieces small.” → supplied shot “Hands slicing tomatoes on a cutting board” → unchanged image query `sliced tomatoes` and video query `slicing tomatoes close up`.

Latest live run: **2.284 s video**, **2.535 s images**, measured from stage API start to completion. The shelf contained **3 YouTube discovery cards, 0 playable videos, 4 Wikimedia images**. All seven preview URLs returned real media bytes successfully. Source links and image licenses (CC BY-SA 4.0 / CC0) survived. Imported JSON remained unchanged, API selection persisted V2/V3/V4, and KEEP generated no provider calls. No generative model was loaded or called. These are fixture retrieval timings, not a KURA or semantic-quality acceptance claim.

Verification: **316 tests pass**, Python 3.12 and pipeline Python 3.10 compilation pass. Tests cover source/plan isolation, invalid imports, continuity, multiple shots, default operation with model construction forbidden, cross-media dedupe, selection mapping, and pure JavaScript controller copy/file/paste/error/gating behavior. Interactive browser inspection was denied by browser permissions; no visual browser QA is claimed.

Local evidence is under `.external-plan-proof/` (not committed): input JSON/text, imported plan, worker events, curation payload and `acceptance.json`. No credentials, source media, previews, weights or runtime logs are published. The committed manual fixture is `tests/fixtures/external-editorial-manual.json`.

## Launch

```powershell
& 'Z:\APP REEL TEST\qwen-embedding-smoke\curation-ui-plain\tools\start_curation_acceptance.ps1'
```

The launcher obtains the verified branch build and prints the local URL. Open `/curation`, load a reel, Analyze, Copy/Export, then Import before either FIND action. The launcher uses existing project-local dependencies. The actual ChatGPT/KURA editorial instructions and plan are a separate next step; no OpenAI integration is included.
