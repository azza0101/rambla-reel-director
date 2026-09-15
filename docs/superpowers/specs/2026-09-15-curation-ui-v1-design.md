# RAMBLA Curation UI V1 — Design

Date: 2026-09-15
Status: design approved in chat, pending written-spec review

## Goal

Turn the current Debug Runner into a useful human-in-the-loop curation interface before full Resolve automation.

For every semantic phrase/chunk, RAMBLA should present a compact set of **real visual previews** instead of only links or opaque scores:

- **3 video candidates** with animated lightweight previews;
- **4 image candidates** with real thumbnails;
- multi-select by the user;
- explicit `NO_BROLL` option;
- export of the selection as a timeline-ready plan where multiple assets selected for the same phrase are placed on separate stacked video tracks.

The runtime path must not require GPT/OpenAI credits. Local ASR, local Qwen, FFmpeg, FastAPI, cached assets and provider APIs/search may be used. External provider/API quotas are separate from GPT/OpenAI usage.

## Product principle

V1 is a **curation assistant**, not an autonomous final editor.

RAMBLA's job is to search, pre-filter, preview and organize strong editorial options. The user makes the final visual choice. This avoids forcing a fragile automatic ranking step to be perfect before the product is useful.

Source priority remains evidence-first:

1. exact evidence / exact subject / exact event / exact post / article / interview;
2. source-native social or archival/repertory material;
3. close editorial/cultural material;
4. generic stock only as fallback.

Orientation is not a hard rejection criterion. Landscape and square assets remain eligible when composition/crop is usable in 9:16.

## Runtime architecture

The feature extends the existing local Debug Runner rather than replacing it.

Existing path:

`video -> ASR -> semantic chunks -> Editorial Intelligence -> discovery -> candidate metrics -> review/edit-plan`

V1 adds a curation layer:

`candidate discovery -> preview materialization -> Curation UI -> user selections -> selection-plan.json -> future Resolve Apply adapter`

The new layer must remain isolated from Resolve. No Resolve mutation happens in V1.

## Candidate set per chunk

Target visible set per semantic phrase:

- up to **3 video cards**;
- up to **4 image cards**.

These are target maxima, not filler quotas. If fewer strong candidates are available, show fewer and explain why. Never fill missing slots with weak generic media merely to reach 3+4.

Each card carries:

- source/provider;
- source URL;
- source type;
- title/caption when available;
- local/remote preview URL;
- source timestamp/window for videos;
- semantic/editorial score summary when available;
- provenance/rights status;
- orientation/aspect ratio;
- crop-safety metadata when available;
- selected state.

## Video previews

Do **not** use full source videos in the page.

Preferred preview format:

- 1.5–3.0 second local MP4 or WebM;
- muted;
- autoplay only while visible or on hover;
- loop;
- low resolution and low bitrate;
- poster frame for immediate paint;
- lazy-loaded.

This behaves like a GIF to the user while remaining far lighter than an actual GIF.

For long sources, preview generation must remain bounded: use the candidate scene/window and fetch only the short preview window plus small padding. Do not download an entire long source only to create a preview when partial acquisition is possible.

Preview generation should be cached by stable key based on source identity + source window + preview settings. Re-renders must reuse unchanged previews.

## Image previews

Images should render as real thumbnails in the page, not text links.

V1 uses a provider-neutral `ImageCandidate` contract. The engine may source images from:

- exact article/news/social pages where permitted;
- Pexels or other existing image-capable provider adapters;
- Wikimedia/common public sources;
- a Bing/image-search adapter when configured with an appropriate local credential/API route.

No provider-specific key may be committed or written into artifacts. Credentials are read from environment/config outside Git.

The UI may display remote thumbnails directly when policy/terms allow, but final selected assets should be materialized locally before timeline export so the selection plan is reproducible.

## Search and ranking

No GPT/OpenAI call is required for the standard runtime.

Allowed standard-runtime components:

- faster-whisper local ASR;
- deterministic chunking and editorial rules;
- local Qwen embeddings/visual scoring;
- provider search APIs or public discovery adapters;
- FFmpeg/yt-dlp/local preview generation;
- local FastAPI UI and cache.

Search should produce several queries per chunk only when needed, but provider calls must be deduplicated and cached.

The ranking layer remains useful as a pre-filter, but V1 does not require RAMBLA to certify one final winner. Its job is to produce a small, diverse, high-quality candidate shelf.

Proposal diversity rule: visible candidates should be meaningfully different where possible, not near-duplicates of the same source/frame.

## Curation UI

The UI should be modern, dense and visual rather than debug-console-first.

### Page shell

- dark neutral background;
- high-contrast typography;
- restrained accent color;
- sticky top toolbar;
- overall run status/progress;
- source video and output summary;
- filters for `All / Selected / Needs choice / NO_BROLL / Errors`;
- compact global selection summary.

### Phrase cards

One card per semantic phrase, in transcript order.

Header:

- phrase text as the primary content;
- timecode range;
- phrase duration;
- intent/source-strategy badges;
- current selection count.

Body:

- section `VIDEO` with up to three large preview cards;
- section `IMMAGINI` with up to four image cards;
- `NO BROLL` choice;
- per-card select toggle.

Cards should clearly show selection using a border/check overlay rather than only a checkbox.

### Preview behavior

Video cards:

- poster visible immediately;
- hover/focus starts muted loop preview;
- click opens larger lightbox/player with source metadata;
- no page-wide autoplay storm.

Image cards:

- thumbnail immediately visible;
- click opens lightbox;
- preserve source metadata and original aspect ratio.

### Selection UX

Selection is multi-select.

The user can select:

- one asset;
- multiple videos;
- multiple images;
- a mix of videos and images;
- no asset (`NO_BROLL`).

`NO_BROLL` is mutually exclusive with selected assets for that chunk.

The UI autosaves local selection state after every change.

## Stacked timeline semantics

V1 does not mutate Resolve, but it must produce deterministic stacked-track semantics for the future Apply adapter.

For each chunk:

- selected assets share the chunk's timeline start/end by default;
- first selected visual -> `V2`;
- second -> `V3`;
- third -> `V4`;
- continue upward in stable selection order;
- speaker/base video remains conceptually on `V1` and is not replaced by this plan.

The exported plan must preserve selection order explicitly so later drag/reorder support can map cleanly to track order.

Example:

```json
{
  "chunk_id": "chunk_007",
  "start": 42.10,
  "end": 45.60,
  "selected_assets": [
    {"asset_id": "vid_02", "kind": "video", "track": "V2", "order": 0},
    {"asset_id": "img_04", "kind": "image", "track": "V3", "order": 1}
  ]
}
```

## Selection plan artifact

New artifact:

`selection-plan.json`

Top-level fields:

- input video identity/path;
- timeline fps;
- generated timestamp/version;
- chunk selections;
- selected asset metadata;
- local materialized path when available;
- source/provenance/rights fields;
- stacked track assignment;
- explicit `NO_BROLL` chunks;
- unresolved/error candidates excluded from selection.

The artifact must be readable without reopening the UI.

## Backend endpoints

Extend the existing local Debug Runner/FastAPI service with small, explicit endpoints instead of embedding all state in HTML.

Suggested surface:

- `GET /debug/curation` — modern curation page;
- `GET /api/curation/run/{run_id}` — chunks + candidate preview metadata;
- `POST /api/curation/run/{run_id}/selection` — save one chunk selection;
- `GET /api/curation/run/{run_id}/selection-plan` — current plan;
- local preview/media routes restricted to approved output/cache roots.

The existing `/debug` progress page may remain as a technical diagnostics view. V1 may make `/debug/curation` the user-facing surface while preserving backwards compatibility.

## Preview materialization contract

Introduce a small preview materializer independent of search/ranking.

Input:

- candidate identity;
- kind (`video`/`image`);
- source URL/provider;
- optional source window;
- output/cache root.

Output:

- preview asset path/URL;
- poster path for video;
- dimensions/aspect ratio;
- status/error;
- cache key;
- downloaded bytes attributable to preview generation.

Errors must be per-card. One broken candidate must not fail a chunk or the whole page.

## Error handling

- Broken preview -> card shows an explicit unavailable state and source link/metadata if safe.
- Provider unavailable -> remaining providers/cached candidates continue.
- Fewer than target candidates -> show available strong candidates; never invent placeholders.
- Missing local materialization for selected remote asset -> selection stays visible but export marks it `needs_materialization` until acquisition succeeds.
- No candidates -> phrase card offers `NO_BROLL` and explains `NO_BROLL_QUALITY_FLOOR` or provider failure.
- Selection save failure -> visible non-destructive error; keep client-side state until retry.

## Performance rules

- Lazy-load previews as cards approach viewport.
- No simultaneous autoplay of all video previews.
- Generate low-cost previews before any full-resolution acquisition.
- Cache every stable preview.
- Deduplicate identical provider queries and candidate URLs.
- Full asset download happens only for user-selected assets or already-required finalist verification.
- Existing ASR transcript/chunks must be reused when input hash is unchanged.

## Rights and provenance

Preview availability is not equivalent to publication rights.

Every candidate and selection retains:

- provider/source URL;
- source identifier;
- timestamp/window when relevant;
- rights/license status when known;
- `review_required` when unclear.

The UI should make provenance inspectable without cluttering the main visual shelf.

## Testing

### Unit

- candidate shelf caps at 3 video / 4 image while preserving quality ordering and diversity;
- preview cache key stability;
- video preview window bounding;
- `NO_BROLL` exclusivity;
- multi-select stacked track mapping;
- deterministic selection-plan serialization;
- path/root safety for local preview serving;
- preview failure isolation.

### API/UI behavior

- page returns real image/video preview URLs;
- selection POST persists and reloads;
- multiple selected assets map to V2/V3/V4 in stable order;
- unavailable preview does not break other cards;
- existing `/debug` runner remains functional.

### Smoke

Use the existing KURA run artifacts first; do not repeat ASR/provider/Qwen merely to build the UI.

Initial smoke should hydrate the curation page from existing candidate artifacts and generate only the missing lightweight preview assets needed to render the page.

No Resolve/ComfyUI calls.

## V1 success criteria

V1 is successful when:

1. opening the local curation URL shows transcript phrases in order;
2. each phrase shows up to 3 **real playable video previews** and up to 4 **real image thumbnails** when strong candidates exist;
3. previews load lazily and the page remains responsive;
4. the user can select any number of assets or `NO_BROLL`;
5. refresh preserves saved selections;
6. `selection-plan.json` is generated/updated locally;
7. multiple selections for one phrase receive deterministic stacked track assignments beginning at V2;
8. no GPT/OpenAI model call is required for standard runtime use;
9. source/provenance metadata remains attached;
10. no Resolve mutation occurs.

## Explicitly out of scope for V1

- actual Resolve timeline mutation;
- polished Resolve panel/plugin packaging;
- drag-and-drop reordering beyond stable selection order;
- automatic transition/effect design;
- automatic final editorial approval;
- publication-rights clearance;
- mandatory GPT/OpenAI runtime dependency.
