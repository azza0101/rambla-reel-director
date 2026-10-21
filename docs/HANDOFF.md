# v0133 / Auto-Cut 0.1.11 — measured timestamp recovery

Root cause: ASR assigned 13.4 seconds to one word, hiding a failed take and its complete retry. Alignment accepted the long span; CUT and caption exports consequently inherited it. The Resolve importer matched the saved source map.

New analysis detects implausibly long word spans before editorial selection, re-recognizes only short cached source windows with the existing Groq ASR, validates the result, and invalidates indexed proposal caches by transcript fingerprint. It never fixes unknown speech by shortening a timestamp. Alignment refuses anomalous measured updates. Native delivery (including without captions) and captions reject unresolved retained anomalies; discarded anomalies do not block export. Source word fingerprint prevents mixing an old CUT map with changed words. A short word crossing an extraction boundary remains available; uncertain manual index remapping raises instead of silently discarding user choices.

Relative audio levels are measured locally and supplied only as an editorial hint for quieter off-camera direction. Low volume alone never excludes speech. No additional provider or audio upload is introduced for this measurement. Missing optional measurement preserves text. Semantic cache version 6.

Current project was recovered from the specifically authorized audio windows only, without another cloud editorial call or Resolve mutation. Its explicit manual exclusions/restorations and selections outside repaired regions were verified unchanged. Full previous CUT artifacts are in autocut-data/repair-backups with a local report. Private transcript/audio/recovery scripts are excluded from GitHub and update ZIP. Reapply is manual. Existing manually restored closing fragments remain as the user chose; this targeted repair does not declare the entire edit approved.

Validation: 224 Python tests passed, including anomalous retained/discarded spans, cache reuse, rollback on ASR failure, alignment protection, word-boundary preservation, manual remapping, quiet-volume context, subtitles and native delivery. Rollback: managed code backup from apply_archive plus the project repair-backup; restore the whole paired transcript/plan folder with the service stopped.

--- Previous handoff ---

# v0132 / Auto-Cut 0.1.10

Apply dialog now has Crea sottotitoli checked by default. Explicit Apply locally generates revision-specific SRT and short native caption rows from the final reviewed source-to-edited map. It uses aligned transcript only when its signature matches; no new ASR/AI. Omitted source spans never become end-of-timeline captions. SRT timings are bounded by CUT duration and do not overlap.

The existing insert_native_subtitles engine imports captions on empty ST1, verifies text/frame bounds and identifies the generated track. This runs inside native CUT rollback handling. Reapply first backs up/preserves the previous whole timeline (including captions), clears the authorized old content, and produces one caption set on the new CUT, avoiding duplicates. Unchecking skips caption generation/import. Download SRT becomes available after a successful application.

Local current CUT proof: 71 rows, 73.067 seconds, last subtitle exactly at CUT end; no AI/Resolve mutations. Actual Apply remains user-triggered. Private transcript and SRT are local only and excluded from releases.

--- Previous handoff ---

# v0131 / Auto-Cut 0.1.9

Visible preparation loader (indeterminate progress, phase, elapsed time) before timeline/range import and ASR launch. Startup controls are locked during the request, with a 30-second request timeout and explicit error display. The existing CUT progress follows once the job is accepted.

Native pause removal is now strictly optional: `ELIMINA PAUSE`, presets and restore are available without Edit mode. Initial CUT merges unremoved consecutive-word pauses; only explicit tight_pauses removes them. Metadata is persisted in native transcripts so all manual rebuilds and restore retain this choice. Main MAGICO behavior is unchanged.

Current project 6e3fe3e96c3d finished successfully in about 21s. Its text/take choices were preserved; pause-opt-in metadata applied with backup, duration 104.47s -> 105.47s, tight_pauses false. No new AI or Resolve mutations.

--- Previous handoff ---

# v0130 / Auto-Cut 0.1.8

Apply the in-memory CUT repeatedly on an edited current timeline without source import or analysis. Read-only apply-check detects edits and returns a SHA256 fingerprint. A styled OK/Cancel dialog explicitly authorizes preservation of existing content; Apply checks that the fingerprint is unchanged before backup/deletion. Cancel sends no apply request.

Edited current content is preserved as a disabled nested timeline reference after the new CUT, retaining its effects/audio/titles. The fully editable snapshot lives in `BCK/<timeline name>/<timeline name> · BCK · date · time · number`. Existing BCK contents are not migrated. New CUT stays native separate clips. Same project/timeline identity and original source identity checks remain mandatory. Failed apply activates the complete backup; original timeline is never deleted.

Actual current Resolve read-only check verified; no automatic Apply and no cloud requests. GUI smoke covers OK/Cancel. No source/project/cache deletion.

--- Previous handoff ---

# v0129 / Auto-Cut 0.1.7

Fix IN/OUT import from restored sessions. `RILEGGI TIMELINE E IN–OUT` calls an authenticated backend endpoint that reads Resolve in a disposable process, with a 20-second timeout. `AVVIA AUTO-CUT` always refreshes live source/range before analysis, and refuses to analyze if that read fails. No native SDK call in the Electron UI import path. Zero IN is valid; inclusive OUT maps to a half-open source range. No live timeline mutations during verification.

Previous full-source project stays intact; selected-range import creates/reuses a separate project. Real current marks verified: [0,10477) source frames at 30 fps. No AI invoked during debugging. User must start analysis of the selected-range project.

--- Previous handoff ---

# Latest update — v0128 / Auto-Cut 0.1.6

Current branch: fix/magico-images-specific-generics-v0094. Prior verified remote parent: eb6c7d93026c29cb11f0fe276be448042c52b51d.

Selected IN/OUT source import, bounded ASR with absolute source timings, range-safe manual CUT rebuilds, styled Apply destination dialog, backup plus disabled full original parked after CUT on active timeline. No automatic Resolve Apply. See docs/AUTOCUT_INTEGRATION.md for behavior, checks and limitations.

Also includes post-v0127 corrections: explicit recitation direction filtering, take dialog opens from read-only review, Apply bypasses blocking native SDK read, VFR full-clip validation and errors adjacent to Apply.

Original projects, source files and previous repair backups are retained. No secrets/media/transcripts in source or update archive. Rollback: previous 0.1.5 package plus installer update-backups; active timeline backup in BCK.

--- Previous handoff ---

# Auto-Cut v0127 / 0.1.5 - 2026-10-21

Production CUT stays Groq; Gemini comparison timed out and is not a production dependency. Complete ASR-block decisions are validated locally, then whole-retake reconciliation selects the latest and prevents nested restarts reappearing. Preserve unique premises and named-place differences; reject incomplete decisions. The full editorial report stays local in cut/editorial-review.json, excluded from GitHub diagnostics.

Real project 80e60d811461 restored with full backup and prior manual exclusion preserved. Delivery revision 576bf454b3bfe362b36ee7f5: 414 kept words, 147.63 seconds, 11 segments, 8 selectable alternate groups. Exact retained-word match to a human-read reference, never provided to runtime. Low-resolution preview ready. No Resolve mutations. 124 targeted tests and browser smoke passed before final metadata changes.

Backups: autocut-data/repair-backups. AGGIORNA restarts only the native integration and loads saved result. No automatic APPLICA.

# Auto-Cut v0126 / 0.1.4 - 2026-10-21

Fixed invalid selected_take indices during merge: keep alternatives for review. Sorting preserves selected take identity. Real recovery succeeded: project 80e60d811461, 27 segments, 11 groups, 221.97 seconds, 645 kept words. Full backup saved before recovery; no Resolve mutations. 94 targeted tests passed. Sanitized automatic diagnostics confirmed by private issue #16.

# Provider JSON recovery + Auto-Cut diagnostics v0125 / 0.1.3 — 2026-10-21

The 0.1.2 user run advanced past block 1 but failed in block 2 with HTTP400 Failed to validate JSON. cut_cloud now recognizes generated-output validation errors separately from invalid request schemas, retries a full JSON-object document with schema instructions and local Draft202012 validation, lower reasoning and bounded quota. Original failed_generation is never consumed. Existing valid block-1 cache and measured-word transcript remain reusable.

Auto-Cut now installs the existing sanitized diagnostics routes/reporting. Production startup enables automatic reporting on first use as explicitly authorized by user on 2026-10-21, preserves later opt-out; test apps default off. CUT/app/apply failures go to the private GitHub reporter, with new PROVIDER_JSON and PROVIDER_OUTPUT_TRUNCATED categories. ASSISTENZA is included. Original failure report received as issue #16; no video/transcript/keys/paths uploaded. 92 focused tests passed; synthetic browser review/preview still passed. Live recovery test running in a separate scratch project copy, no Resolve mutation; results will be recorded separately.

# Auto-Cut truncated Groq output fix v0124 / 0.1.2 — 2026-10-21

Real integration run on project 80e60d811461 failed at 25% while proposing take groups, first of three word windows. Groq returned HTTP 400 max completion tokens reached. Original measured-word transcript remains cached in autocut-data; no CUT plan or timeline edits were completed by the failed run.

cut_cloud.query_json now recognizes only output-truncation failures, retries a complete JSON document with lower reasoning and a larger completion allowance within the existing 7500-token pacing budget, max three attempts total. It never consumes failed_generation as a partial plan. Other HTTP 400 errors are not retried. Existing transcript and successful per-request cache remain reusable. New tests reproduce truncation and distinguish malformed requests. No live AI retry or Resolve mutation was performed during diagnosis/unit verification. User should AGGIORNA the integration, then AVVIA AUTO-CUT; transcription is reused if source unchanged.

# Auto-Cut in-plugin updates v0123 / 0.1.1 — 2026-10-21

AGGIORNA added to the integration, with idle checks, clean worker shutdown, code-only updater and Electron app.relaunch (guard refuses if host executable is Resolve). No Resolve process termination. Last project/context restores after relaunch. Developer checkout reloads local source/plugin JS; registered installs fetch dedicated autocut-* prerelease assets, not the RMBL main latest release. Loaded native SDK and runtime are excluded; dependency changes require installer. Main RMBL must be closed if sharing its runtime/code before a production update.

Updater tests cover allowed paths, traversal rejection, native SDK/data/credential preservation, SHA mismatch. Node lifecycle mock proves only integration/worker restart and busy rejection. Actual installed worker startup/UI/auth/shutdown and synthetic review/preview verified. Real Resolve host opening/relaunch still pending user test; never claim it was exercised. First registration can require Resolve restart. Packaging and Mac hardware verification remain pending.

# Auto-Cut Workflow Integration v0122 — 2026-10-21

New independent integration com.rambla.autocut / version 0.1.0 installed in the local Resolve Workflow Integration Plugins folder. Native SDK copied from this machine's installed Resolve, not committed. Main app/bridge remain usable independently; only shared CUT UI change is making its optional Analysis button nullable.

Worker: backend/app/autocut_service.py, loopback + random per-session token, dedicated ../autocut-data. Shared install_cut_routes/CUT UI/native export/native apply engine. No bridge routes, heartbeat or outbox. Explicit source import and explicit Apply; Apply creates a new owned timeline and leaves original intact. Current revision/source identity/current Resolve project+timeline checks. No native timeline mutations or AI calls in the completed smoke tests.

Window lifecycle/SDK source adapter: tools/autocut_integration. Installer: tools/install_autocut_integration.py, INSTALL_RMBL_AUTO_CUT.ps1/.command. Windows installed-worker boot/auth/UI/shutdown and synthetic browser review/preview tested; 49 focused Python tests + 3 Node adapter tests passed before final verification. Await real Resolve menu opening/source snapshot and real Apply. Existing Python runtime is reused; self-contained runtime packaging, Mac hardware test and native Resolve transcript reading are NOT complete. Studio + Local scripting required for existing native Apply helper.

Full instructions and exact limitations: docs/AUTOCUT_INTEGRATION.md. No keys copied to plugin source/runtime config; existing .env.local allowlist loader reused. Do not publish credentials or local SDK binary. Original project data untouched.

# Main application reference theme v0121 — 2026-10-20

Main app only: charcoal surfaces, compact controls, restrained aqua/violet accents, consistent workflow headers and smaller previews. Bridge GUI unchanged. Existing custom paints remain saved and active; factory defaults migrate only on exact former factory values. RIPRISTINA COLORI previews the new defaults; SALVA IMPOSTAZIONI persists them.

Combined export retains the full native subtitle transcript. Highlight words, including expanded compound names, form separate disabled cues. Native import matches newly created cues by text and frame range before applying and verifying SetClipEnabled; existing clips are untouched. State is applied before restoring track locks. Text-only export without highlights keeps all cues enabled. No Resolve timeline modified during this task; mock integration verified, actual APPLICA remains user-controlled.

A stale visual plan no longer turns export-options into HTTP 500 / false project-restore error. Counts for text remain readable, media warning is shown, and existing export validation remains authoritative. No plan regenerated or selections changed.

Verification: 111 focused unit tests passed. Browser checks at 1440 and 720 px: no JavaScript errors, no horizontal overflow, accordion and unsaved live-color preview working. Old custom preferences were not overwritten (automatic review rejected that proposal).

# Diagnostica remota v0120 — 2026-10-20

ASSISTENZA su entrambe le GUI: consenso automatico inizialmente spento, invio manuale, anteprima e copia. Coda sanitizzata condivisa e lock app/bridge; repository privato obbligatorio, deduplica e limite 10/giorno. Agganci agli errori CUT, MAGICO, app e bridge. Non inviare messaggi grezzi o progetti: solo schema allowlist verificato prima di ogni upload. Prova reale issue #13 creata, riletta e chiusa; nessun dato del video inviato.

Preconfigurazione GitHub pronta con token fine-grained dedicato + DPAPI locale. Non copiare il token OAuth attuale dell'account. L'utente ha fornito il token dedicato: salvato solo in .runtime-temp/github-distribution-token.txt e nel provisioning personale ignorato da Git. Verificati download release e apertura issue #14, chiusa dopo la prova. Sul PC corrente e cifrato DPAPI in rambla-data/credentials; le chiamate runtime GitHub usano quello, senza modificare il login CLI usato per pubblicare codice. Non pubblicare quel file o installer personale. In assenza del token si usa il login CLI esistente. Nessun monitoraggio Codex continuo e nessuna patch automatica dal client.

Dettagli: docs/REMOTE_DIAGNOSTICS.md e docs/DIAGNOSTICS_QA_20261020.json. Versione app/bridge v0120. Nessuna modifica a Resolve.

# Windows distribution v0119 — 2026-10-20

SEARCH UPDATE in entrambe le GUI. Repository privato: GitHub CLI autentica l'utente; download release con SHA256 e controllo zip, conferma, blocco durante CUT/MAGICO/ricerca/APPLICA. Sviluppo Git non viene sovrascritto. App riavviata, Resolve mai arrestato. Bridge attende la fine dell'installazione prima di autoricaricarsi.

Installer: wheel offline, FFmpeg + DLL, GitHub CLI, template Fusion, collegamenti standalone/bridge. Bootstrap Python 3.12 via winget se assente. Installazione e aggiornamento v0118->v0119 provati in directory isolate: dati, .env.local e preferenze conservati; backup codice e script rollback. HTTP health/UI/stato update della copia installata verificati. Nessun test su un secondo PC fisico ancora.

EXE standard e ZIP aggiornamenti non contengono chiavi. Su esplicita richiesta utente viene prodotto un EXE PERSONALE solo locale, con 3 API preconfigurate. Mai pubblicare dist/personal o private-provision.json. Copia provisioning verificata senza stampare valori. Gateway FreeLLMAPI sperimentale esterno non incluso; provider nativi utilizzabili.

# RMBL B ROLL — handoff v0118

2026-10-20. Branch: fix/magico-images-specific-generics-v0094. Non fare merge automatico.

Ultimi interventi: riconciliazione CUT incrementale, ripristino/esclusioni manuali, preview ridotta, verifica sorgenti native VFR, sottotitoli senza sovrapposizioni, coperture distribuite e fill del quadro, nomi composti evidenziati interamente. FreeLLMAPI opzionale locale per tavole di tre fotogrammi.

Verifica reale coperture: docs/COVERAGE_QA_20261019.json e docs/LOCAL_COVERAGE_AUDIT_20261019.json. La selezione reale precedente è stata revisionata manualmente; non confonderla con una verifica cloud. Prova gateway separata: docs/VISUAL_GATEWAY_TRIAL_20261020.json. Nessuna credenziale inclusa nel repository. Il gateway sperimentale esterno non è ancora incluso nell'installer.

Test mirati recenti: 43 per gateway/vision/product/usage/launcher; 35 per highlight e selezioni. Due test editoriali preesistenti restano da correggere (deduplicazione e mock max_output_tokens). Non dichiarare verde l'intera suite.

Progetti, media e chiavi restano fuori Git. APPLICA in Resolve rimane esplicito. Installer e aggiornamento GitHub sono il prossimo lavoro, non ancora collaudati su un altro PC.

---

# RMBL B ROLL — handoff tecnico

Aggiornato: 2026-10-17  Versione: `v0078`  Branch di consegna: `feat/api-first-text-first-v1`

## Reinvio esplicito MAGICO v0078

INVIA AL BRIDGE disponibile dopo la preparazione, anche su risultato parziale/già consegnato: conserva CUT, selezioni, ricerche, media, payload e contatori; invalida solo la consegna e archivia il journal precedente, producendo un nuovo pacchetto nella sessione corrente. Nessuna nuova chiamata AI. Riprendi mantiene il significato di continuare le fasi interrotte. Il bridge mostra GIÀ APPLICATO e disabilita APPLICA sul CUT completato, anziché offrire un pulsante che il backend ignora per evitare duplicati. Reinvio abilita una nuova applicazione, con nuova timeline CUT esplicitamente indicata. 288 regressioni passate.

## Recupero template Fusion vuoto v0077

Resolve 21.1 può inserire KURA_paper_title_v9 restituendo una composizione senza nodi, anche se il template è installato. Il seed CUT verifica la composizione e, solo se vuota, importa direttamente il .setting del medesimo pacchetto DRFX in una composizione, collega MediaOut e usa poi il percorso già esistente dei titoli singoli. Nessun cambio di template o compound. Il pacchetto selezionato è trasmesso e aggiornato insieme al nome al momento di APPLICA. Seed già valido invariato. Prova reale: testo modificabile, 68 nodi e MediaOut collegato; regressioni 287 passate. Pacchetto fallito rilanciato sui media salvati senza nuove chiamate AI; rollback precedente aveva rimosso la timeline incompleta.

Esito reale completato: `RMBL CUT 20261017 081754 aee559` nel progetto TEST Egitto, 19 video + 19 audio originali, 39 titoli individuali con una composizione ciascuno, 91 sottotitoli nativi, 9 coperture e zero saltate. Durata 2232 frame a 30 fps, 1080x1920, source_unchanged=true. Conferma indipendente via MCP dopo fine helper; nessun RPC concorrente durante l’importazione.

## MAGICO ibrido economico v0076

- Pulsante MAGICO dopo la sorgente: CUT isolato, pause medium e margine finale 120 ms, selezioni automatiche, piano contestuale, ricerche limitate, verifica dei fotogrammi reali, pacchetto standard. APPLICA resta manuale.
- Budget predefinito 12 chiamate cloud totali, di cui al massimo 4 visive. Nessuna chiamata Codex nel prodotto. Risposte, checkpoint e consumi persistono; riprendere non azzera i contatori. CAPTCHA e media non verificati restano segnalati, non approvati automaticamente.
- Le immagini di riserva verificate sono disattivate su traccia dedicata sotto i titoli. Se non c’è una copertura verificata resta il parlato, con avviso. Generiche collocate nel testo quando coerenti, senza coda obbligatoria.
- Sorgente caricata oppure snapshot di clip originali Resolve: tracce AV, offset sorgente, abilitazioni e formato conservati. Retime/nested e sorgenti non verificabili fermano il percorso prima della modifica.
- Correzioni da test reale: Director raggruppa il testo compatto anziché metadati parola; risultato AI completamente vuoto non viene pubblicato; verifica video usa il file scaricato anziché il JPEG Pexels; fotogrammi mancanti non fanno fallire tutto; modulo snapshot standalone senza dipendenze server.
- Resolve 21.1 rifiuta Red nella tavolozza delle clip: le alternative restano disattivate e usano Pink se Red non è supportato. Tracce audio nuove create prima di eliminare quelle vuote predefinite.
- QA reale TEST Egitto: CUT da file originale 2232 frame a 30 fps, 10 alternative disattivate, marker originali invariati. Ricostruzione snapshot multitraccia 210 frame esatti, firma sorgente invariata. 285 regressioni passate prima del rilascio; parsing JS verificato.
- Collaudo cloud reale run `7f7c968e5ad6486e8e2c50e02f0f17a7`: output salvato `3b295c5c891c`, 5 richieste editoriali più 4 visive incluse le prove di correzione. Sei video verificati, zero immagini approvate e 23 passaggi senza copertura; esito parziale esplicito. Ricezione automatica confermata dal bridge per `handoff-20261017-075627-437048-ea580a05`, senza AGGIORNA. APPLICA completo lasciato manuale all’utente.
- Runtime live verificato build `c791791c7399`, UI v0076 e BRIDGE CONNECTED; stato MAGICO ritrovato ricaricando il progetto risultato, contatori 9/12 e 4/4 visive corretti. Il primo comando restart ha incontrato una corsa con il riavvio automatico: il processo già avviato è sano ed è stato riutilizzato con focus sul risultato.


## Take alternative compatte v0075

Le take scartate restano disattivate e diventano Red. La durata termina al termine della frase scelta corrispondente, rimappata attraverso i segmenti CUT anche se contiene pause eliminate. Una take più corta non viene allungata. Sorgente originale e maniglie restano disponibili. Si applica ai nuovi export video CUT; timeline già importate non alterate automaticamente.

## Parole evidenziate senza annidamento v0074

- Eliminato CreateFusionClip dal percorso condiviso append_separate_fusion_titles: composizione applicata direttamente alla singola clip, senza contenitore Fusion/compound. Vale per invii CUT e standard.
- Nome assegnato prima di importare la composizione; testo e timing verificati. Prova reale isolata: titolo a frame 320–350, composizione corretta, clip ordinaria con 11714 frame di margine destro. Nessun contenitore da decomporre.
- 267 test CUT/Resolve/export/UI passati. Le clip già annidate si rigenerano reinviando le sole parole evidenziate; non vengono convertite silenziosamente durante l’aggiornamento.

## Invio componenti dal progetto CUT v0073

Il progetto CUT confermato cerca la ricevuta della base nativa anche nel proprio progetto originale (cut-origin.project_id), verificando revisione e identità sorgente. Consente video-only dal padre seguito da testi/subs dal figlio sulla stessa timeline, senza reimportare il video.

## Visibilità trascrizione v0072

Sezione 2 sempre visibile e apribile. Prima della trascrizione/conferma CUT mostra un avviso con collegamento a CONFERMA CUT; contenuto attenuato e non interattivo. Il workflow già pronto resta invariato.

## Export selettivo e CUT nativo v0071

- Sezione 7: sotto INVIA A RESOLVE, tendina **Componenti da esportare** con video CUT, sottotitoli, parole evidenziate, B-roll/immagini, social e coperture generiche. Preferenze salvate per progetto; preparazione solo dei componenti scelti.
- Video CUT: nuova timeline dal file lungo originale, video/audio separati, tagli in frame, formato 1080 sul lato corto e FPS originali anche 30000/1001. Take alternative disattivate sopra la base. Bozza non confermata: solo video; confermare CUT prima di lavorare sugli overlay.
- Invii senza video su progetto CUT richiedono timeline e ricevuta della stessa revisione/sorgente. IN modificato non sposta gli overlay della base CUT.
- Titoli separati sopra i video: creatore esistente con un solo seed Fusion inizializzato. Sottotitoli nativi su ST1 riservata. Nessuna dipendenza MCP nel prodotto.
- SCARICA MP4 CUT sotto il player: file completo separato, render atomico verificato con ffprobe.
- Heartbeat durante APPLICA usa stato cached senza RPC concorrenti. Checkpoint/ricevuta evitano duplicazioni dopo errori di conferma.
- Verifica 2026-10-14: 257 test CUT/Resolve/export passati, con cartelle temporanee adattate al drive Windows nel processo di test. Helper prodotto provato su 20 video + 20 audio, 13 alternative disattivate, 1860 frame a 30fps, 1080x1920; titolo KURA v9 separato, SRT e generica in coda. Prova 30000/1001: 60 frame, 2.002s.

## Avvio rapido

- App: `RMBL_B_ROLL_APP.vbs` oppure `python launch_local_v5.py start`.
- Bridge Resolve: `Workspace → Scripts → RAMBLA_B_ROLL`.
- Backend: `backend/app/curation_server.py`.
- UI prodotto: `backend/app/curation_ui_v2.py`, con moduli UI separati per trascrizione, visual beat ed export.
- Bridge nativo: `tools/resolve_bridge/standalone_bridge.py`.
- Versione unica app/bridge: `RAMBLA_VERSION`.

## Flusso Resolve

### Pass CUT opzionale v0054 (fase plugin)

- Pannello prima della selezione parole: analisi integrale Groq ASR con tempi misurati, gruppi di tentativi, revisione semantica dell'ultima take completa e scarti fuori scena.
- `cut_pass.py` costruisce un'unica mappa in frame originali/ricompattati, conserva la take precedente a quella valida e protegge i confini dall'arrotondamento.
- `cut_pass_routes.py` salva trascrizione originale, suggerimenti, revisione e piano fuori dagli artefatti del workflow. Job asincroni con progressi delle fasi effettivamente completate, errori e debug copiabile.
- UI permette ascolto delle take, cambio della scelta, conservazione/scarto dell'intero gruppo, ripristino degli scarti, parametri pause e anteprima video pulita.
- Conferma crea un progetto indipendente `nome · CUT`, con video di proprietà, guida audio e trascrizione già rimappata; originale e bozza restano recuperabili. Il nuovo progetto riprende dalla selezione delle parole senza ASR.
- Da v0071, CUT di video originali caricati in app esportabile come nuova timeline nativa; CUT di guida audio multitraccia del bridge ancora escluso. Contratto congelato in `cut-origin.json`.
- Test: motore, confini fra parole, FPS, restituzione take precedente, job/revisioni, render reale con conteggio frame e conferma su progetto indipendente. Prova su `TEST-autocut_v1 / IMG_1545.MOV`: 336 parole fino a 185.282s; proposta iniziale verificata 11.9s con tre gruppi, anteprima generata. La domanda sul peso del passaporto è conservata nella proposta: l'utente può scartare quel gruppo se era una variante abbandonata.
- v0055: timestamp video ricompattati con contatore intero dopo il filtro FPS e frequenza di output esplicita; elimina una durata video dichiarata più breve di un frame. Il test reale verifica sia conteggio frame sia durata video, oltre alla presenza audio. La revisione render invalida le vecchie anteprime.
- v0056: anteprima pulita azzera il seek e il callback di ASCOLTA, ricarica anche job successivi con lo stesso esito e mostra il player accanto ai comandi. Audio/video originali vengono messi in pausa durante l'ascolto CUT.
- `cut_alignment.py` verifica le take scelte e le precedenti su finestre brevi del video originale, conserva il testo, aggiorna i timestamp misurati e i confini degli scarti adiacenti. Trascrizione originale immutabile; allineamento separato in `transcript-aligned.json`. Avvisi espliciti per take non riallineate completamente.
- Prova reale v0056: la presentazione non tronca più “Cura Viaggi”; proposta riallineata 10.633s. La penultima presentazione ha un avviso per testo non completamente riallineato e richiede ascolto. Il significato editoriale dei tre gruppi rimane una proposta da revisionare.
- v0057: `Frasi e take` è una tendina chiusa inizialmente. Ogni gruppo mostra la frase scelta nel riepilogo; le take non scelte sono dentro una sottotendina. Gli scarti fuori scena sono raccolti in una tendina separata. Aperture conservate durante salvataggi e aggiornamenti della UI. Pulsante `GENERA ANTEPRIMA CUT`.
- v0058: feedback CUT immediato al click, loader, barra determinata dalle fasi/unità completate, percentuale, tempo trascorso e cronologia delle ultime fasi. Polling stato ogni 900ms. Il cambio sorgente non blocca più lo stato del nuovo job dietro un errore 409 della vecchia proposta. Errore 429 Groq visibile con indicazione del limite temporaneo e tempo suggerito dal servizio.
- Se Groq interrompe la verifica, il rilancio riusa trascrizione e gruppi riconosciuti per la medesima firma sorgente; i risultati del video precedente restano esclusi.

1. Il bridge mantiene un heartbeat con il backend locale e rileva la timeline focalizzata.
2. **USA AUDIO IN RMBL B ROLL** invia audio e intervalli video esistenti; l'audio può essere riutilizzato solo se la firma della timeline coincide.
3. L'app prepara un handoff senza modificare Resolve.
4. Il bridge riceve il pacchetto nella stessa sessione, si espande e abilita **APPLICA**.
5. La modalità predefinita crea un backup timestampato in `BCK` e applica direttamente alla timeline attiva usando l'IN corrente.

Il bridge espone anche **RICALCOLA AUDIO · IN → OUT**: invia `force_recalculate=true`, impedisce il riuso della guida precedente e renderizza il range IN/OUT letto dalla timeline focalizzata in quel momento. Resolve 21 restituisce i mark relativi all'inizio timeline e può omettere `in` quando coincide con l'inizio: `timeline_range()` normalizza entrambi i casi in frame assoluti. Il ricalcolo forzato rifiuta di partire se non vede almeno un range esplicito, evitando il fallback silenzioso all'intera timeline. Il riepilogo mostra `mark_in`, `mark_out` e `range_source` realmente acquisiti.

La timeline sorgente resta protetta. Le mutazioni Resolve passano dai job di `resolve_handoff_jobs.py`; i calcoli temporali usano FPS e frame iniziale della timeline acquisita.

### Sottotitoli nativi e debug v0050

- L'import SRT porta temporaneamente il playhead all'inizio prima di creare il media e lo ripristina al termine.
- Durante l'append viene abilitata soltanto la ST riservata a RMBL: Resolve non può più accodare i nuovi sottotitoli dopo quelli già presenti.
- Stato di blocco e visibilità di tutte le tracce sottotitoli vengono ripristinati dopo l'operazione.
- Il bridge espone **COPIA DEBUG**: copia versione, build, sessione, timeline, pacchetto, avanzamento, errore completo e diagnostica.
- Prova reale su `KURA parlato / KURA_FOTO BAMBINI_v2`: 140 nuovi sottotitoli su ST1 ai frame previsti; 202 sottotitoli preesistenti conservati sulla traccia separata.

### Fusion Title separati v0051

- `KURA_paper_title_v9` è verificato direttamente in Resolve 21.1: il nome registrato è corretto e il preset viene caricato.
- L'API `InsertFusionTitleIntoTimeline` inserisce sempre su V1: con V1 protetta fallisce, con V1 libera esegue un insert edit e sposta le clip esistenti.
- RMBL costruisce i titoli in una timeline isolata che eredita FPS e timecode dalla sorgente, poi copia ogni composizione sulla traccia `RMBL TEXT` più alta come Fusion Clip autonoma.
- Ogni parola o frase evidenziata resta quindi una clip gialla separata, modificabile e con la propria durata; non viene più creata una lunga timeline compound.
- Le revisioni selettive eliminano soltanto i precedenti titoli RMBL e lasciano intatti video, audio e marker del montaggio.
- Il backup viene archiviato come DRT timestampato nella cartella `BCK`; la timeline duplicata e la timeline tecnica dei titoli vengono eliminate alla fine, quindi Resolve non lascia aperte schede temporanee.
- Prova reale su una copia di `KURA parlato / KURA_FOTO BAMBINI_v2`: 24 titoli v9 separati ai frame previsti, nessuna timeline BCK o `RMBL TEXT LAYER` residua.

### Immagini per Visual Beat v0052

- Ogni sezione **IMAGE SUGGESTIONS** permette una ricerca aggiuntiva limitata al Visual Beat attivo e una query manuale testuale.
- La query manuale sostituisce le varianti automatiche per quella ricerca e viene mostrata nella diagnostica del beat.
- Immagini e video condividono la selezione ordinata `V2`, `V3`, `V4…`; la scelta rimane salvata nel normale `selection-plan.json`.
- Durante l'export, ogni immagine selezionata viene materializzata localmente come still H.264 alla frequenza della timeline e copre esattamente l'intervallo della frase assegnata.
- Le immagini Pexels non passano più per il downloader video; l'export usa il file immagine locale verificato.

### Galleria immagini uniforme v0053

- Le immagini di ogni Visual Beat usano la stessa galleria ordinata e paginata delle altre fonti.
- La griglia mantiene anteprime, card e pulsanti della stessa dimensione anche con immagini di proporzioni diverse.

## Branding

- `backend/assets/branding/rmbl_wordmark_white.png`: marchio orizzontale originale fornito dall'utente.
- `backend/assets/branding/rmbl_mark_white.png`: simbolo originale usato come icona app/finestra.
- `backend/assets/branding/rmbl_bridge_mark.svg`: variante del simbolo RMBL con un ponte sovrapposto; è usata esclusivamente dal bridge.

## Distribuzione

- `INSTALL_RMBL_B_ROLL.cmd` è l'ingresso a un clic.
- `INSTALL_RMBL_B_ROLL.ps1` installa app, dipendenze, shortcut e bridge.
- `INSTALL_RESOLVE_BRIDGE.ps1` può aggiornare soltanto il bridge.
- `BUILD_WINDOWS_PACKAGE.ps1` genera lo ZIP trasferibile senza dati privati.
- `BUILD_WINDOWS_INSTALLER.ps1` avvolge ZIP e bootstrap in un solo `RMBL-B-ROLL-Setup-vXXXX.exe` tramite IExpress.
- Gli aggiornamenti rilevano la versione installata, chiedono conferma e mantengono `rambla-data`, profili browser, progetti e configurazioni locali. Il registro di sicurezza e in `%LOCALAPPDATA%\RMBL B ROLL\install-backups`.
- `RMBL_B_ROLL_APP.vbs` è il launcher app senza bridge.

## Browser e accessi esterni

- I pulsanti di accesso TikTok, Instagram ed Envato aprono una nuova finestra nella sessione e nel profilo Google Chrome attualmente usati dall'utente.
- **SCARICA DA ENVATO** apre allo stesso modo la pagina dell'asset in Chrome e continua a monitorare il download ufficiale.
- Il comando Chrome usa `--profile-directory=<ultimo profilo>` e `--new-window`, senza creare un profilo RMBL separato e senza passare da Edge.

## Navigazione guidata

- Le sezioni numerate 1–7 partono chiuse.
- L'app apre automaticamente una sola sezione: il primo passaggio ancora da completare.
- Ogni intestazione resta cliccabile per aprire o richiudere manualmente la sezione.
- In modifica trascrizione, **ANNULLA MODIFICHE** e **SALVA MODIFICHE TESTO** sono affiancati sotto il box, allineati a destra; **MODIFICA TESTO** resta disponibile sotto la trascrizione in modalità normale.

## Tema grafico

- Il canvas predefinito di `v0028` è verde acqua scuro e solido, senza il precedente gradiente marcato.
- Il pannello finale **⚙ IMPOSTAZIONI GRAFICHE** controlla live canvas e sezioni 1–7, ciascuno in modalità solida o gradiente.
- `GET/PUT /api/curation/theme-preferences` valida soltanto colori esadecimali e persiste in `rambla-data/theme-preferences.json`.
- Il file resta fuori dai progetti e viene conservato dall'installer durante ogni aggiornamento.

## Dati locali esclusi dal repository

Non pubblicare `.env.local`, `rambla-data`, profili browser, progetti cliente, media scaricati, cache, log, render, pacchetti DRA/XML di prova o cartelle `.test-*`. Le chiavi provider rimangono locali.

## Verifica

Prima di dichiarare una modifica pronta:

```powershell
$env:TEMP=(Resolve-Path '..\rambla-data').Path
$env:TMP=$env:TEMP
& '..\editorial-intelligence-worktree\.venv\Scripts\python.exe' -m pytest -q -p no:cacheprovider
```

Il vincolo di sviluppo resta `resolve_calls=0`: i test non devono modificare una timeline reale. Per prove reali su EGITTO serve l'azione esplicita dell'utente nel bridge.

### Correzione Resolve v0035

- La timeline di lavoro e il backup vengono spostati nel bin `TEMP` soltanto dopo la materializzazione. Resolve 21.1 non inserisce i Fusion Title se una timeline appena duplicata è stata spostata prima del montaggio.
- L'importazione SRT sblocca temporaneamente la prima traccia sottotitoli e ripristina subito il lock. Resolve 21.1 restituisce successo ma crea zero clip quando quella traccia è protetta.
- Verifica reale su `Egitto2 / EGITTO`: 25 Fusion Title e 117 sottotitoli nativi creati; timeline sorgente invariata e backup conservato.

### Applicazione diretta Resolve v0036

- La timeline attiva viene modificata direttamente: non viene più creata una terza timeline di lavoro.
- Prima di ogni modifica viene creata una copia numerata con giorno e ora nel bin `BCK`.
- L'origine temporale viene riletta dall'IN corrente quando si preme APPLICA.
- I marker vengono salvati e ripristinati con posizione e metadati identici.
- Le parole evidenziate occupano sempre la traccia video più alta, sopra ogni B-roll.
- I video vengono organizzati in `B-ROLL MEDIA`; gli estratti conformati conservano maniglie pari alla durata visibile per lato quando il sorgente lo consente.

### Stato suite al passaggio v0036

I test focalizzati sulla disposizione dei comandi di modifica testo, UI, tema e versione passano (`47 passed`). La batteria precedente su ricalcolo audio IN/OUT, normalizzazione dei mark Resolve 21, cache, bridge standalone e distribuzione Windows passa (`71 passed`). Il JavaScript completo renderizzato passa inoltre `node --check`.






### Correzione primo Text+ v0038

- Resolve 21 può ignorare il primo posizionamento non-zero su una traccia Fusion Title appena riservata e creare il primo titolo dall'origine relativa della timeline.
- La materializzazione ora inserisce un boundary di priming vuoto a frame 0 quando la prima parola evidenziata parte più avanti.
- Il primo boundary reale spezza il titolo di priming esattamente nel punto richiesto; il frammento vuoto iniziale viene poi eliminato dalla selezione dei range esatti.
- Il comportamento non cambia quando il primo titolo parte già da frame 0.
- Aggiunti test di regressione per priming, assenza di doppio zero e rimozione del lead-in.


### Wrapping Text+ verticale v0039

- Le frasi evidenziate inviate ai Fusion Title vengono ora mandate a capo automaticamente tra parole.
- Ogni riga cerca di restare entro 11 caratteri, così i titoli lunghi non sbordano nel formato verticale.
- Le parole non vengono mai spezzate a metà; una singola parola oltre 11 caratteri resta intera.
- Lo stesso testo wrappato viene usato anche nella verifica finale di Resolve, evitando falsi mismatch.
- Aggiunti test per wrapping, parole lunghe e integrazione nel piano Text+.


### Aggiornamento selettivo Resolve v0040

- Il bridge espone tre modalità di Apply: **TUTTO**, **SOLO TESTI** e **SOLO SUBS**.
- Le modalità selettive lavorano esclusivamente sulla timeline attiva e creano comunque il backup numerato in `BCK` prima di ogni mutazione.
- **SOLO TESTI** non prepara, conforma o reinserisce alcun B-roll: disabilita i precedenti Text+ RMBL e crea la nuova versione su una video track superiore, nominata `RMBL TEXT vN`.
- **SOLO SUBS** non tocca media/B-roll: disabilita i precedenti Subtitle item riconosciuti come RMBL e crea una nuova Subtitle track `RMBL SUBS vN`.
- L'inserimento selettivo dei subs verifica esplicitamente che Resolve abbia materializzato il nuovo SRT sulla track richiesta; se non lo fa, il job fallisce e il ripristino automatico dal backup protegge la timeline attiva.
- Il bridge conserva la modalità selezionata durante il proprio auto-restart.


### Preservazione marker Resolve v0041

- Correzione regressione: i marker della timeline non vengono più cancellati e ricreati ad ogni Apply.
- Se il dizionario marker dopo l'operazione è già identico allo snapshot iniziale, RMBL non esegue alcuna chiamata `DeleteMarkerAtFrame` / `AddMarker`.
- Il restore via API viene usato solo come fallback quando Resolve ha realmente modificato i marker; dopo il restore viene verificata nuovamente l'equivalenza completa di frame e metadati.
- Il risultato del job espone `markers_restored` per distinguere il caso normale (nessun rewrite) dal fallback.


### Bridge riutilizzabile e SOLO MEDIA v0042

- Il pacchetto ricevuto dal Bridge non viene più consumato dopo il primo Apply: dopo un invio completato resta disponibile per ulteriori invii selettivi.
- L'interfaccia usa un pulsante grande **INVIA TUTTO** e, sotto, tre azioni compatte orizzontali: **SOLO SUBS**, **SOLO FRASI**, **SOLO MEDIA**.
- **SOLO FRASI** e **SOLO SUBS** mantengono la logica non distruttiva già introdotta: i precedenti elementi RMBL vengono disattivati e le nuove versioni vengono create su tracce superiori dedicate.
- **SOLO MEDIA** non tocca frasi, sottotitoli o clip utente. Rimuove soltanto i precedenti B-roll identificati come RMBL (il backup BCK resta la rete di sicurezza) e riusa preferibilmente le stesse tracce media, così il nuovo B-roll non sale sopra ai Text+.
- Se non esistono ancora tracce media RMBL riutilizzabili, vengono create soltanto le nuove video track necessarie.
- Gli handoff completati possono rientrare nello stato `applying`; `application_count` registra quante applicazioni sono state eseguite dallo stesso pacchetto.
- I pacchetti completati della stessa sessione Bridge restano discoverable anche dopo l'auto-restart del Bridge.


### Fallback Subtitle track Resolve 21.1 v0043

- Test reale: Resolve 21.1 può ignorare `trackIndex` quando un SRT nativo viene passato a `MediaPool.AppendToTimeline`, materializzando correttamente i nuovi caption su ST1 invece che sulla Subtitle track superiore richiesta.
- `SOLO SUBS` tenta ancora la traccia superiore, ma non considera più il fallback di Resolve un errore se i nuovi subtitle item sono stati creati correttamente.
- La verifica finale viene eseguita sugli item appena creati (testo + frame assoluti), non sull'intera traccia, così i precedenti subs RMBL disattivati non causano falsi mismatch.
- Se la traccia superiore appena creata resta vuota a causa del fallback, viene rimossa.
- Il risultato espone `subtitle_track_index` e `subtitle_track_fallback`; il Bridge segnala il fallback all'utente.
- Il backup BCK resta obbligatorio prima di ogni Apply.


### B-roll preview anchor + interruzione Bridge v0044

- Correzione B-roll: quando Resolve usa il file sorgente completo, il punto visibile non riparte più da frame 0. Il piano conserva `source_start_seconds/source_end_seconds` del frammento verificato mostrato nell'app e lo usa come ancora assoluta del ritaglio.
- Il conformed media aggiunge le maniglie attorno a quell'ancora; `source_start_frame` nel file con handles punta quindi allo stesso punto visto nella preview. I campi diagnostici `selected_source_start_frame_absolute`, `selected_source_end_frame_absolute` e `conformed_cut_start_frame_absolute` rendono verificabile l'allineamento.
- Per i selezionati Pexels, TikTok, Instagram, YouTube Shorts e YouTube normale viene preferito/scaricato il full source quando disponibile; Envato/full locali vengono riconosciuti distinguendoli dal file preview.
- Il Bridge espone **INTERROMPI OPERAZIONE** durante un Apply. L'interruzione è cooperativa e sicura: viene scritto un cancel request, il helper si ferma al primo checkpoint e, se la timeline attiva era già stata mutata, il normale rollback ripristina il backup `BCK`.
- Uno stato `cancelled` resta riutilizzabile: lo stesso pacchetto può essere reinviato con TUTTO / SOLO SUBS / SOLO FRASI / SOLO MEDIA.
- Dopo la pressione di Interrompi il pulsante resta disabilitato mentre compare `Interruzione richiesta · attendo il ripristino sicuro della timeline…`.


### Layout azioni selettive Bridge v0045

- Sotto il pulsante grande **INVIA TUTTO** il Bridge mostra esattamente tre pulsanti orizzontali della stessa larghezza: **SOLO SUBS**, **SOLO FRASI**, **SOLO MEDIA**.
- Le tre colonne usano una griglia Tk uniforme per garantire dimensioni identiche indipendentemente dalla lunghezza dell'etichetta.
- **SOLO MEDIA** chiama esplicitamente lo scope `media`: aggiorna soltanto i B-roll, senza reinserire frasi o sottotitoli.


### SOLO SUBS: conflitto tra destinazione e lock ST1 — v0046

- Root cause nel percorso v0040-v0045: protect_existing_tracks bloccava ST1,
  mentre insert_native_subtitles sbloccava soltanto ST2 richiesta. L'importatore
  SRT nativo poteva restituire un valore truthy ma non inserire alcun caption.
- SOLO SUBS ora riserva una nuova ST1 vuota con AddTrack("subtitle", {"index": 1})
  PRIMA degli snapshot e dei lock. Le vecchie tracce sottotitoli passano a ST2,
  ST3, ecc.; identità, testi, frame e lock vengono verificati e conservati.
- I vecchi subs RMBL rimangono disattivati, non eliminati. La nuova ST1 riceve
  un normale AppendToTimeline([subtitle_media]), senza il trackIndex ignorato.
- Se Resolve ignora l'inserimento indicizzato della traccia, non viene eseguito
  l'append su una ST1 occupata. Il percorso di errore conserva il backup BCK.
- Il file SRT include la differenza fra IN corrente e inizio timeline: non si
  basa sulla posizione del playhead e non modifica marker o tracce video/audio.
- La modifica non tocca il layout del Bridge, SOLO MEDIA o le maniglie B-roll.
- Regressioni testate nel simulatore dell'importatore nativo: ST1 bloccata,
  trackIndex ignorato, invii consecutivi, vecchi caption conservati, IN non-zero,
  marker invariati, lock ripristinati e rifiuto delle destinazioni non sicure.
- Verifica su Resolve reale richiesta: i test automatici non aprono Resolve.

## v0059 — CUT preservazione testo
Il testo completo mantenuto è visibile anche per frasi senza ripetizioni. Protezione conservativa delle continuazioni lunghe non corrispondenti alle altre take; conservate e segnalate invece di essere eliminate. Proposta 20662ddac185 ricostruita conservando le scelte e con backup del piano. 21 test CUT passati.

## v0060 — Revisione CUT nel testo
Box completo interattivo con take evidenziate apribili, esclusioni manuali per intervalli di indici parola originali e ripristino delle parole barrate. Le esclusioni sono persistenti nel piano, applicate prima della mappa temporale/render e preservate durante il riallineamento. Anteprima e conferma sotto il box. Nessuna chiamata AI per queste modifiche.

## v0061 — CUT compatto
Primo clic esclude/ripristina subito una parola; secondo clic estende la stessa operazione al range. Evidenziazioni continue con spazi inclusi. Hover/focus mostra Take alternative; dialog nativo per una sola frase, scelta e ascolto indipendente dal player anteprima. Nessun elenco permanente delle frasi ripetute.

## v0062 — Confini semantici delle take
Revisione semantica prima della scelta take: ogni range deve rappresentare solo il concetto comune; nuovi concetti separati restano indipendenti e conservati, frammenti non equivalenti non offerti come alternative. Verifica strutturale: risposta completa, range solo sottointervalli originali; remap scelte. VERIFICA CONFINI TAKE ripara un piano salvato senza perdere esclusioni o scelte; backup automatico. Usa Groq, nessuna chiamata Codex.

## v0063 — Anteprima CUT post conferma
Progetti CUT derivati possono riprodurre il proprio clean.mp4 dal pulsante anteprima, anche senza piano draft, senza nuovo render/AI. Motivo visibile e tooltip quando anteprima disabilitata.

## v0064 — Revisione ripartenze residue
Secondo pass sul testo mantenuto per correzioni parziali/non letterali e ripetizioni mancate. Aggiunte validate, nessuna sovrapposizione con scelte esistenti; esclusioni mantenute, backup. VERIFICA RIPARTENZE ripara piani salvati. Durata originale/CUT visibile anche su progetto confermato; player take etichettato sorgente integrale.

## v0065 — Pause reel reversibili
ELIMINA PAUSE LUNGHE prima anteprima: gap >0.45 s, respiro di 0.06 s per lato, soli tempi senza cambiare parole/selezioni. Spunta verde al salvataggio e secondi rimossi. RIPRISTINA PAUSE riapplica i parametri normali conservati; stato tight persistente in review/riallineamento/ripartenze/confini. Nessuna chiamata AI.

## v0066 — SOFT/STRONG e silenzi misurati
ELIMINA PAUSE con selettori SOFT/STRONG sotto. Rileva silenzi reali con ffmpeg -40 dB, minimo 0.15 s; soft taglia >0.45 s lasciando 0.06 s per lato, strong >0.18 s con 0.04 s per lato. Non dipende solo dai gap ASR. Intervalli misurati persistiti nel piano e preservati da tutte le review. Ogni parola ASR assegnata una sola volta al segmento con maggior parte sopravvissuta: niente duplicazioni quando il timestamp attraversa un silenzio. Revert ricostruisce tempi normali.

## v0067 — MEDIUM e protezione finali brevi
SOFT/MEDIUM/STRONG rispettivamente soglia 0.45/0.30/0.18 s, margini 0.10/0.08/0.06 s. Protezione parole brevi <=0.35 s quando un confine del silenzio misurato le attraversa: conserva timestamp completo e 0.04 s extra. Risolve via a sorgente 77.76–78.02. Algoritmo pause v3, riapplicare per anteprima aggiornata.

## v0068 — Domande ripetute e regia residua
La revisione riceve candidati locali di ripetizioni 4–12 parole con normalizzazione modal verbs e confini frase, senza auto-tagli. Riceve anche anomalie ASR parole >1.8 s e indicazioni per distinguere conferme di regia. Caso utente: tre domande non bisogna/dobbiamo più scattare, esatto esteso 14 s.

## v0069 — CUT entro quota Groq 8k TPM
Tutte le fasi CUT segmentate: riconoscimento con finestre fino 300 parole e overlap60, confini con take compattate e batch10, scelta batch5 con contesto locale, residuali220 parole. Indici assoluti; merge/dedup range, conflitti conservativi. Completion CUT cap2600, reasoning medium. Limitatore locale rolling60s 7500 token conservativi, conto alla rovescia via job, retry429 limitato. Cache JSON per hash prompt/schema in cut/api-cache per riprendere i blocchi riusciti. Nessun DEV richiesto. Client generale Groq conserva il default; override solo CUT.

Le sovrapposizioni dei risultati residui vengono unite in modo conservativo: gruppi già gestiti mantenuti, scarti limitati alle parole libere, scelte manuali protette. Cache per riallineamento ASR di finestre; su 429/413 del solo affinamento opzionale conserva timestamp misurati e segnala diagnostica, senza bloccare il piano.

## v0070 — UNDO/REDO esclusioni CUT
Pulsanti accanto ESCLUDI DAL CUT, cronologia fino100 modifiche alle esclusioni nella sessione. Salvataggio solo riuscito crea history; errori undo/redo non consumano stack. Nuova esclusione azzera redo; cambio progetto/sorgente azzera cronologia. Restano invariati scelte take e preset pause.
