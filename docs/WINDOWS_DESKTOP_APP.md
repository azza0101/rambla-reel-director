# RAMBLA Windows Desktop App

The Windows desktop launcher keeps the RAMBLA product code unchanged: FastAPI
serves the same `/curation` application, while a hidden `pythonw.exe` process
owns the local server. Product features can therefore continue to be developed
and tested in the normal repository workflow.

## Runtime

The desktop launcher selects `desktop_api` mode:

- Director and transcription use configured cloud APIs;
- retrieval ranking uses provider metadata and does not load local Qwen/GPU;
- local file selection remains available;
- local TikTok and Instagram browser sessions remain available;
- projects and browser profiles live under the sibling `rambla-data` folder.

The launcher hashes its own relevant source files into a build token. It only
reuses a running RAMBLA server when `/health` reports the same token. This stops
an old server from silently serving an outdated UI after an update.

## User commands

- `RAMBLA_REEL_DIRECTOR.vbs`: start or reopen RAMBLA without a console window.
- `RAMBLA_RESTART.vbs`: stop the recorded matching build and start it again.
- `RAMBLA_EXIT.vbs`: stop the recorded matching build.
- `INSTALL_RAMBLA_DESKTOP.ps1`: create a desktop shortcut to the hidden launcher.

The current development package reuses the approved project-local Python
runtime in `../editorial-intelligence-worktree/.venv`. A later distributable
ZIP/installer can place an equivalent runtime inside the application folder
without changing the FastAPI product or feature-development workflow.

## Updating

Develop and publish features normally on `feat/api-first-text-first-v1`. After
updating the desktop checkout, use `RAMBLA_RESTART.vbs`. The changed source hash
produces a new build token, so the launcher will not attach to the prior build.

Secrets remain local and untracked. Never commit `.env.local`, API keys, browser
profiles, project media, caches, logs or `rambla-data`.

## Resolve Fusion Title templates

The highlighted-word workspace includes a local Resolve title library. New and
existing projects select the bundled `KURA_paper_title_v8.drfx` by default.
Choose another installed title from the selector or drag a compatible `.drfx`
package into the drop zone. RAMBLA validates the archive before storing it and
never silently substitutes a different title.

Use **INSTALLA IN RESOLVE** when a selected package is missing from the current
Windows user's Resolve templates. If RAMBLA reports **Riavvia Resolve**, close
and reopen Resolve before creating the title timeline. The JSON Text+ exports
remain available even when Resolve or the selected title is unavailable.

The generated timeline contains only Edit-page Fusion Title clips at the exact
source timecodes. RAMBLA writes into the title's exposed `Template` Text+ control
when present, preserves the source timeline, and removes an incomplete generated
timeline if insertion or verification fails.

## Animation and Editing exports

Transcript exports are grouped under **ANIMATION** and **EDITING**. The complete
subtitle export remains a normal SRT and always includes highlighted words.
**Crea timeline parole + subs** creates one Resolve timeline where highlighted
words use the selected Fusion Title and every remaining caption is a native
Subtitle clip, grouped into at most three words. Highlighted words create hard
gaps in this combined Subtitle track.

**Esporta timeline parole + subs · DRT** creates the same verified timeline and
downloads a native Resolve `.drt`. Resolve cannot reliably export a DRT directly
to a mapped drive such as `Z:`. RAMBLA therefore exports to a local temporary
file through the official Resolve API, verifies it is non-empty, and then copies
it to the project/download destination.
