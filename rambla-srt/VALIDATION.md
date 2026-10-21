# Verifica della candidata 3.2.1 — 21 ottobre 2026

## Eseguito

- Lua V3.1 originale recuperato dal pacchetto fornito, 21.487 byte, SHA-256 `0ac35af7db4df9cd5d96c0fe9b0e8b9b371e7ac7a60e0c2f71ba20b5e91de17c`. Copia archivio immutata.
- 40 output SRT prodotti eseguendo il Lua originale con UI/API simulate: SINGLE, MULTI fuori ordine/overlap/adiacenze, original/zero, context on/off, Unicode/multilinea, caption ai limiti, start non zero, 23.976/25/30/29.97/59.94 e DF. Confronto byte per byte con JS: tutti uguali. Missing IN/OUT verificato separatamente nel Lua.
- 65 test Node: export, adapter con `__flags`, identità/fingerprint, stato per timeline, errori di scrittura, collisioni file, updater, rollback su errore e recupero dopo interruzione, URL non autorizzati, IPC e lifecycle Electron simulato, installer Windows in cartella temporanea.
- GUI browser Edge headless con Session reale e adapter simulato: export scritto, autosave/reload, SINGLE all'apertura, MULTI/rimozione, contesto, errore rete/offline, nessun errore JS o overflow a 1000/620/496 CSS px. 496 px simula lo spazio utile a 620 px / zoom 125%; non equivale a tutti gli scenari DPI nativi.
- Resolve **21.1.0.17 Windows**: lettura reale delle 2 tracce sottotitoli (70 caption), start 108000 / `01:00:00:00`, 30 fps. Nessun IN/OUT impostato. Otto export su intervalli locali di prova confrontati col Lua: byte identici. Nessuna mutazione Resolve. Snapshot e trascrizioni reali restano solo nella cartella QA locale, esclusi da GitHub e pacchetti.
- Installer Windows eseguito realmente dopo i test: nuova cartella `com.rambla.srt`, SDK copiato dalla distribuzione Resolve locale. AutoCut non modificato; hash dello script Utility installato prima/dopo invariato (`aa6ecaaa1183c3cedca51cdee8bdb04fab11a913175f6c63dafa7ac560196de0`, V2.5).
- Shell Mac e builder `.pkg` controllati sintatticamente con Bash. Simulazione installer sotto Git Bash separata dal collaudo fisico Mac.

## Non ancora validato / release gate aperto

1. **Windows host verificato:** dopo il riavvio manuale, RAMBLA SRT compare separatamente da AutoCut. Avvio e lettura nativa via `WorkflowIntegration.node` riusciti. Sulla copia `RAMBLA SRT QA 2026-10-21`: SINGLE original, SINGLE zero+context e MULTI zero+context con due intervalli disgiunti esportati dalla GUI; tutti e tre identici byte per byte al Lua originale. Apertura cartella riuscita. Chiusura/riapertura: SINGLE iniziale, opzioni e due intervalli persistiti. Timeline originale riattivata, senza alterarne IN/OUT o clip. Copia QA e due SRT importati restano nel progetto per ispezione. Il probe esterno falliva perché non avviato dall'host; non occorre un helper Python.
2. **Import con footer:** Resolve ha accettato nel Media Pool entrambi i file, con/senza contesto. Non ancora verificato il round-trip completo sulla traccia subtitle. FFmpeg/ffprobe legge 10 cue da entrambi, ma ingloba il footer nell'ultimo cue (2948 byte contro 27 senza contesto). Il contesto resta quindi sperimentale, disattivato per default e sconsigliato per reimportazione; il comportamento originale non è stato alterato.
3. **macOS reale:** non disponibile in questa sessione. Restano caricamento SDK su Apple Silicon/Intel, dialoghi/percorsi, permessi dopo installazione amministratore, export, update, firma e notarizzazione. Builder firmato presente; nessun certificato/ticket simulato o dichiarato ottenuto.
4. **Aggiornamento online end-to-end:** architettura e transazione testate, ma nessuna release stabile `srt-*` pubblicata. Repo privato: accesso dedicato richiesto, nessun token AutoCut copiato. Controllo AGGIORNA provato nell'host: errore repository privato/release non disponibile correttamente mostrato, senza modifiche. Applicazione di una release online e successiva riapertura restano da collaudare.
5. **OUT inclusivo:** preservata la semantica esclusiva del Lua V3.1. La documentazione AutoCut usa OUT inclusivo; il comportamento al frame limite e l'euristica relative/absolute sulle timeline molto lunghe richiedono decisione di compatibilità prima di eventuale variazione.

La candidata non è una release finale validata su entrambe le piattaforme. Nessun merge, sostituzione dello script Utility o modifica ad AutoCut è autorizzato dal superamento dei soli test simulati. La V3.1 originale resta disponibile in archivio.

## Modifiche 3.2.1
COPIA SRT con validazione timeline/IN-OUT identica all’export e senza destinazione obbligatoria. Test IPC clipboard e GUI aggiunti. AGGIORNA usa il login GitHub CLI esistente se manca il token dedicato; verifica online sul repository riuscita, stato `unpublished` perché non esistono ancora release SRT. Messaggi Electron ripuliti dal prefisso tecnico. Nessuna release AutoCut selezionata.

Verifica nativa 3.2.1: AGGIORNA mostra «Nessun aggiornamento SRT pubblicato» dopo accesso riuscito; COPIA SRT mostra «SRT copiato negli appunti» senza cartella impostata. Installer 3.2.1 eseguito con backup del solo SRT.

## Modifica 3.2.2 — contesto fluido
Richiesta esplicita utente: rimosse dal footer le righe di timecode e gli intervalli. Trascrizione completa in un unico paragrafo, con spazi e a-capo normalizzati. Test dedicato per ordine, assenza di metadati temporali e corpo SRT invariato. I confronti V3.1 da questa versione verificano il corpo sottotitoli, non il footer modificato intenzionalmente. 66 test Node superati.
