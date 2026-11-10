# Offline DRA export: validation and limitations

The experimental exporter writes a Resolve project and DRA ZIP without calling Resolve. It is currently **not release-ready**: faithful stereo output, HEVC media, and pixel-level KURA rendering remain unverified.

An isolated Resolve Studio 21.1 test restored an archive created offline after moving the archive and temporarily hiding both original media paths. A video guide, video coverage, disabled still, native subtitle and individual Text+ title imported on their intended tracks and timings. Resolve reported both copied media online; the still remained disabled. A separate title/subtitle-only project also restored. An accented filename restored and relinked correctly.

The `media.dat` member in `project.drp` is necessary for Resolve's archive restore to relink the media inside `MediaFiles`. This was tested with one and two distinct source files. Same-name collisions are rejected rather than risking incorrect relinking.

The current implementation supports only verified H.264 video and still images; it rejects HEVC, unverified codecs, stereo or multichannel source audio, duplicate media filenames, and Resolve-sourced multi-clip CUTs. Titles use a captured KURA v9 Fusion composition. A real Resolve 21.1 restore confirmed its 68 nodes, two-line editable text and timing. Visual rendering and installation on a second computer remain unverified. The ZIP includes the matching DRFX and installers for Windows and macOS; if the matching package and a title are already installed they leave the existing title untouched. On first install Resolve must be restarted. Windows installation, repeated installation and conflict handling were tested in an isolated directory; the macOS installer has not been tested on a Mac. Montserrat must be installed separately. Audio rendering did not complete in the local test environment; do not claim that sound has been verified. A failed archive attempt caused Resolve to exit; the test project was reopened afterwards.

Third-party origins and licenses are documented in `backend/vendor/THIRD_PARTY_OFFLINE_ARCHIVE.md`. No original user media is included in this code.
