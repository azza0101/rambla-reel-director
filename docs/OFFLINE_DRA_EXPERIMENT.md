# Offline DRA export: validation and limitations

The experimental exporter writes a Resolve project and DRA ZIP without calling Resolve. It is currently **not release-ready**: the product must not promise faithful stereo output, HEVC media, or the selected KURA Fusion preset until these are verified.

An isolated Resolve Studio 21.1 test restored an archive created offline after moving the archive and temporarily hiding both original media paths. A video guide, video coverage, disabled still, native subtitle and individual Text+ title imported on their intended tracks and timings. Resolve reported both copied media online; the still remained disabled. A separate title/subtitle-only project also restored. An accented filename restored and relinked correctly.

The `media.dat` member in `project.drp` is necessary for Resolve's archive restore to relink the media inside `MediaFiles`. This was tested with one and two distinct source files. Same-name collisions are rejected rather than risking incorrect relinking.

The current implementation supports only verified H.264 video and still images; it rejects HEVC, unverified codecs, stereo or multichannel source audio, duplicate media filenames, and Resolve-sourced multi-clip CUTs. Titles are editable default Text+, not the requested KURA preset. Audio rendering did not complete in the local test environment; do not claim that sound has been verified. A failed archive attempt caused Resolve to exit; the test project was reopened afterwards.

Third-party origins and licenses are documented in `backend/vendor/THIRD_PARTY_OFFLINE_ARCHIVE.md`. No original user media is included in this code.
