# Windows installation and update plan

Goal: one installer for standalone and bridge with private GitHub updates.
Architecture: keep existing launcher/runtime; separate persistent rambla-data from code. Download releases through the user's GitHub CLI authentication, verify digest and archive, ask before update, preserve configuration and code backup. Never stop Resolve. Refuse development checkout updates.

1. Publish current work: bee2908 (done).
2. Implement common updater with checksum/path regression tests and SEARCH UPDATE controls.
3. Repair installer dependency checks; bundle wheels and media binaries; create both launchers.
4. Test fresh installation and update with persistent-data sentinels; build EXE; publish versioned assets.

No credentials, media, browser profiles or experimental gateway databases in distribution. First Python installation requires internet; Resolve is installed separately. Test only isolated install copies.
