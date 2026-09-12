# Content Sprint live proof (bridge-only)

The 2026-09-12 live proof used the existing in-Resolve bridge on `127.0.0.1`.
It did not import `DaVinciResolveScript`, load `fusionscript.dll`, use GUI
automation, or touch ComfyUI. All runtime audio, model files, transcript,
client media, generated overlays, plans, reports, and DRP backups remain outside
the tracked repository under the local `work/content-sprint` area.

## Observed content and plan

- The `test-mcp` source timeline `REEL MASTER` has one talking-head V1/A1 clip,
  25 fps, 2135 timeline frames. The media source contains 85.433 seconds of audio.
- An isolated local `faster-whisper` 1.2.1 runtime (small model, CPU/int8)
  produced 21 timestamped Italian segments. The raw ASR transcript needs human
  correction before publication; it is not committed.
- Five semantic beats were derived from actual speech. The first local B-roll
  candidate was a workflow-node screenshot from the same local source project
  folder, matching the passage about workflows and nodes.
- The first plan placed that candidate on V2 at absolute frames
  `[91360, 91473)` (54.4–58.9 seconds relative to timeline start).

## Resolve capability finding and exact-range workaround

Resolve Studio 21.0.0.47 ignored `endFrame` for a directly imported still in
`MediaPool.AppendToTimeline`:

| Disposable timeline | Requested still duration | Read-back duration |
| --- | ---: | ---: |
| `REEL_AI_v04` | 113 frames | 125 frames |
| `REEL_AI_v05` | 50 frames | 125 frames |

Both are preserved and were not retried. The same image was therefore rendered
locally into a 25 fps, 113-frame video before import. A new persisted Edit Plan
targeted the collision-safe `REEL_AI_v06`; its V2 read-back was exactly
`[91360, 91473)`. A draft SRT containing all 21 ASR segments was generated
locally. One transparent caption overlay derived from the “workflow nodi”
passage was rendered as a 113-frame alpha-capable video and placed on V3 of
`REEL_AI_v06`, also read back at `[91360, 91473)`. The SRT is a draft, not a
verified subtitle track.

The `REEL MASTER` video/audio IDs, ranges, and V1 transform were unchanged
before and after each operation. `ProjectManager.SaveProject()` returned `True`
after a local DRP backup was exported and again after caption Apply. The API
Media Pool and exported DRP contain all generated timelines in the `Master`
bin. A prior visible Edit-page snapshot showed only the original timeline,
however; GUI visibility after saving has **not** been verified. The bridge is a
Resolve-launched child process, so API state and GUI state must not be assumed
to match without an independent check. No GUI automation is permitted for this
project.

## Code boundaries

- `content_live.py` validates source identity, hashes the source snapshot and
  local asset, persists a plan before mutation, uses a new duplicate, verifies
  exact frame read-back, and refuses Apply retries.
- `caption_live.py` targets only the verified generated duplicate, persists its
  own plan, checks the SRT/overlay hashes and alpha-capable frame count, and
  verifies B-roll, caption, and source after insertion.
- Successful Applies call `SaveProject()` and verify the source again; save
  failure is ambiguous, never silently treated as success.

Current limitations: the live helpers are an intentionally narrow proof for
this fixture, not a general multi-client API. Neither the private transcript
nor media assets are stored in Git. GUI visibility, render composite, and ASR
word accuracy remain separate verification gates.
