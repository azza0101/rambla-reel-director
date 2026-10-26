# Premontato diagnostic reports

## Intent

When Premontato fails, let the user send enough technical context for RAMBLA to investigate without asking them to locate logs manually. Upload is user-triggered and requires reviewing the report and confirming the send.

## Approaches

- Automatically create a report on every error: fastest, but sends data without case-by-case review.
- Let the user preview and confirm a filtered report, then create a private GitHub issue: chosen because the user requested confirmation and GitHub issues are immediately readable by maintainers.
- Save a local diagnostic bundle for manual sharing: avoids authenticated upload, but adds steps and does not meet the request for quick access.

## Behavior and constraints

- Record a bounded local log of technical events and errors only. Do not log script text, transcript text, media paths/names, video/audio, credentials, or tokens.
- Add a **Invia debug** action that summarizes the report, permits review, and requires a separate explicit confirmation before creating an issue in `azza0101/rambla-reel-director`.
- Use the machine's existing authenticated GitHub CLI (`gh`) at runtime; never embed, save, print, or pass a token in command arguments. If `gh` is unavailable or unauthenticated, show a clear recovery message and retain the log locally.
- Scrub usernames, absolute paths, credential/token-like strings, and environment details before preview and upload. Include app/OS versions, safe error summaries/stacks, and recent technical event names.
- Create an issue in the private repository with a fixed Premontato diagnostic label and timestamp/version in its title. Show the resulting issue link.
- No automatic upload, media/script attachments, or changes to RMBL/Auto-Cut. Keep all changes within `premontato-workflow/`.

## Validation

Unit tests cover redaction, bounded log collection, preview payload exclusions, and GitHub CLI invocation without token leakage. A live upload is only tested when the user confirms sending a real report; ordinary implementation verification uses a mocked CLI.
