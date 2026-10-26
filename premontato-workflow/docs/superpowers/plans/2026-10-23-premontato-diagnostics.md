# Premontato Diagnostic Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users preview and confirm a sanitized technical diagnostic before creating a private GitHub issue for Premontato support.

**Architecture:** Existing `plugin/updater.js` gains diagnostics and GitHub issue helpers so the already-installed 0.3.0 update allowlist can accept the feature in one update. The module writes a bounded local technical log and composes a redacted support report. The Electron main process invokes the user's authenticated `gh` CLI only after the renderer displays the report and the user confirms; no token enters installer code, command arguments, logs, or issue text.

**Tech Stack:** Electron main/preload/renderer, Node.js built-ins, GitHub CLI, Node test runner, PowerShell packaging scripts.

**Spec:** `docs/superpowers/specs/2026-10-23-premontato-diagnostics-design.md`

## Global Constraints

- Keep all edits within `premontato-workflow/`.
- Do not upload automatically; require preview and a distinct user confirmation.
- Never include script/transcript content, media, media names/paths, credentials, tokens, or personal absolute paths.
- Use the authenticated local `gh` executable; never embed or persist its token.
- Create issues only in `azza0101/rambla-reel-director`, a private repository.

## Review Focus

- Unexpected user paths or names in thrown errors: add redaction tests in Task 1.
- Huge or malformed log entries: add bounded collection tests in Task 1.
- Missing, unauthenticated, or failing `gh`: add mocked invocation/error tests in Task 2.
- Renderer tries to submit an unpreviewed or altered payload: main process rebuilds and confirms the report in Task 2.
- Packaged update omits diagnostics files or changes the bridge SDK: package-contract checks in Task 3.

---

### Task 1: Bounded diagnostic log and safe report

**Files:**
- Modify: `plugin/updater.js`
- Create: `tests/unit/diagnostics.test.cjs`
- Modify: `plugin/main.js`

**Interfaces:**
- `createDiagnostics({ logPath, appVersion, platform, release })` returns `{ record(event, details), preview(), clear() }`.
- `preview()` returns `{ reportId, title, body, createdAt }` containing at most the latest 200 sanitized technical events and basic version/platform fields.
- Record only allowlisted event names and safe error summaries/stacks; redact absolute paths, usernames, tokens, and credential-like strings before writing or previewing.

- [ ] **Step 1: Write failing tests** for path/token redaction, exclusion of arbitrary event detail/script text, truncation to 200 events and 64 KiB, and clear behavior.
- [ ] **Step 2: Run** `node --test tests/unit/diagnostics.test.cjs`; expect failures because the module does not exist.
- [ ] **Step 3: Implement** the bounded file-backed diagnostics module using Node built-ins only.
- [ ] **Step 4: Wire** startup and caught operation failures in `plugin/main.js` to record allowlisted event names without media/script data.
- [ ] **Step 5: Run** `node --test tests/unit/diagnostics.test.cjs`; expect all diagnostics tests to pass.

### Task 2: Preview, confirmation, and private issue upload

**Files:**
- Modify: `plugin/main.js`
- Modify: `plugin/preload.js`
- Modify: `plugin/index.html`
- Modify: `plugin/renderer.js`
- Modify: `plugin/style.css`
- Create: `tests/unit/support-report.test.cjs`

**Interfaces:**
- `prepareSupportReport()` returns a fresh diagnostics preview and checks that `gh` exists and is authenticated, without creating a remote issue.
- `submitSupportReport(reportId, confirm)` rejects unless `confirm === true` and `reportId` matches the latest preview; it creates `gh issue create --repo azza0101/rambla-reel-director --title ... --body-file ... --label bug` with a temporary body file, then deletes the file.
- Renderer displays the report body for review, requires a separate checkbox/button confirmation, and shows the resulting issue URL.

- [ ] **Step 1: Write failing mocked-CLI tests** for preview-only behavior, explicit confirmation, report ID freshness, safe `gh` arguments/body file, unsupported CLI, unauthenticated CLI, command failure, and temporary file cleanup.
- [ ] **Step 2: Run** `node --test tests/unit/support-report.test.cjs`; expect failures before implementation.
- [ ] **Step 3: Implement** main-process commands and mocked process adapter; do not accept report body text from renderer, only report ID and confirmation boolean.
- [ ] **Step 4: Add** renderer preview/confirmation flow and result/error messages; all IPC remains behind `assertTrusted`.
- [ ] **Step 5: Run** `node --test tests/unit/support-report.test.cjs tests/unit/ipc-security.test.cjs`; expect all tests to pass without a live GitHub issue.

### Task 3: Package, docs, and final verification

**Files:**
- Modify: installer and update allowlists only if needed; 0.3.0 must accept every new file
- Modify: `tests/unit/test_package_contract.py`
- Modify: `README.md`
- Modify: `USAGE.md`
- Modify: `VALIDATION.md`
- Modify: plugin version metadata as required for a Premontato update release.

- [ ] **Step 1: Write failing package-contract tests** that require the diagnostics module and preserve `WorkflowIntegration.node` exclusion and no embedded credentials.
- [ ] **Step 2: Run** `python -m pytest tests/unit/test_package_contract.py -q`; confirm the new diagnostics asset requirement fails before packaging edits.
- [ ] **Step 3: Include** diagnostics module in the safe update allowlist and document the preview/confirm flow and local `gh` prerequisite.
- [ ] **Step 4: Run** `node --test tests/unit/*.test.cjs` and `python -m pytest tests/unit -q`; expect all tests to pass.
- [ ] **Step 5: Build and inspect** the update ZIP, verify no token/SDK/media/test report is packaged, run the update script in validation-only mode, and publish the versioned Premontato release without merging the PR.

## Execution ruling

- Ruling: Place diagnostics helpers in the already-allowed `plugin/updater.js` instead of separate modules — the installed 0.3.0 update script rejects files outside its fixed allowlist — cost if wrong: the updater module has more responsibilities.
- Ruling: Use the existing `bug` GitHub label instead of creating `premontato-debug` — repository label inspection showed only `bug` and generic labels — cost if wrong: support issues are less distinct in the repository list.
- Ruling: Publish the first bridge release as stable with `make_latest=false` — installed 0.3.0 ignores prereleases — cost if wrong: new code can’t be discovered by the current installation or may replace the repository’s latest release.
