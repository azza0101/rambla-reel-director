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

## Diagnostic report feature — Premontato 0.3.1

- Added bounded local diagnostics (latest 200 events, maximum 64 KiB). Reports include only app/OS versions, event names, error classes and redacted stack frames; exception messages, script/transcript text, media names/paths, and media files are excluded.
- Added an **Invia debug** preview and separate confirmation step. The main process retains the preview payload, rejects stale report IDs or missing confirmation, checks `gh auth status`, then creates a private repository issue with the existing `bug` label. GitHub CLI output and credentials are never shown in the UI; the temporary issue body is removed after use.
- No real issue was submitted during tests. Node tests mock the CLI and verify no token appears in arguments, missing authentication behavior, preview binding, URL validation, and temporary-file cleanup.
- The feature is embedded in the existing `updater.js` file so the installed 0.3.0 updater's fixed allowlist can install it. `WorkflowIntegration.node` remains excluded from the update archive.
- `node --test tests/unit/*.test.cjs`: 32 passed. `pytest tests/unit -q`: 22 passed. JavaScript syntax checks passed. The 0.3.1 ZIP passed `update.ps1 -ValidateOnly` with 1,166 files. Archive SHA-256: `0a1ff53d4e7e2c63fef216b4a194616cfe66e842504b570882b82aadf6c6fd72` (65,685,255 bytes).
- The updater is tested against dedicated `premontato-v0.3.1` releases while ignoring Auto-Cut release tags. The 0.3.1 release is stable so installed 0.3.0 can discover it, but GitHub confirms `v0120` remains the repository latest. The Actions upload step checks the repository's current latest tag before uploading.
- Resolve was not launched for a UI test, and no live issue was created. The CLI authentication check was verified locally without displaying its credentials.

## 0.9.0 — 24 ottobre 2026

64 test Node, 49 test Python e test browser con worker reale: caricamento note .md, marcatori narrativi, salvataggio note e bozze, protezione delle correzioni non applicate, revisione di 66 still, nessun errore JS a 1100/680 px. Test di selezione sintetici verificano stretta-stretta-larga, fallback segnalato, visibilità del parlante, protezione delle pause e nessuna sostituzione del campo narrativo per risposte brevi. Non provano la qualità editoriale di un intero sketch.

Resolve 21.1 MCP, progetto locale di test: inserimenti separati video/audio della sorgente stereo 9815 su tre coppie V/A; sottotipo audio mono verificato, record start/end combacianti, colori Blue/Green/Orange, link AV presenti e GetAudioMapping sorgente immutato. Timeline temporanea eliminata, timeline iniziale ripristinata. Il test ha evidenziato il divieto di eliminare l’ultima traccia audio: il codice crea prima le tre sostitutive. Anche l’adapter JavaScript completo è stato eseguito tramite un bridge di test sulle API native Resolve: 9 inserimenti video + 9 audio dai tre file reali, compresi source_ranges per silenzi, distribuiti su tre coppie mono; controlli di sorgente/timecode/posizione/colore/link superati, mappature sorgente invariate, timeline originale ripristinata e timeline temporanea eliminata. La nuova versione completa del pannello non è stata ancora usata per applicare il premontato reale dal plugin installato. Non è stato ascoltato il mix risultante.

Ulteriori verifiche updater: riprodotto su Windows PowerShell 5.1 processo separato il mancato autoload di Get-FileHash; aggiunti import espliciti Utility/Management. Test reale con hash errato raggiunge la verifica SHA e restituisce il dettaglio corretto senza effettuare installazione. Test regressione impedisce successo se package.json installato conserva la vecchia versione; dettagli locali redatti prima della visualizzazione. Timeline native 9 AV ritestate sotto Premontato/v0.9.0/Test con nome contenente v0.9.0, poi eliminate.

## 0.9.1 — correzione avvio Electron

Riprodotto il problema con il preload realmente installato nell’Electron ufficiale di Resolve: module not found: ./package.json impediva l’esposizione dell’intera API e bloccava versione, recupero e comandi. Il numero versione viene ora passato dal main tramite additionalArguments, senza import locale nel preload sandbox. Titolo e badge HTML iniziale riportano la versione anche prima del JavaScript. Test di regressione nella sandbox limitata e smoke nell’Electron reale con IPC di prova: API esposta, v0.9.1 visibile, sessione di prova recuperata, pulsanti copione/aggiorna funzionanti e nessun errore. Il bridge Resolve vivo non è simulato come risultato di questo smoke; gli altri collaudi nativi restano quelli documentati sopra.
