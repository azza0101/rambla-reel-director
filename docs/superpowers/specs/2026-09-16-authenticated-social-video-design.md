# Authenticated Social Video Discovery Design

## Goal

Make RAMBLA reliably discover useful short-form and news video from TikTok, Instagram Reels, YouTube Shorts and the wider web, while separating *finding the right source* from *being able to download it automatically*.

The system must always preserve useful source cards. A provider result may become a verified local clip, a preview-only card, or a link-only manual-download card; download failure must never erase a semantically useful result.

## User experience

RAMBLA exposes dedicated social/video-source state without requiring credentials in chat or in the repository.

A local browser profile is created under a configurable RAMBLA-owned directory, never the user's normal Chrome/Edge profile. The first time TikTok or Instagram authentication is needed, RAMBLA opens a visible browser window using that profile. The user logs in manually. Later searches reuse the same profile and authenticated browsing state.

For each discovered candidate RAMBLA displays one of three acquisition states:

- `CLIP_READY`: a verified local 3–5 second clip exists and can be selected normally.
- `PREVIEW_ONLY`: RAMBLA has a thumbnail or browser-captured preview plus public source URL, but automatic bounded download failed.
- `MANUAL_LINK`: RAMBLA has title/creator/source URL and possibly thumbnail; the user can open the source and download manually.

Preview-only and link-only cards remain visible and rankable, but are not selectable as final media until a local file exists. They have an explicit `OPEN SOURCE` action.

## Architecture

### 1. BrowserProfileManager

New module responsible only for persistent browser profile lifecycle.

Responsibilities:

- derive provider-specific RAMBLA profile directories;
- ensure profiles stay outside project artifacts and Git;
- launch a visible Playwright Chromium/Edge persistent context;
- expose provider login/open helpers;
- serialize access so the same profile is never opened by two Playwright contexts at once;
- never store username/password or 2FA data.

Default profile root is controlled by `RAMBLA_BROWSER_PROFILE_ROOT`; when unset it is a local sibling of the project store named `browser-profiles`.

The implementation uses Playwright persistent contexts with a dedicated `user_data_dir`; it never points Playwright at the user's normal browser profile.

### 2. Authenticated social discovery

TikTok gets first-class browser-backed discovery because TikTok search quality is the primary requirement.

`TikTokBrowserSource` navigates to TikTok search in the persistent authenticated context, submits the query, waits for video result links, scrolls a bounded number of times, and extracts public result metadata:

- canonical video URL;
- provider video id;
- caption/title text when available;
- creator name/page when available;
- cover/thumbnail URL when available;
- discovery rank.

DOM extraction uses semantic URL patterns (`/@.../video/...`) and resilient text/attribute fallbacks rather than screen coordinates. If TikTok changes markup, the source records a provider-local structured failure and leaves other sources operational.

`InstagramBrowserSource` follows the same interface for Reels. Its initial discovery is allowed to be less aggressive: authenticated browser search when results can be extracted, plus existing public-web `site:instagram.com/reel` discovery as a fallback.

### 3. Authenticated acquisition

Automatic download is attempted after discovery, never before discovery is accepted.

For TikTok/Instagram candidates RAMBLA tries, in order:

1. `yt-dlp` with cookies from the dedicated RAMBLA browser profile and current browser user-agent;
2. bounded source download/materialization using the existing 3.5-second clip path when a direct media URL is available;
3. if acquisition fails, retain the candidate as `PREVIEW_ONLY` or `MANUAL_LINK`.

Cookie material is never committed, logged, serialized into project JSON, or copied into the repository. Command logging redacts cookie/profile arguments.

### 4. Web/news video discovery

`WebVideoSource` provides provider-agnostic web video results for current events/news. It is designed behind a small adapter interface so discovery backends can be replaced without changing curation.

Phase 1 uses the existing web-search approach and canonical source pages to produce preview/link candidates from video pages across TikTok, Instagram, YouTube and publishers. Optional Brave Video Search or Google Videos/SerpAPI adapters may be added later without changing the candidate contract.

The core requirement is that a result can enter RAMBLA without a downloadable file.

### 5. Unified candidate contract

Social/video discovery candidates gain these fields:

- `acquisition_state`: `CLIP_READY | PREVIEW_ONLY | MANUAL_LINK`;
- `source_page`: canonical public URL;
- `preview_url`: remote thumbnail/cover if available;
- `local_preview_path`: optional local image/video preview;
- `selectable`: true only for `CLIP_READY` with verified local clip;
- `manual_reason`: concise download/materialization failure reason;
- `source_authenticity`: existing provider confidence signal.

Existing candidate fields remain compatible.

Qwen ranking may evaluate preview-only/link-only candidates using cover/thumbnail plus title/caption metadata. A remote preview can influence discovery ranking, but only a verified local video clip can become final selected B-roll.

### 6. Curation UI

Video shelves remain provider-separated and add explicit source/acquisition badges:

- `TIKTOK`
- `INSTAGRAM REELS`
- `YOUTUBE SHORTS`
- `WEB / NEWS VIDEO`
- existing general YouTube and stock shelves.

Cards show `CLIP READY`, `PREVIEW`, or `MANUAL` state. `PREVIEW`/`MANUAL` cards expose `OPEN SOURCE` and remain non-selectable until materialized.

A small `SOCIAL LOGIN` control opens the provider profile browser for TikTok or Instagram. This action does not run Analyze, ASR, Qwen or Resolve.

### 7. Failure isolation

Every provider records structured attempts and errors. A TikTok login wall, Playwright selector failure, Instagram rate limit, yt-dlp extractor failure, or missing thumbnail must not abort the beat or hide candidates from other providers.

Provider diagnostics distinguish:

- no search hits;
- authentication required;
- browser unavailable/not installed;
- DOM/search extraction changed;
- download failed;
- local clip failed verification;
- semantic rejection.

### 8. GPU independence

Browser discovery, HTML parsing, yt-dlp acquisition and thumbnail handling are CPU/network tasks. They must run without loading Qwen or consuming GPU memory. Existing Qwen ranking remains a later optional ranking stage when the GPU is available.

### 9. Security and storage

- Never request or store raw TikTok/Instagram passwords.
- Never commit browser profile directories or cookies.
- Never expose cookies in diagnostics or command logs.
- Use a dedicated RAMBLA browser profile, not the user's default Chrome/Edge profile.
- Browser automation is bounded: limited scrolls/results and explicit timeouts.
- `resolve_calls` remains `0`.

## Compatibility

Existing public-web TikTok/Instagram discovery remains as fallback. Existing YouTube Shorts, Pexels, project manifests, transcript, visual-plan, beat research, clean media and selection behavior remain compatible.

The social browser subsystem is additive: projects created before this feature open normally, and no re-analysis is required.

## Acceptance criteria

1. A test browser adapter can return TikTok/Instagram candidates from a persisted provider profile without any password field in RAMBLA.
2. TikTok/Instagram download failure produces a visible non-selectable candidate with public link instead of dropping the result.
3. A successful authenticated acquisition becomes a verified local `CLIP_READY` candidate.
4. Browser profile/cookie paths are redacted from logs and absent from project manifests/artifacts.
5. Provider failures do not prevent Shorts, general YouTube, stock or image sourcing.
6. The curation API/UI exposes acquisition state and source link for every social/web candidate.
7. Login/profile operations and discovery do not invoke Analyze/ASR or Resolve.
8. Existing focused CI, JavaScript syntax check and backend compile remain green.
