# RAMBLA Professional Curation UI Redesign

**Status:** APPROVED IN NORMAL CHAT on 2026-09-15 with `APPROVO REDESIGN`.

**Supersedes for product/UI behavior:** `docs/superpowers/specs/2026-09-15-curation-ui-v1-design.md` and the UI/API assumptions in `docs/superpowers/plans/2026-09-15-curation-ui-v1.md` whenever they conflict with this document.

## Goal

Turn the current debug-style curation page into a professional local editorial application. The product must start from a source video, derive or accept an audio guide, reuse the existing RAMBLA analysis engine, then let the editor curate real video and image candidates phrase-by-phrase with durable multi-selection and deterministic V2/V3/V4… track assignment.

The normal user must not need to type Windows paths, inspect JSON, read logs, or understand provider/Qwen internals.

## Product split

Two surfaces remain intentionally separate:

- `/debug` — engineering/debug runner, logs, stage diagnostics, artifact paths.
- `/curation` (and `/` may redirect here later) — the professional editorial product.

The professional UI must not look or behave like the debug runner.

## 1. Project/source-video entry

The first screen is **New Reel / Project Setup**.

### Source video

Provide two local-first input modes:

1. **Choose / drag & drop video** — browser file picker uploads the file to a project-scoped source area under the approved RAMBLA runtime root. No cloud upload.
2. **Register local path** — advanced option for large files already on local/network storage such as `Z:`. The server validates the file and records it without copying it.

After selection show:

- real source-video player;
- filename;
- duration;
- fps;
- resolution;
- audio-stream present/missing state.

The source video is treated read-only after registration.

### Audio guide

Default control: **Use original audio** = ON.

If the source contains audio, extract it once with FFmpeg to a project-scoped guide file, e.g.:

`<project>/source/guide-audio.wav`

Recommended extraction:

```text
ffmpeg -y -i <source-video> -vn -ac 1 -ar 16000 -c:a pcm_s16le <guide-audio.wav>
```

The guide audio is the canonical audio input for ASR/timing-oriented stages. Extraction is cached by source signature and must not repeat when unchanged.

Also provide **Replace guide audio** for WAV/MP3/M4A. External guide audio is copied into the project source area and normalized to WAV. If its duration materially differs from the source video, show a visible warning; do not silently time-stretch in V1.

If the video has no audio, show a clear `No source audio` state and offer external guide audio.

## 2. Analysis as product workflow

Primary CTA: **ANALYZE REEL**.

The user sees a clean stage progression, not developer logs:

`Audio -> Transcript -> Phrases -> Search -> Ranking -> Previews`

Reuse-first is mandatory:

- unchanged source + existing transcript/chunks/candidates/edit plan => reuse;
- existing image-candidates => reuse;
- only missing preview artifacts are materialized;
- do not rerun ASR/Qwen/provider discovery merely to render the UI.

Detailed logs remain available only in `/debug`.

## 3. Professional curation workspace

Desktop-first three-zone layout:

### Left rail — phrase navigator

Shows all semantic phrases in timeline order with:

- phrase number;
- start/end timecode;
- short text preview;
- state chip: `Needs choice`, `Selected`, `NO BROLL`, `Error`.

Clicking a row activates that phrase.

Filters at the top:

- All
- Needs choice
- Selected
- NO BROLL
- Errors

### Center — active phrase + media shelves

At top:

- full phrase text;
- source time range;
- small source-video context preview for that time range when practical.

Then two clearly separate shelves.

#### VIDEO SUGGESTIONS

Maximum 3 candidates. Never invent filler.

Each card must contain a real video preview:

```html
<video muted loop playsinline preload="none" poster="...">
```

Behavior:

- poster visible immediately;
- preview source lazy-attached with `IntersectionObserver`;
- hover/focus plays;
- mouseleave/blur pauses and returns to start;
- no global autoplay storm.

Card metadata shown compactly:

- provider/source;
- short title/description;
- final/relevant score when available;
- source clip range;
- rights/provenance state.

#### IMAGE SUGGESTIONS

Maximum 4 candidates. Never invent filler.

Each card must show a real thumbnail image, not a text link. Clicking the media body opens a large lightbox. Image provider/source and rights state remain visible.

Image previews may come from Wikimedia and optional Pexels Photos or later adapters. Full-resolution image acquisition remains deferred until selection unless already required by another verified stage.

### Right rail — Selection Tray

Persistent selection tray for the active phrase.

Selection is **multi-select**, ordered, and independent from media inspection.

Example:

- `V2 · video A`
- `V3 · image C`
- `V4 · video B`

The user can reorder selected items with explicit up/down controls in V1; drag reorder is optional.

`NO BROLL` is a separate mutually-exclusive command. Activating it clears selected visual assets for that phrase. Selecting a visual asset clears NO BROLL.

Global progress shown in the top bar, e.g. `18 / 31 phrases curated`.

## 4. Interaction model

Clicking the **media body** opens/plays/inspects the asset.

Clicking the **selection control** toggles selection and must not open the inspector/lightbox.

Selection state is visually obvious with:

- high-contrast selected border;
- check badge;
- assigned track chip (`V2`, `V3`, `V4`...).

Autosave after every selection change. Header shows:

- `Saving...`
- `Saved`
- `Save failed — Retry`

On save failure, keep the local visible state and expose retry; do not silently revert.

Refresh/restart must restore selections.

## 5. Selection persistence

The old shape `chunk -> single string` is invalid for the professional product.

Canonical request:

```json
{
  "chunk_id": "chunk-001",
  "asset_ids": ["video-a", "image-c", "video-b"],
  "no_broll": false
}
```

Canonical persisted selection-plan fragment:

```json
{
  "chunk_id": "chunk-001",
  "no_broll": false,
  "selected_assets": [
    {"asset_id": "video-a", "order": 0, "track": "V2"},
    {"asset_id": "image-c", "order": 1, "track": "V3"},
    {"asset_id": "video-b", "order": 2, "track": "V4"}
  ]
}
```

Track assignment is deterministic from selection order. No Resolve mutation occurs in this phase; the plan only prepares the later apply step.

## 6. Candidate/media contract

Every UI candidate must resolve by `asset_id`, never by a browser-supplied raw filesystem path.

Minimum candidate view fields:

```text
asset_id
chunk_id
kind: video | image
provider
source_page
title
description
score
rights_state
orientation
preview_status
preview_url
poster_url (video optional)
source_start_seconds (video optional)
source_end_seconds (video optional)
selected
track (when selected)
```

Server media endpoints resolve `asset_id` through the run/project candidate index and verify the resolved file lives inside approved output/cache roots.

The current `/api/curation/media?path=...` contract must be removed from the professional surface.

## 7. Preview materialization

### Video

Create lightweight local previews, normally ~2.2 seconds, max width 480, no audio:

```text
ffmpeg -y -ss 0 -i <bounded-input> -t 2.2 -vf "scale='min(480,iw)':-2" -an -c:v libx264 -preset veryfast -crf 28 -movflags +faststart <preview.mp4>
```

Generate poster:

```text
ffmpeg -y -ss 0.2 -i <preview.mp4> -frames:v 1 -q:v 3 <poster.jpg>
```

Reuse existing bounded/local clip when available. Preview failures are isolated per card.

### Image

Fetch/cache only the thumbnail for browsing, bounded to a safe byte cap (8 MiB target). Full image is deferred until selected.

### Cache

Stable content key includes candidate identity, source URL/page, source clip range and preview version. Reopening the product must reuse cached previews.

## 8. Project/run API

The professional surface needs project-oriented endpoints. Exact routing may follow existing FastAPI conventions, but contracts must cover:

- create/register project source video;
- register local source path;
- upload source video as local-only raw bytes/stream;
- extract/replace guide audio;
- start/reuse analysis;
- get project/run state;
- get phrase/candidate curation data;
- set ordered selection for one phrase;
- fetch `selection-plan.json`;
- serve preview/poster/image by `asset_id` + variant.

No endpoint accepts an arbitrary filesystem path for media serving.

Avoid introducing a cloud dependency. If browser upload requires a new package solely for multipart, prefer a raw streamed upload endpoint or another stdlib/FastAPI-native route unless the dependency is explicitly justified and isolated.

## 9. Top-level professional UI

The top bar contains:

- RAMBLA / project name;
- current source filename;
- curated phrase count;
- filters;
- autosave status;
- primary action `CONFIRM PLAN` when every phrase has a selection or NO BROLL.

`CONFIRM PLAN` validates and freezes a reviewable `selection-plan.json`; it still does not mutate Resolve.

The visual language must be restrained and professional: dark neutral canvas, clear typography, generous spacing, large media, minimal technical chrome. Avoid dashboard-card clutter, tiny buttons, raw JSON, log windows or developer metrics on the professional page.

## 10. Runtime boundary

Normal runtime remains local-first:

- FastAPI local server
- FFmpeg/ffprobe local
- faster-whisper local
- Qwen local
- local preview/cache
- external media provider APIs only where configured

No GPT/OpenAI/Codex call is required for normal use of the application.

## 11. Security and filesystem rules

- Resolve remains frozen: `resolve_calls=0`.
- No ComfyUI/global Python/system/CUDA mutation.
- Source media read-only after registration.
- Credentials never appear in Git, UI payloads, logs, selection plan or preview URLs.
- Generated project/runtime artifacts stay under approved RAMBLA roots.
- No single download exceeds the existing 5 GiB autonomy boundary.
- Preview/media errors are isolated and visible per candidate.

## 12. Acceptance criteria

The redesign is not complete until a user can do all of the following from the professional page without typing filesystem paths or opening `/debug`:

1. choose or register a source video;
2. see the source video metadata/player;
3. use extracted original audio as guide or replace guide audio;
4. run/reuse analysis;
5. open a phrase and see real video previews and real image thumbnails when candidates exist;
6. inspect media independently from selecting it;
7. select multiple mixed media items for one phrase;
8. see deterministic V2/V3/V4 assignment;
9. set another phrase to NO BROLL;
10. refresh and retain state;
11. obtain `selection-plan.json`;
12. complete the above with `resolve_calls=0` and zero GPT/OpenAI runtime dependency.

KURA remains the first reuse-first acceptance project. Expensive upstream analysis must not be rerun merely to verify UI behavior.