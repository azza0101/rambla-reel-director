# Resolve Highlighted Titles + Native Subtitles — Design

## Goal

Extend RAMBLA's transcript workflow so editors can create and export a Resolve timeline containing both styled Fusion Titles for highlighted words and native Resolve Subtitle clips for the remaining spoken words. Preserve the existing complete SRT export unchanged.

## Product rules

RAMBLA exposes two compact disclosure groups below the transcript selection surface.

### Animation

- **Copy animation JSON**
- **Export animation JSON**

### Editing

- **Export complete subtitles**
- **Create selected-word timeline**
- **Create selected-word + subtitle timeline**
- **Export selected-word + subtitle timeline (.drt)**

The selected Resolve Fusion Title panel remains inside Editing.

## Subtitle semantics

The existing SRT export remains complete. It includes every spoken word, including words selected as highlighted Text+.

Only the combined Resolve timeline applies exclusion:

- highlighted words become Fusion Title clips using the selected `.drfx` template;
- those word indices are removed from native Subtitle captions;
- all other words remain in native Subtitle clips;
- removing a highlighted word creates a hard caption boundary, so words on opposite sides are never joined across the visual title;
- remaining words are grouped in chronological semantic units of no more than three words;
- punctuation stays attached to its spoken word;
- empty caption groups are omitted;
- original word start/end times remain authoritative.

The title-only timeline behavior remains available and unchanged.

## Resolve timeline variants

### Title-only

This is the existing path. RAMBLA duplicates the open source timeline, clears the duplicate, inserts the selected Fusion Title at each highlighted interval, writes its exposed Text+ control before trimming, verifies the result, and saves the Resolve project.

### Combined titles + native subtitles

RAMBLA duplicates the open source timeline and clears the duplicate. It inserts and verifies the highlighted Fusion Titles, then adds a native Subtitle track populated from a temporary filtered SRT. The source timeline signature must remain unchanged.

Resolve 21 exposes subtitle tracks but not a direct `InsertSubtitleClip` scripting method. Implementation therefore begins with a rollback-safe compatibility probe:

1. create a temporary SRT containing known captions;
2. attempt official `MediaPool.ImportMedia` plus supported timeline placement into a subtitle track;
3. confirm that `GetItemListInTrack("subtitle", 1)` returns native Subtitle items with the expected ranges and text;
4. delete the temporary timeline and imported probe media.

If the installed Resolve build does not support SRT placement through those official calls, use an FCPXML caption timeline imported through `MediaPool.ImportTimelineFromFile`, then copy/compose the verified title clips into that generated timeline. Mouse, keyboard and menu automation are prohibited.

If neither official route produces native Subtitle items, stop with a concrete compatibility error. Do not replace them silently with Text+ clips.

## DRT export

The **Export selected-word + subtitle timeline** operation first creates and verifies the same combined timeline inside Resolve. It then calls the official timeline export API with `resolve.EXPORT_DRT` and writes the result into a RAMBLA-managed export directory.

The HTTP response streams the `.drt` to the browser with a sanitized filename. The generated Resolve timeline remains in the project and is saved. A failed export keeps the verified timeline, reports the export error, and does not return a partial file.

## Planning data

Add a combined Resolve manifest derived from the authoritative transcript document and phrase-intent state:

- `titles[]`: existing highlighted groups, maximum three consecutive words;
- `subtitles[]`: filtered non-highlighted groups, maximum three words;
- project ID, transcript signature and source duration;
- exact seconds and frame ranges;
- selected Resolve title template name.

The builder is pure and domain-general. It never reads provider results, visual plans or KURA-specific transcript content.

## API

Keep existing routes and add:

- `GET /api/curation/projects/{project_id}/exports/captions.srt`
  - existing complete SRT; behavior unchanged;
- `POST /api/curation/projects/{project_id}/resolve/textplus-timeline`
  - existing title-only timeline;
- `POST /api/curation/projects/{project_id}/resolve/combined-timeline`
  - create and save titles plus native Subtitle clips;
- `POST /api/curation/projects/{project_id}/resolve/combined-timeline.drt`
  - create, verify and export the combined timeline, then stream the DRT.

Responses distinguish title-template errors, subtitle compatibility errors, subtitle import failures, verification failures, Resolve save failures and DRT export failures.

## Verification and rollback

Before success RAMBLA verifies:

- generated timeline name and frame rate;
- every Fusion Title name, exposed text and exact frame range;
- every native Subtitle clip text and exact frame range;
- no highlighted word appears in the Subtitle track;
- complete SRT still contains highlighted words;
- source timeline signature is unchanged;
- Resolve project save succeeds;
- DRT exists, is non-empty and was exported from the verified combined timeline.

Timeline construction failures delete the incomplete generated timeline, restore the source timeline and save the rollback. DRT export failures do not delete a successfully verified combined timeline.

## UI behavior

Animation and Editing use native disclosure controls so the workspace stays compact. Editing displays the selected Fusion Title panel followed by the four actions. Buttons show progress and remain individually guarded:

- complete SRT requires analyzed transcript;
- title-only creation requires highlighted words and a ready Resolve title;
- combined creation/export requires highlighted words, a ready title and Resolve availability;
- JSON exports remain independent from Resolve.

Successful combined creation reports title count, subtitle count and timeline name. Successful DRT export downloads the file and reports its timeline name.

## Tests and acceptance

Automated tests cover:

- complete SRT retains highlighted words;
- combined subtitle grouping excludes highlighted indices only;
- highlighted gaps split captions;
- maximum three-word captions and punctuation preservation;
- empty/all-highlighted transcript behavior;
- combined manifest timing and frame conversion;
- API routing and error mapping;
- disclosure UI, button labels, progress and download behavior;
- title-only regression;
- rollback and Resolve project saving;
- DRT export validation and streaming.

Real Resolve acceptance uses the current KURA project and `KURA_paper_title_v8`:

1. generate a combined timeline;
2. inspect native Subtitle track items and Fusion Title clips through a fresh Resolve scripting process;
3. prove highlighted words appear only in Fusion Titles while the remaining words appear in native Subtitle clips;
4. export and re-import the DRT into a temporary project/timeline context when safe, or at minimum verify successful official DRT export and non-empty output;
5. leave the accepted combined timeline open and preserve the source.

## Out of scope

- subtitle styling beyond Resolve's native track defaults;
- burning subtitles into rendered video;
- replacing native subtitles with Text+;
- automatically editing the user's source timeline;
- importing DRT into a different Resolve database automatically;
- changing animation JSON format.
