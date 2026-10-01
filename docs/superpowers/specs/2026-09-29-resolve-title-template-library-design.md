# Resolve Title Template Library — Design

## Goal

Make RAMBLA's highlighted-word timeline generation portable and independent of one hard-coded Resolve installation. RAMBLA ships with `KURA_paper_title_v8.drfx` as the default, lets the user upload other `.drfx` Fusion Title packages, stores the selected template, installs missing packages into the current Windows user's Resolve template directory, and creates exact-time Edit-page title clips with the chosen style.

## User experience

The highlighted-word area gains a compact **Resolve title template** panel:

- a select control showing the active template;
- status: **Ready**, **Not installed**, **Resolve restart required**, or **Invalid**;
- a drag-and-drop/file-picker target accepting `.drfx` files;
- an **Install in Resolve** action when required;
- the existing **Create timeline in Resolve** action.

`KURA_paper_title_v8` is preselected for new and existing projects. Uploading a valid package adds it to the library and selects it. Selection is persisted per RAMBLA project. The UI never silently substitutes another style. If Resolve cannot see the selected title, timeline generation stops with an actionable message.

## Bundled default

The supplied `KURA_paper_title_v8.drfx` is copied into a repository-owned bundled-assets directory. RAMBLA treats it like every other library item, except that it cannot be deleted and is the default selection.

The package currently contains:

- `Edit/Titles/KURA_paper_title_v8/KURA_paper_title_v8.setting`;
- its thumbnail;
- bundled paper texture and animation image sequences.

Its Resolve insertion name is derived from the `.setting` filename: `KURA_paper_title_v8`.

## Package validation and metadata

RAMBLA reads `.drfx` as ZIP without extracting during validation. It rejects:

- non-ZIP or corrupt files;
- packages larger than the configured upload limit;
- absolute paths, drive-qualified paths, or `..` traversal entries;
- packages without exactly one usable `Edit/Titles/**/*.setting` title entry;
- duplicate library IDs with conflicting content.

For a valid package RAMBLA records:

- stable ID based on SHA-256;
- display name and Resolve insertion name;
- original filename;
- byte size and digest;
- relative `.setting` path;
- whether the package is bundled or uploaded;
- installation state.

Uploaded packages are copied into an application-managed library below the RAMBLA project-data root. Metadata is regenerated from the package when read so it cannot become authoritative over the file itself.

## Installation

On Windows, installation copies the selected `.drfx` atomically into:

`%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Templates`

The destination filename is derived from validated metadata. RAMBLA compares hashes before copying:

- matching file: **Ready**;
- missing file: **Not installed**;
- different file with the same name: preserve it and use a digest-suffixed destination;
- newly copied or replaced library entry: **Resolve restart required** until the title can actually be inserted.

RAMBLA does not claim installation succeeded merely because the file exists. The final readiness check is a non-destructive Resolve insertion probe or an actual timeline-generation attempt. Installation never changes global Python, PATH, CUDA, or Resolve system configuration.

## Template compatibility

After Resolve inserts the title, RAMBLA inspects its Fusion composition. It chooses the editable text control using this order:

1. exposed Text+ tool named `Template`;
2. exactly one Text+ tool in the composition;
3. exactly one Text+ tool whose `StyledText` is writable and not expression-driven.

If selection remains ambiguous, generation rolls back and reports that the template needs a declared text control. The first version does not provide a node picker; this avoids silently editing the wrong internal node.

RAMBLA writes each selected word group before later boundary insertions trim the title, preserving the existing Resolve 21 workaround. It verifies text, title name, exact frame ranges, source signature, and final clip count. Any failure deletes the generated timeline and restores the source timeline.

## Persistence

The project stores only the selected template library ID. The library is shared by all local RAMBLA projects. Existing projects without a selection resolve to the bundled `KURA_paper_title_v8` ID.

Project autosave and reopening preserve the selection. A missing library file produces **Invalid / file missing**, never a fallback.

## API

Add project-scoped and library endpoints:

- `GET /api/curation/resolve-title-templates`
  - list validated templates and installation/readiness state;
- `POST /api/curation/resolve-title-templates`
  - bounded binary upload of one `.drfx` package with its filename in `X-Rambla-Filename`; this avoids adding a multipart runtime dependency;
- `POST /api/curation/resolve-title-templates/{template_id}/install`
  - install the package for the current Windows user;
- `PUT /api/curation/projects/{project_id}/resolve-title-template`
  - select a library item for the project;
- existing `POST /projects/{project_id}/resolve/textplus-timeline`
  - resolve the selected template and pass its insertion name to the isolated Resolve helper.

API responses expose no arbitrary filesystem paths. Errors distinguish invalid package, not installed, restart required, Resolve unavailable, ambiguous text control, and generation failure.

## UI behavior

The template panel loads with the transcript intent workspace. Dragging a file highlights the drop target; upload progress and validation result appear inline. A successful upload selects the new template. Installing updates the status but does not automatically restart Resolve. When a restart is required, the create button stays disabled and the UI explains the next action.

The existing JSON copy/export actions remain available and independent of Resolve/template readiness.

## Tests and acceptance

Automated coverage includes:

- valid KURA package inspection;
- malformed ZIP, traversal and missing-title rejection;
- stable IDs and collision-safe installation;
- default and per-project selection persistence;
- API upload/list/select/install behavior;
- UI drop zone, selector and status behavior;
- custom-title editable-node selection;
- rollback when a template is unavailable or ambiguous;
- preservation of existing transcript, export and timeline behavior.

Real acceptance uses Resolve with `KURA_paper_title_v8`:

1. generate a separate timeline from the current highlighted words;
2. confirm every Edit clip is named `KURA_paper_title_v8`;
3. confirm the exposed text control contains the intended words;
4. confirm exact frame ranges and unchanged source timeline;
5. verify missing-template messaging using a deliberately unknown insertion name without altering the installed preset.

## Out of scope

- editing the internal Fusion graph;
- choosing among multiple ambiguous Text+ nodes;
- modifying or uninstalling existing user presets;
- automatically closing or restarting Resolve;
- cloud-side Resolve integration.
