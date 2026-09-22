# Social execution fix and workflow organization — 2026-09-22

## Root causes and changes

- FIND SOCIAL consumed `visual_beats` from the normalized retrieval bundle, whose actual map is `chunks`. It silently scheduled zero beats. Global and per-beat workers now use the same normalized contract.
- Browser launch failures, empty pages, login forms, challenges and missing search markup must not masquerade as zero provider hits. Browser diagnostics and public fallback errors now survive into shot attempts and UI. Failed searches carry no fabricated hit count.
- Social searches bypass query/outcome caches so retrying after login actually searches again. Other provider caching is unchanged. Direct social adapters no longer duplicate their own attempt rows.
- The public fallback makes one bounded query per shot and detects challenge/parser responses. Browser failure details survive the per-run circuit breaker.
- Appending social results preserves existing discovery cards and recomputes proposals from retained verified clips.
- UI keeps the existing beat list, preview shelves and selection column. Controls are grouped into Source & analysis, Editorial plan, Find media. Manual import/export, provider logins and media maintenance are collapsible. Global versus current-beat scope is explicit.

## Real execution evidence

Existing imported KURA project `fea7fff128ef`, unchanged transcript and plan; no ASR, installs or new models.

- Global social worker: 20 BROLL beats / 24 shots / 48 non-cached provider attempt records, 12.778 seconds.
- Every shot has separate TikTok and Instagram attempt records, including all three airplane/bus/ferry shots of beat_002.
- Transcript, chunks, visual plan, selection and image artifacts unchanged by the global run (SHA-256 comparison).
- Existing verified clips retained. Regression additionally covers retained discovery cards/proposals after append.
- Public fallback made actual HTTP requests. In this environment it returned challenge pages and later HTTP errors, not valid empty search results.
- TikTok browser reported ProcessSingleton/profile-in-use; close the RAMBLA login browser before retrying.
- Instagram browser launch reported access denied in this execution environment.

**Limit:** successful social clip retrieval remains unverified until the local browser/profile blockers are removed. Recorded attempts prove execution, not usable candidates. No claim of successful TikTok/Instagram media acquisition is made.

Local detailed evidence: `.social-real-proof.json`, `.social-product-run.log`, `.social-api-result.json` (not committed).

## Validation

530 tests passed, Python compileall and rendered JavaScript syntax check passed. Browser-based visual review was denied by the browser authorization policy; no alternate browser access was attempted. HTML tests verify unique control IDs, grouping, and preserved controls.
