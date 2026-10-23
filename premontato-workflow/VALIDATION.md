# Validation record — 2026-10-23

## Built and checked locally

- Self-contained Windows x64 installer generated at `dist/Install-Premontato.exe` (137,782,694 bytes) from the runtime and worker payload. The installer file was built but not run.
- Python 3.13.17 embed runtime launched successfully; imported OpenCV 5.0.0, NumPy 2.5.4, and pypdf 6.10.0.
- Local JSON-lines worker `ping` returned `status: ok` under the same isolated interpreter.
- `node --test`: 17 passed.
- `.test-venv` Python 3.10 test environment: `pytest tests/unit -q`: 18 passed, including package contract.
- `node -c` on plugin main/session and Node JSON parsing of package metadata passed.
- SDK discovery found the local Resolve 21.1 sample `WorkflowIntegration.node`. It is not in the project payload or installer.

## Not yet host-tested

- The installer was not executed, and the plugin was not installed or loaded in Resolve. No UAC prompt was accepted.
- No API calls were run against the open Resolve project, and no timeline was created. The open project was left unchanged.
- A user should test the installer and generated review timeline in a disposable project before using the workflow on production footage.
