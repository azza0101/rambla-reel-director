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

## Explicit start and independent providers

VERIFY CONNECTIONS now only checks connections. A separate START SEARCH button becomes available as soon as one selected provider is ready. Ready providers are selected automatically; blocked providers are disabled and skipped. Both whole-project and beat-specific searches carry the selected provider list to the worker; an Instagram login failure no longer prevents a TikTok-only search. Search-start errors remain in the dialog and a successfully accepted job switches to the normal progress view.

Validation: 539 tests pass, Python compilation and rendered JS syntax pass. Executable JS tests cover TikTok-ready/Instagram-blocked, no automatic search during verification, explicit start, provider deselection, and correct whole-project/per-beat payloads. API and command tests verify TikTok-only routing and reject empty/unsupported provider selections. No new real media acceptance is claimed by these UI/routing tests.

## DOM capture timeout

The installed-browser fallback previously used virtual time but no real Chrome capture deadline. It now uses the documented `--timeout=15000` capture bound, retaining a separate 25-second process deadline. If the process deadline fires after a complete HTML document was emitted, that document is inspected normally; incomplete/empty output remains a search_timeout with login state unknown. This does not treat timeout as login failure or successful search.

542 tests pass, including complete/partial/empty output on TimeoutExpired. Python compilation passes. This addresses a confirmed command/diagnostics deficiency; resolution of the user's live TikTok hang is pending a user-runtime retry. Process inspection in the agent environment was denied. No browser processes were indiscriminately killed and no profile locks or credentials were modified.

Chrome flag reference: https://developer.chrome.com/docs/automation-and-testing/headless-cli

## User diagnostic review and bounded console

The supplied beat_002 diagnostics contain 21 historical TikTok attempts and 18 Instagram attempts. Latest TikTok rows for airplane, bus and ferry contain zero extracted search cards; public fallback errors are ReadError/ConnectTimeout. Historical provider errors remain in the appended artifact. No verified new TikTok clips are established.

Search diagnostics now have a 320px internally scrolling console and COPY CONSOLE copies the complete JSON, with explicit clipboard failure feedback. Search/login evidence now excludes script/style/template and inline-hidden contents instead of matching strings in raw HTML. This prevents translation strings such as `no results found` from being accepted as a real empty search page. Unrecognized result pages remain search_results_unavailable; title, visible text length and zero-result evidence are retained for investigation without storing private HTML.

546 tests pass; compile and rendered JavaScript syntax pass. A browser fixture containing `no results found` only inside a script is rejected as unavailable, with no fabricated hit count. Actual TikTok acquisition remains unresolved; these changes do not claim provider success.
