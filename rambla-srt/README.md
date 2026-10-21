# RAMBLA SRT Range Exporter — handoff Codex

**Stato:** implementazione Lua V3.1 attualmente distribuita come `Workspace > Scripts > Utility > RAMBLA_SRT_Range`. Questo commit documenta il contratto funzionale e la migrazione desiderata a una Workflow Integration dedicata, senza alterare AutoCut. Le funzionalità segnate come future NON sono già implementate.

**Sorgente di riferimento esatto:** pacchetto `RAMBLA_SRT_V3_1_WINDOWS_MAC.zip` generato in conversazione ChatGPT del 21/10/2026, file `Plugin/RAMBLA_SRT_Range.lua` (21.487 byte). Se non è disponibile nella checkout locale, recuperarlo dall'artefatto prima di implementare. Non inventare un suo equivalente e non dichiarare regressioni superate senza confrontare l'output reale.

## Comportamento V3.1 da preservare

- DaVinci Resolve Studio 21 su Windows e macOS.
- Lettura dalla timeline attiva e dalla/e traccia/e `subtitle`; mai modificare timeline, clips, tracks, media, markers o progetto.
- Stato se IN e/o OUT mancano: `IN - OUT not found`. Visualizzare IN, OUT, durata in `HH:MM:SS:FF`, frames e secondi.
- **SINGLE**: senza intervalli memorizzati, esporta solo il corrente IN/OUT. La modalità finale deve avere selettore SINGLE/MULTI esplicito, con SINGLE iniziale e comportamento V2.5 invariato.
- **MULTI**: pulsante aggiungi l'attuale IN/OUT; tutti gli intervalli devono appartenere allo stesso `timeline.GetUniqueId()` e progetto; mostra lista; rimuovi intervallo/svuota; ordinamento cronologico; unione overlap e adiacenze; evitare caption duplicate.
- Una cartella selezionabile, nome file facoltativo (automatico se mancante), export di un solo `.srt`; pulsante `APRI CARTELLA` dopo successo.
- Checkbox **Mantieni timecode originali della timeline** attivo di default. Alternativa timecode azzerati. Rispettare timeline start timecode, framerate e, dove presente, drop-frame; per MULTI a zero definire esplicitamente concatenazione o offset rispetto al primo IN e testarla.
- Checkbox comune **Aggiungi testo completo della timeline in coda**, disattivato di default; se attivo aggiungere nel MEDESIMO file SRT il blocco `# RAMBLA_CONTEXT_BEGIN` / `# RAMBLA_CONTEXT_END` con tutte le caption della timeline e una chiara istruzione che il contesto non richiede B-roll. NON produrre file contesto separati.
- I commenti `#` non appartengono allo standard SRT: opzione sperimentale; verificare come Resolve e parser esterni reagiscono e mostrare avviso quando attiva.
- Dati Lua speciali `__flags` possono comparire nell'enumerazione `GetItemListInTrack`: non trattarli come clip. Non assumere che tutti i valori della tabella siano oggetti.
- Nessun cloud, AI, trascrizione, ASR o render Deliver per questa utility.

## Migrazione

Creare una nuova `Workflow Integration` indipendente `com.rambla.srt`, non un modulo integrato in `com.rambla.autocut`. Riutilizzare da `autocut-standalone` solo scheletro plugin Electron/native SDK, tema e approccio installer/updater; **non** copiare vincolo single-full-video, worker ASR, CUT, editing o suoi path/credenziali. Per prima cosa verificare nella SDK di Resolve 21 se GetItemListInTrack('subtitle') e TimelineItem.GetName/GetStart/GetEnd sono accessibili via modulo `WorkflowIntegration.node` nel processo Electron. Se non lo sono, prevedere un helper locale read-only con scripting API e comunicazione vincolata, invece di aggirare il problema silenziosamente.

Isolare adattatore Resolve, logica degli intervalli, renderer SRT, UI ed updater. Salvataggio dello stato per timeline/progetto e verifica del fingerprint prima dell'export. Non aggiornare o sovrascrivere nessun file AutoCut.

## Release & aggiornamenti

Namespace release separato `srt-*`, versioni semver, manifest e SHA-256, allowlist stretta, limitazione path traversal/symlink/size, backup atomico e rollback; aggiornamento manuale `AGGIORNA` nella GUI dopo controllo versione; niente update quando export attivo, niente riavvio non richiesto di Resolve. Update della SDK nativa o dipendenze strutturali tramite installer, non hot reload. Offline funziona. Installer/riparazione Windows+Mac; firma/notarizzazione per distribuzione Mac. Preservare dati e preferenze.
