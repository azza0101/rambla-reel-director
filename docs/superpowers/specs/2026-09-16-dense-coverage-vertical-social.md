# Dense Coverage + Vertical Social Design

## Goal
Make RAMBLA keep visual coverage active across almost the entire spoken reel while adding a first-class portrait social source tier for YouTube Shorts, TikTok and Instagram Reels.

## Product behavior
- Preserve the imported editorial plan as the source of truth; do not mutate transcript, timestamps or imported beat IDs.
- Future exported editorial-input instructions should target roughly 90–98% spoken-duration visual coverage through `BROLL` and `CONTINUE_PREVIOUS_VISUAL`, with `KEEP_TALKING_HEAD` reserved for deliberate intro/punchline/CTA or delivery-critical moments.
- Display visual-coverage percentage in Curation so under-covered plans are obvious before sourcing.
- Do not fabricate B-roll to satisfy a quota; continuity is preferred over meaningless filler.

## Video source tiers
### Vertical Social
A dedicated shelf containing only playable portrait clips from:
1. YouTube Shorts — robust/default vertical source.
2. TikTok public videos — opportunistic web discovery + yt-dlp extraction.
3. Instagram Reels — opportunistic web discovery + yt-dlp extraction; failures are explicit because Instagram often requires authentication or changes extractor behavior.

Every final card must be a local playable 2.5–4.5 s clip. Discovery-only links are diagnostic leads, never selectable final cards.

### YouTube / Repertory
Keep the existing localized normal-YouTube path for useful long-form source footage.

### Stock / Pexels
Keep the independent Pexels stock shelf and provider budget.

## Vertical discovery
- Add a provider-neutral `VerticalSocialSource` contract.
- YouTube Shorts uses yt-dlp search with full metadata, short-duration filtering and portrait aspect-ratio verification.
- TikTok/Instagram discovery uses a bounded public web-search adapter (DuckDuckGo HTML) to find public post URLs, then yt-dlp probes each URL for duration, thumbnail and dimensions.
- No browser cookies are read automatically. If Instagram extraction fails, surface a provider/extraction error and continue with Shorts/TikTok/Pexels.
- No credentials are committed or serialized.

## Ranking and selection
- Vertical Social candidates must be portrait (`height > width`).
- Rank actual sampled clip frames against the exact imported shot description/query.
- Prefer vertical candidates when relevance is comparable; never accept a weak vertical clip solely because it is vertical.
- Keep provider-independent dedupe and per-shot budgets.

## Persistence / no reanalysis
- Project artifacts already live on disk under RAMBLA's project root and analysis must remain reuse-first.
- Fix the acceptance launcher to use a stable `127.0.0.1:8765` origin by stopping its previous recorded acceptance-server process before restart. Stable origin preserves browser localStorage so the last project ID reopens automatically.
- Do not rerun ASR when source + guide are unchanged.
- Imported visual plan, retrieval artifacts and selection plan remain project-local and reusable.

## UI
- Add `VERTICAL SOCIAL` shelf above normal YouTube/stock shelves.
- Cards show provider (`YouTube Shorts`, `TikTok`, `Instagram`), source URL, portrait badge, clip time range and local playable preview.
- Show plan visual-coverage percentage near editorial-plan status.
- Existing sticky independently scrolling Visual Beats rail remains unchanged.

## Safety / constraints
- `resolve_calls=0` remains mandatory.
- No OpenAI/GPT/Codex runtime dependency.
- No new global Python/PATH/CUDA/ComfyUI changes.
- No automatic reading of browser cookies.
- Social providers are best-effort; unavailable providers must fail independently and never block other shelves.
- No merge to main.

## Acceptance
1. Reloading the acceptance launcher on the same machine reopens the previous project without re-analysis when source/guide are unchanged.
2. Exported editorial-input instructions explicitly request dense visual coverage.
3. Curation reports the plan's visual coverage percentage.
4. A vertical-social search produces at least a YouTube Shorts provider attempt for each BROLL shot and only portrait final candidates.
5. TikTok and Instagram providers record real discovery/extraction attempts or explicit provider errors; no fake success cards.
6. Normal YouTube and Pexels continue functioning independently.
7. All selectable videos are local playable clips with bounded duration and source timing.
8. `resolve_calls=0`.