# RAMBLA Resolve Confirmed Export

## Objective

Replace immediate Resolve mutations with a visible, confirmable handoff. RAMBLA prepares one local export package containing subtitles, highlighted Fusion Titles and selected B-roll. The Resolve bridge previews the package and changes Resolve only after the editor presses **APPLICA**.

The workflow must remain clear during long operations, preserve the source edit by default, and support an explicit advanced mode that imports into the active timeline.

## User flow

### RAMBLA

The Editing area exposes one primary action:

**INVIA A RESOLVE · SUBS + FRASI + B-ROLL**

Pressing it validates the selections and writes an immutable local handoff package. It does not call Resolve's editing API. RAMBLA then displays a persistent delivery card with:

- project and source timeline;
- duration;
- available and unavailable B-roll counts;
- subtitle count;
- highlighted phrase count;
- status: preparing, sent, waiting for confirmation, applying, completed, discarded, or failed;
- the message **File inviato a Resolve · controlla il bridge** when ready.

RAMBLA polls the package status so the page reflects actions taken in the bridge.

### Resolve bridge

The bridge keeps its existing audio-send controls and adds an **Export ricevuti** section. It periodically checks for the newest pending package associated with the active Resolve project and timeline.

The card shows:

- RAMBLA project;
- source Resolve project and timeline;
- duration;
- selected B-roll count;
- subtitle count;
- highlighted phrase/Fusion Title count;
- unavailable media count.

The editor chooses one destination mode:

1. **CREA NUOVA TIMELINE** — default. Creates a new, otherwise empty, versioned timeline inside `TEMP`.
2. **IMPORTA SULLA TIMELINE ATTIVA** — advanced. Before changing the active timeline, creates a timestamped safety duplicate inside `TEMP`. It then inserts new material on free tracks above existing content, creating tracks when required.

Actions:

- **APPLICA** starts an asynchronous apply job;
- **SCARTA** marks the package discarded without touching Resolve;
- retry is available after a failed apply.

## Timeline layout

The package uses deterministic track roles:

- existing/source picture tracks remain unchanged;
- B-roll coverage clips use dedicated tracks above source picture and receive a purple clip color;
- highlighted keyword Fusion Titles use a dedicated higher track and receive a yellow clip color;
- native subtitles use a subtitle track;
- generic thematic coverage uses a dedicated tail track and receives a beige clip color.

When applying to the active timeline, RAMBLA finds the highest occupied video track, assigns new role tracks above it and creates missing tracks. It must never overwrite an existing clip.

For a new timeline, only the exported RAMBLA elements are created. Timing remains based on the source timeline and Resolve bridge In/Out offset.

## Generic thematic coverage

After the normal visual beats, RAMBLA displays a section named **COPERTURE GENERICHE · TEMA DEL VIDEO**.

The system derives a short topic query from the editorial plan's global topic and the full transcript. It requests 12 landscape Pexels videos using progressively broader topic keywords. Examples:

- Egypt travel story → Egypt, Nile, Egyptian streets, desert, temples;
- sustainability story → renewable energy, nature, recycling, green city.

These cards use the normal preview, source and selection behavior. Generic assets do not belong to a transcript phrase.

Selected generic clips are added after the timed program material, in selection order, with a short configurable default duration. They are placed after a small tail gap and colored beige. They are included in the Resolve package summary.

The search must preserve source attribution and license/source metadata. Missing downloads remain explicitly unavailable and are not silently substituted.

## Package model

Each package is stored under the RAMBLA project in a versioned `resolve-outbox` directory and contains:

- package ID and schema version;
- immutable creation timestamp and source transcript signature;
- linked Resolve project, timeline ID, name, FPS, start frame and duration;
- destination mode chosen later in the bridge;
- normalized subtitle rows;
- normalized Fusion Title rows and selected title template;
- downloaded B-roll rows with source URLs and phrase timing;
- selected generic coverage rows and tail ordering;
- counts and validation warnings;
- status and apply-job progress.

Only one package can be actively applying. New packages do not overwrite previous records.

## Local API

Add endpoints for:

- preparing a package for one RAMBLA project;
- listing/reading the pending package compatible with the active Resolve timeline;
- discarding a package;
- starting an apply job with the chosen destination mode;
- polling apply progress and final result.

Apply is asynchronous. Progress is reported by phase and percentage:

1. validate package;
2. prepare destination/backup;
3. import media;
4. place coverage clips;
5. place highlighted titles;
6. place subtitles;
7. place thematic tail clips;
8. verify timeline and save.

## Safety and failure behavior

- Preparing or discarding a package never changes Resolve.
- New-timeline mode never changes the source timeline.
- Active-timeline mode cannot start until its safety duplicate exists in `TEMP`.
- Package application is idempotent: retrying the same completed package cannot insert clips twice.
- The helper records created timeline IDs and inserted item identifiers.
- A failure preserves the source timeline, keeps the package retryable and surfaces technical details in both RAMBLA and the bridge.
- Resolve being closed, wrong project/timeline, missing title template, unavailable media, track creation failure and save failure receive distinct messages.

## UI progress

Both RAMBLA and the bridge show the same server-side apply state. Progress is based on completed phases rather than a purely animated timer. Controls are disabled only while a package is preparing or applying.

The bridge must continue processing UI events while polling, so Resolve does not appear frozen.

## Compatibility

Existing direct XML, DRT and DRA exports remain available as secondary actions. Existing audio capture and Detect Videos behavior remain unchanged. Old direct timeline endpoints remain callable for compatibility but the main UI uses the confirmed handoff.

## Verification

Automated tests cover:

- package validation and versioning;
- counts and summaries;
- pending/list/discard/apply state transitions;
- idempotent apply;
- new-timeline and active-timeline destination planning;
- mandatory backup before active-timeline mutation;
- role-track allocation and clip colors;
- generic Pexels query broadening and exactly 12 displayed candidates when available;
- thematic-tail ordering;
- progress monotonicity and error propagation;
- source timeline unchanged in default mode.

Manual Resolve verification uses a disposable RAMBLA package and confirms both modes without deleting or renaming existing timelines.
