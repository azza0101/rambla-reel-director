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

## 0.9.2 — prova reale completa e limiti editoriali

Eseguita la pipeline installata 0.9.1 sulle tre riprese reali già trascritte in Resolve, con cache visuale vuota: identificata la scena corretta, 79 segmenti grezzi, 33 intervalli visivi e 66 still. Ispezionate manualmente le still per confermare campi e personaggi: questo controllo umano non costituisce prova di identità automatiche affidabili. Riprodotti e corretti taglio della conclusione dell’invito, selezione del controcampo sbagliato e prestito del nome iniziale della battuta seguente. Verificato anche il recupero di un progetto salvato con segnaposto negativo e l’errore nativo GetSelectedClips senza selezione.

Con le correzioni 0.9.2: 12 battute abbinate, nessuna non abbinata, 66,20 s; creata una nuova timeline nel progetto reale e riletti 12 segmenti video e 12 audio, su tre tracce video e tre audio mono, colori Blue/Orange e sorgenti/tempi verificati. Timeline iniziale e mapping audio sorgenti preservati. Generato e decodificato completamente un proxy dagli intervalli riletti dalla timeline; non è un render Resolve né una prova del mix finale.

Il risultato resta un premontato da revisionare: una ripetizione finale scelta automaticamente perde l’attacco del discorso; l’invito resta una lunga stretta e non inserisce la reazione silenziosa di Fabrizio prima della larga. Le note libere non aggiungono reazioni automatiche. Non equivale a 12 battute editorialmente complete e non viene dichiarato montaggio finito. Questi limiti restano segnalati, separati dai controlli tecnici superati.

Misurata analisi campi della stessa clip 4K da 1716 frame: 198,47 s con seek ripetuti, 10,18 s con campionamento sequenziale, stessa cadenza di campionamento. Test automatici: 69 Node, 56 unittest Python e 9 contratti pacchetto, senza dipendenze globali aggiunte. Il runtime distribuito non include pytest; i contratti sono stati invocati direttamente.

## 0.9.3 — scelta completa e reazione automatica

Prova reale sulle medesime tre riprese: scena individuata e tutte le 12 battute abbinate; il discorso finale conserva ora “Eh, va beh, ma che significa?” scegliendo una versione completa della master invece della ripetizione parziale più recente. Il motore cerca e propone autonomamente una stretta silenziosa di Fabrizio di 30 frame (1,20 s) al frame 1040–1070 della copertura stretta, poi la risposta sulla larga. La still esatta al frame 1055 è stata ispezionata. Nessun intervallo di questi tagli è stato immesso manualmente; rimangono manuali soltanto le conferme visive dei personaggi/campi e i marcatori narrativi già disponibili.

Nuova timeline nativa PREMONTATO v0.9.3 - TEST COMPLETO AUTO, cartella Premontato/v0.9.3/Test: 12 battute, 14 segmenti AV inclusi inserto e taglio di pausa, 1788 frame (71,52 s), tre tracce video e tre audio mono. Adapter verifica sorgenti, timecode, sincronizzazione, colori e mapping. Contenuti della timeline iniziale preservati e timeline iniziale ripristinata. Proxy ricostruito dagli intervalli riletti dalla timeline e decodificato completamente; non è un render Resolve né un ascolto certificato del mix.

Verificati nel browser locale con il vero Session/worker: anteprima della reazione, esclusione e riattivazione, salvataggio, barra e fasi; trasporto IPC sostituito dal ponte locale di test, non dichiarato click-through sulla finestra Resolve installata. Test di regressione su tentativi interrotti, prestito di battute, margini senza parole adiacenti, mancanza audio/copertura, durata minima, take, idempotenza, esclusione persistente dopo ricalcolo, fotogrammi già trattenuti, progetto manomesso e inserimento AV mono.

Suite finale 0.9.3: 73 test Node, 66 unittest Python e 9 contratti pacchetto superati. Revisione indipendente: corretti mantenimento dell’esclusione dopo ricalcolo e protezione contro riuso di un’attesa già presente nel montaggio. Entrambi hanno test di regressione. Smoke nell’Electron ufficiale con IPC di prova: versione0.9.3 visibile, preload e pulsanti di prova funzionanti, nessun errore; non equivale a un aggiornamento del pannello vivo.


## 0.9.4 — inizializzazione SDK e riavvio del pannello

Riprodotto sul pannello installato 0.9.3: errore nativo «Not initialized, call InitializePromise(<pluginId>) first»; il log Resolve mostra lo scaricamento della integrazione senza un nuovo caricamento dopo app.relaunch(). Riprodotto inoltre il bootstrap inattivo sotto il loader Electron e aggiunto test dedicato. Corretti sia la cache della inizializzazione fallita sia il riavvio che perdeva la registrazione host. Snapshot del collegamento indipendente dalla selezione Media Pool.

77 test Node e 66 unittest Python superati. Prova nel vero Electron distribuito con Resolve, con SDK simulato: recupero da inizializzazione fallita, selezione di tre clip, due ricaricamenti mantenendo il PID e il collegamento, nessun CleanUp durante il ricaricamento; lettura di una nuova versione package.json al primo ricaricamento. Il test usa il vero main, preload, renderer e IPC, ma non dimostra la connessione SDK a Resolve. Correzione applicata localmente; verifica reale dopo riapertura dal menu Resolve ancora da completare.


## 0.9.5 — conferme esplicite e anteprime compatte

79 test Node superati, inclusa regressione sulla conferma finale che non deve nascondere una revisione visiva mancante. Browser locale con renderer vero e Session del plugin: motivo del blocco, collegamento alla revisione, frame chiusi per impostazione iniziale, apertura/chiusura, immagini di volti/still ingrandibili e decodificate, timeline abilitata dopo conferma e nuovamente bloccata da una correzione in bozza. Trasporto IPC sostituito dal ponte locale; nessuna timeline creata in Resolve da questo test UI.


## 0.9.6 — gruppi volti compatti

Test browser con vero Session/worker locale: volti e inquadrature entrambi chiusi all’apertura, pulsanti indipendenti e aria-expanded corretto, due gruppi assegnati allo stesso personaggio e valori conservati dopo chiusura/riapertura, zoom di volti e still, conferma visiva tramite il motore e sblocco timeline. Verificata immagine compatta della sezione; nessuna timeline creata da questo test.


## 0.9.7 — creazione indipendente dalla selezione corrente

Riprodotto il blocco causato dal confronto ordinato con GetSelectedClips. Risoluzione per ID delle sorgenti analizzate nell’albero Media Pool, senza cambiare cartella; controlli sulle proprietà del media e mantenimento della validazione file/progetto/timeline. Test automatici: creazione dopo cambio selezione/cartella con GetSelectedClips che solleva intenzionalmente errore se consultato; sorgenti mancanti e ricollegate fermate prima di creare timeline/cartelle. 82 test Node superati. Test UI con Session/worker locale: errore di creazione mostrato accanto al pulsante e comando riabilitato.

Prova nativa nel progetto test-mcp: nuova timeline PREMONTATO v0.9.7 - TEST SORGENTI SALVATE, cartella Premontato/v0.9.7/Test; 12 battute, 14 segmenti AV, 1788 frame, tre tracce video e tre audio mono. Sorgenti e tagli riletti dalla timeline con adapter reale tramite scripting Python; timeline originale verificata invariata e ripristinata. Il test nativo non è un click-through del pannello Electron e non rifà l’analisi editoriale.


## 0.9.8 — progressi aggiornamento e apertura del risultato

84 test Node superati. Regressione discovery: eventi ricerca/manifest prima delle rispettive risposte di rete, avanzamento manifest misurato e nessuna credenziale negli eventi. Browser con Session/worker e servizio aggiornamento simulato: barra visibile immediatamente prima della risposta, timer attivo, percentuale/MB da byte ricevuti, errore di riapertura visibile con ripristino del pulsante. Immagine del pannello di avanzamento ispezionata.

Prova nativa Resolve: PREMONTATO v0.9.8 - TEST APERTURA AUTO, 12 battute/14 segmenti AV e tre tracce mono; verificato che la timeline appena creata diventi attiva. La prova QA ripristina poi esplicitamente la timeline iniziale, verificata invariata. Il comando utente passa activateCreated=true e aggiorna il contesto del pannello alla nuova timeline. Il test nativo non è un click-through del pannello installato.


## 0.9.9 — conferma visiva compatta

Browser locale con renderer e Session/worker: tendina esterna chiusa inizialmente, conferma e ricalcolo visibili all’esterno, collegamento dal blocco timeline che apre la tendina, ricalcolo e abilitazione timeline anche dopo averla richiusa. Verificate anche le regressioni su associazioni, zoom e progressi aggiornamento. Screenshot della sezione chiusa ispezionato. Nessuna modifica al motore di montaggio o prova nativa aggiuntiva richiesta per questa modifica di presentazione.


## 0.9.10 — elenco montaggio compatto

Test browser con Session/worker: elenco battute chiuso inizialmente, conferma finale e comando timeline fuori dalla tendina, apertura dei controlli e applicazione dei blocchi per bozze; conservati i test su conferma visiva e progressi aggiornamento. Nessuna modifica al motore o alle sorgenti.


0.10.0 — 2026-10-25. Real worker/session tested on the three supplied 25fps clips and full screenplay, with existing Resolve transcripts but without manual shot labels, names, narrative markers or alternative choices. All 12 dialogue beats matched; master opening, girl invitation close, refusal master, Fabrizio homosexual line tight shot verified. First analysis with fresh analysis cache: 85.84s, repeated run 0.40s; transcription time excluded. Still/identity debug deferred. Seven audio/video candidate samples; no cloud calls.

Native Resolve API created and opened PREMONTATO v0.10.0 - TEST PARLANTE AUTO FINALE 181424 in Premontato / v0.10.0 / Test: 12 beats, 13 AV segments, 1707 frames (68.28s), three video tracks and three mono audio tracks, colors/readback verified; prior active timeline contents preserved and restored. Private contact sheet visually inspected. Found and fixed a three-frame repeated pause handle.

Local browser UI exercised final confirmation without names/debug, explicit debug generation, collapsed sections, manual corrections, zoom, and update progress; no page errors. These tests use the actual session/worker and a test UI bridge, not the installed Resolve panel. Narrative interpretation uses conservative text cues and remains an estimate. ASD is sampled, not exhaustive ground truth or actor identity recognition.

0.10.1: ritorni master su scambi prolungati al cambio di parlante, esclusi crescendo, dialoghi brevi e monologhi. Regola verificata anche attraverso il protocollo; nessuna inferenza extra per un ritorno master già deciso. Ricalcolate le tre riprese reali: 12 battute e scelte chiave conservate.

0.10.2 migration fix: reproduced installed 0.9.10 updater rejecting worker/active_speaker.py. Updater now accepts safe flat Python modules; installer copies all safe worker modules. Both stage and validate worker imports/dependencies before replacing the old installation. Full installer migration and full in-place update tested in isolated folders with real bundled runtime, plus missing-module payload preserving old files and CPU model load from installed runtime. UAC branch bypassed only in the private update test copy; no UAC behavior claimed tested.


## 0.10.3 — analysis preflight

Local analysis validates the loaded Resolve project without depending on the current timeline or Media Pool selection. Transcription still requires the loaded media set, independent of its ordering, and rejects another project. The renderer initializes preflight progress so IPC errors replace the startup label immediately. Regression tests cover project protection, timeline changes, reordered clips, the main IPC handler and preflight error visibility. JavaScript suite: 91 passed.

Actual host check: adapter.snapshot without reading the current selection and SaveProject succeeded against open Resolve project test-mcp. Session analyzed its three saved media using the installed 0.10.2 Python runtime and worker, completed every phase and produced all 12 dialogue decisions. No timeline was created or changed in this check. The Electron button itself was covered by regression harness, not clicked remotely.


## 0.10.4 — listening reactions and source continuity

The local editor overlays a verified inactive face from the answering take over the tail of the preceding dialogue, retaining the preceding dialogue audio. The reaction is checked against the answering active face by local Light-ASD evidence and bounding-box continuity, without person names. Unknown or talking preroll, reused frames, same-angle cutaways and manually edited decisions are excluded.

Internal silence removal no longer splits the same angle. Adjacent forward intervals in one take preserve their source gap; Resolve coalesces contiguous AV inserts and rejects residual discontinuous same-angle ranges before timeline creation. Manual bounds are never extended to hide a jump. Script actions use shared wide-take dialogue anchors; the alternate outgoing anchor is moved before the opening word group to avoid repeated words. A final action preserves available take tail up to 30 s, subject to production-cue boundaries. This is source coverage, not semantic action recognition; duration remains reviewable in Resolve.

Verification: full Python and JavaScript suites passed; full automatic analysis produced 12 dialogue decisions, one 2 s listening overlay and two action spans. Project save/load preserved new fields. With existing shot/audio cache and fresh ASD evidence the test took 26.72 s, and repeated same-worker analysis 0.39 s; this excludes Resolve transcription and cold shot analysis.

Actual Resolve readback: timeline PREMONTATO v0.10.4 - TEST REAZIONI E RACCORDI 192259, 2734 frames / 109.36 s, eight AV segments, three mono audio tracks. Reaction video used 9816 frames 1020–1070 with 9820 dialogue audio; wide coverage retained girl exit / Claudio approach through frame 1550 and final action to take end. No same-source discontinuous adjacent video cuts. Previous timeline contents preserved and restored during test. Button itself not clicked remotely.

Final packaging check: exact ZIP/EXE hashes, versions, licenses, shipped source bytes and excluded SDK/private files verified. Full updater migration from a 0.10.3 fixture installed the two new modules and imported them using its installed runtime; a broken payload preserved the prior installation. UAC was bypassed only in the private fixture copy, not production. Headless renderer reaction toggle and timeline readiness passed without page errors. The latest 0.10.4 test timeline was subsequently opened for user review.
