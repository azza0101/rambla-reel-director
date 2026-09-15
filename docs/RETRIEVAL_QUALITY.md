# Retrieval quality — regression work, not product validation

The imported beat/shot is authoritative. Retrieval never creates a new editorial
plan, changes the subject, or calls a generative model. No new runtime or package
is required. Qwen3-VL-Embedding-2B, when already available locally, ranks images
and sampled video frames only.

## Behavior

- Separate SOCIAL / YOUTUBE and STOCK / PEXELS shelves, up to three candidates
  each. Fewer are valid when quality is weak. Selection requires a playable,
  relevance-checked clip. Sources without previews remain visibly **source found /
  preview pending**, with selection disabled and no invented start/end.
- Pexels Photos is primary; the existing Google Custom Search adapter is secondary
  when its two settings are present; Wikimedia is last fallback. No Bing adapter
  or Google credentials are installed automatically.
- Image searches use imported image queries, never video queries. Bounded aliases
  and removal of nonessential camera/container wording preserve subject and
  condition. The original query, expanded query, provider hits and rejections are
  recorded. Example: `wilted basil plant` → `wilting basil plant` → `wilted basil`.
- Exact shot descriptions drive ranking, including when two shots share a query.
  Generic creator/vlog metadata receives a penalty. Explicit contradictory
  conditions are rejected; provider order is not a confidence score.
- Current conservative gates: visual cosine at least 0.60, combined score at least
  0.48; an unconfirmed required condition needs visual cosine at least 0.65.
  These are regression-fixture thresholds, not calibrated probabilities or proof
  of general editorial quality. Metadata-only image results are marked as such.
- Photos pass dimension checks. Source URL, content hash and perceptual hash
  remove repeated results within and across beats, including the other media
  stage. Empty results carry an explicit reason rather than filler.
- Pexels clips sample two source windows. YouTube resolves an existing video-only
  rendition up to 480p; a sampled window becomes selectable only after two local
  frames pass relevance checks. This is bounded sampling, not exhaustive scene
  localization of a long video.
- Browser previews are silent H.264 MP4, approximately 3.5 seconds. Python HTTPS
  acquisition avoids the observed Windows FFmpeg SSPI failure; FFmpeg cuts locally.
  Proxy acquisition is capped at 32 MB and a 30-second streaming budget (an active
  read can additionally take its 25-second socket timeout). Unavailable/oversize
  sources stay pending. Cached valid clips are re-ranked without reacquisition.
- Optional local embedding uses bf16 on CUDA and a 512-token pixel budget. It
  never downloads weights or changes another application's environment.
- Expandable candidate details show provider, matched query, score, quality state,
  source URL, source interval and rejection/review reasons. Missing Pexels key
  appears in UI/backend logs; only booleans are exposed, never credentials.
- Old imported retrieval artifacts are hidden with a rerun warning. Files and
  saved choices are retained on disk; users can rerun retrieval explicitly.

## Regression evidence and limits

The live probe uses a manually imported two-beat fixture: slicing tomatoes and a
wilted basil plant. No ASR or generative planning is run. Local evidence is in
`.retrieval-quality-proof/`: provider logs, actual preview media, query attempts,
rejected candidates, stage timings and `review.json`.

Measured on 2026-09-15, with previews cached from the preceding debugging runs:

| Imported shot | YouTube clips | Pexels clips | Images |
|---|---:|---:|---:|
| Hands slicing tomatoes on a cutting board | 2 | 3 | 2 Pexels |
| Wilted basil plant with drooping leaves | 0 | 0 | 1 Wikimedia fallback |

Image sourcing: **15.136 s**. Video sourcing: **77.5833 s**, including two bounded
YouTube download timeouts. These are observed warm-cache timings, not cold-start
benchmarks. Across retained images, cross-beat duplicate rate was 0.0. All eight
preview files passed API delivery checks; valid selections persisted. Separate
unit/controller tests reject pending selection and verify both three-card limits.
**331 automated tests passed**, Python 3.12/3.10 compilation passed, and the pure
JavaScript controller test passed. No interactive browser acceptance is claimed.

Manual inspection confirms cutting action in the two YouTube samples; one preview
has a visible stock watermark. The UI retains its rights-review status. Retrieval
relevance is not clearance for final use.

The expanded basil query reaches a relevant wilted plant photo via Wikimedia
after Pexels. A weak leaf close-up is rejected despite matching disease-related
metadata. Pexels slicing clips and photos are inspected against the requested
action; YouTube sources with weak sampled windows are rejected or remain pending
when acquisition fails. A short successful retrieval probe is **not KURA or
product acceptance**. Full reel quality remains for user review.

Google is supported but unconfigured in this local probe. Provider availability,
network throttling, language of metadata, semantic thresholds, and sparse sampling
can still reduce coverage. Inspect candidates before using them editorially.

## Reproduction

Run the normal project-local launcher:

```powershell
& 'Z:\APP REEL TEST\qwen-embedding-smoke\curation-ui-plain\tools\start_curation_acceptance.ps1'
```

Import a VisualPlan, then choose FIND B-ROLL / FIND IMAGES. The launcher name is
historical; running it does not declare the product accepted.

Run automated behavior tests with the existing UI Python:

```powershell
& 'Z:\APP REEL TEST\qwen-embedding-smoke\editorial-intelligence-worktree\.venv\Scripts\python.exe' tools/run_workspace_tests.py -q
```

After running the image/video sourcing CLIs on a manual imported fixture, audit
actual files through API media endpoints and selection persistence without
running more searches:

```powershell
& 'Z:\APP REEL TEST\qwen-embedding-smoke\editorial-intelligence-worktree\.venv\Scripts\python.exe' tools/review_retrieval_quality.py --run .retrieval-quality-proof/run
```

The script creates an isolated fixture project, copies only the fetched previews
into its safe media root, checks MIME/intervals, blocks pending selection, and
saves a readable report. Pure controller tests cover shelf separation and debug
visibility; interactive browser validation is a separate review step.
