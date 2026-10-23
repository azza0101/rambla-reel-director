# Validation record — 2026-10-23

## OpenCV runtime correction

- Reproduced the reported failure in the installed Python 3.13 runtime: OpenCV 5.0.0 imported, but `cv2.CascadeClassifier` was absent.
- Pinned the Windows-compatible OpenCV wheel to `opencv-python-headless==4.11.0.86` and recorded its SHA-256 in `runtime/requirements.lock`.
- Rebuilt the isolated Python 3.13 runtime; confirmed `cv2.CascadeClassifier` exists and `haarcascade_frontalface_default.xml` loads (`empty() == False`).
- Ran `analyze_video` against synthetic frames through the real OpenCV 4.11 classifier: one segment returned without error. This validates runtime plumbing, not visual accuracy on the user's footage.
- `node --test`: 24 passed; Python unit tests: 19 passed.
- Installer rebuilt with the updater (65,690,112 bytes; SHA-256 `AEA435D51F4B80CAB63D86B5B59B13DF108B3E2F3F7125059A583AF3FF8B3A3F`). The v0.3.0 update ZIP is 65,681,439 bytes; SHA-256 `C5907A7F887CA8E2547826E5A6DEA74ABCD0BC8CDE9DF432924F61B7F0B7AD6E`.
- Implemented the explicit GitHub **Aggiorna** action: it reads the existing Auto-Cut DPAPI credential in memory, checks a versioned private release, verifies the update ZIP hash, then invokes an elevated PowerShell installer with backup and rollback. The updater payload excludes the Resolve `.node` SDK binary and the token.
- Added private release packaging for tags `premontato-vX.Y.Z`; release workflow permissions are read-only for build/test and contents-write only for the tag-gated publishing job.
- New update flow tests: semantic versions, manifest/tag validation, DPAPI path lookup, credential-free package contract, private release discovery, verified download and worker shutdown.
- Update ZIP passed `update.ps1 -ValidateOnly` against a disposable plugin directory (1,166 files); no actual plugin files were replaced. Archive audit found no SDK module, user PDF/media, or credential files.
- Final local installer and release ZIP are built but have not been run/installed; no update has been applied to the open Resolve session.

## Built and checked locally

- Self-contained Windows x64 installer generated at `dist/Install-Premontato.exe` from the runtime and worker payload. The installer file was built but not run.
- Python 3.13.17 embed runtime launched successfully; imported OpenCV 4.11.0, NumPy 2.5.4, and pypdf 6.10.0.
- Local JSON-lines worker `ping` returned `status: ok` under the same isolated interpreter.
- `node --test`: 24 passed.
- `.test-venv` Python 3.10 test environment: `pytest tests/unit -q`: 19 passed, including package contract.
- `node -c` on plugin main/session and Node JSON parsing of package metadata passed.
- SDK discovery found the local Resolve 21.1 sample `WorkflowIntegration.node`. It is not in the project payload or installer.
- Installer PowerShell smoke test installed the staged files into a disposable workspace directory using a fake SDK marker; runtime and worker paths were verified, then the test tree was removed.
- Latest EXE payload inspection found the updated OpenCV module, Python runtime, notices and worker; no Resolve SDK module, user PDF/media or credential-like paths were present.

## Not yet host-tested

- The EXE was built but not executed; its PowerShell staging was tested separately. The plugin was not installed or loaded in Resolve. No UAC prompt was accepted.
- No API calls were run against the open Resolve project, and no timeline was created. The open project was left unchanged.
- A user should test the installer and generated review timeline in a disposable project before using the workflow on production footage.
