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

## Follow-up: visible login and real preflight

The previous fix repaired routing but did not establish working browser access. The login launcher also mistook process creation for a successful browser launch.

- FIND SOCIAL and ADD TIKTOK + IG now open a connection dialog and request visible login windows for both providers.
- VERIFY & SEARCH checks the actual provider search page. Profile-directory existence never establishes login. Search access and observed login state are reported separately; a failed check prevents the full search.
- Immediate nonzero browser exit becomes an explicit error, not a false `started` response.
- If all social attempts fail, the worker exits as failed while preserving attempt artifacts; the UI reloads diagnostics even for failed runs.
- `RUN_RAMBLA_V5.cmd` / `launch_local_v5.py` launch the existing project runtime when invoked by the user. No installations, global environment changes or model downloads. The user-launched server is distinct from servers started inside the agent sandbox.

Real follow-up probe: TikTok visible launch exited 21 and check reported profile_in_use. Instagram visible launch exited 4294930433 and check reported browser_access_denied. Both checks returned ready=false, login_state=unknown. Successful social media retrieval remains blocked and is not claimed.

537 tests pass, including executable JavaScript checks that opening the dialog does not start sourcing, a failed provider check prevents sourcing, and successful checks dispatch the correct whole-project or single-beat action. Python compile and rendered JS syntax pass. The local launcher requires user execution; it was not used to circumvent the restricted runtime.
