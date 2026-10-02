# RAMBLA · B-ROLL Resolve Bridge

## Goal

Expose RAMBLA · B-ROLL from DaVinci Resolve, use the active timeline's audio between its In/Out marks as the RAMBLA guide, and return generated editorial material to versioned duplicate timelines without changing the source timeline.

## Resolve entry point

Install a Python Utility script named `RAMBLA · B-ROLL` in Resolve's supported Scripts directory. It opens a themed Fusion UI Manager window showing connection state, Resolve project, active timeline, range and duration. If RAMBLA is unavailable, the script starts the desktop launcher and waits for localhost health. RAMBLA never starts Resolve.

## Capture

The bridge identifies the project and timeline by stable Resolve IDs. It uses audio In/Out marks when present, otherwise video marks, otherwise the full timeline. It renders the mixed timeline range to a temporary WAV, imports that WAV through the existing primary-audio path, and stores the Resolve project ID, source timeline ID/name, fps, absolute start frame, In/Out and capture signature in a bridge manifest.

## Return to Resolve

Resolve exports resolve the recorded source timeline by ID, verify its signature, and duplicate it. Output is always a new `vN` timeline in `TEMP`; media goes into the matching `<project>_media_vN` child bin. Timeline offsets convert RAMBLA-relative transcript times back to absolute Resolve frames. Existing timelines are never deleted or modified.

## Safety and errors

Capture removes only the render job it created and restores the previously active timeline. Failures preserve the source and report actionable text. If Resolve is closed, RAMBLA reports that it is not open. If the source timeline changed, export stops before mutation.

## Branding

The product, launcher-facing UI and Resolve script use `RAMBLA · B-ROLL`. The bridge window follows the existing dark navy, soft-panel and lime-accent visual system.
