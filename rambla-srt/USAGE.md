# RAMBLA SRT 3.2.2 — candidata al collaudo

Workflow Integration autonoma `com.rambla.srt`. AutoCut e lo script Utility V3.1 non vengono sostituiti. Nessun cloud/AI/ASR, Python, Node o download di dipendenze richiesto all'utente: usa Electron e SDK già inclusi in Resolve Studio 21.

## Installazione e riparazione

Chiudi solo eventuali finestre RAMBLA SRT. Estrai tutta la cartella del pacchetto.

- Windows: doppio clic su `INSTALLA_WINDOWS.cmd`. Se la cartella di sistema richiede privilegi, Windows mostra UAC. L'installer verifica SHA-256, copia l'SDK locale, mantiene un backup del solo plugin SRT e concede al tuo account l'accesso per i successivi aggiornamenti del solo plugin.
- Mac: esegui `INSTALLA_MAC.command`. Se il file estratto non è eseguibile, usa `/bin/bash` seguito dal percorso del file nel Terminale. L'accesso alla cartella `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins` può richiedere la password amministratore. Non modificare Gatekeeper o quarantena. Questa candidata non è firmata/notarizzata: per distribuzione pubblica serve il pacchetto firmato descritto in `MAC_DISTRIBUTION.md`.

Apri **Workspace > Workflow Integrations > RAMBLA SRT**. Resolve enumera i plugin all'avvio: dopo la prima installazione può essere necessario salvare il lavoro e riavviare Resolve manualmente. Non viene riavviato dall'installer.

La riparazione ripete lo stesso installer. Il codice precedente è conservato in `RAMBLA SRT Install Backups`, accanto alla cartella `Workflow Integration Plugins`, fuori dalla scansione dei plugin. Un errore nella sostituzione ripristina la cartella precedente. Nessun downgrade automatico. Lo script `Utility/RAMBLA_SRT_Range.lua` non viene letto, cancellato o sostituito.

## Esportazione

1. Apri la timeline con sottotitoli e imposta IN/OUT in Resolve.
2. RAMBLA SRT si apre sempre in **SINGLE RANGE**. Premi **AGGIORNA IN / OUT** dopo modifiche alla timeline o ai marker.
3. Per più intervalli, passa a **MULTI RANGE**, aggiungi ciascun IN/OUT e rimuovi/svuota quelli indesiderati. L'export ordina e unisce intervalli adiacenti o sovrapposti.
4. Scegli cartella e nome facoltativo. Un file già esistente non viene sovrascritto: cambia nome.
5. Timecode originali attivi per default; disattivali per partire da zero. In MULTI i segmenti si concatenano senza le pause tra intervalli, come V3.1.
6. Il contesto opzionale aggiunge nello stesso SRT l'intera trascrizione in un unico paragrafo, senza timecode o elenco intervalli, delimitata da commenti `#`. È sperimentale e non standard: alcuni parser inglobano il contesto nell’ultimo sottotitolo (verificato con FFmpeg). Per reimportare in un editor, lascialo disattivato.
7. Premi **ESPORTA SRT**, poi **APRI CARTELLA**. **COPIA SRT** copia negli appunti lo stesso SRT con le opzioni correnti, senza creare file o richiedere una cartella.

Le opzioni e gli intervalli sono salvati atomicamente per ID di progetto/timeline. Il cambio di timeline, dei tempi o dei sottotitoli viene rilevato prima dell'export. La UI indica errori di salvataggio; non considera un salvataggio fallito come riuscito.

## Aggiornamenti indipendenti

**AGGIORNA** cerca esclusivamente release stabili `srt-X.Y.Z` di `azza0101/rambla-reel-director`. Mostra la versione; **INSTALLA AGGIORNAMENTO** è un'azione esplicita. Non aggiorna durante export e non tocca SDK, dati, AutoCut o Resolve. Dopo un aggiornamento chiudi e riapri solo RAMBLA SRT. Non viene effettuato hot reload del modulo nativo.

La release contiene `srt-update.json` e `RAMBLA-SRT-X.Y.Z.json`: bundle JSON/base64 con elenco file esatto e SHA-256, equivalente al controllo ZIP di AutoCut senza estrazione di archivi. Dimensioni, versioni, identità, file e dipendenze sono verificati. Backup, journal di applicazione e rollback gestiscono errori e aggiornamenti interrotti. Non pubblicare la candidata come release stabile finché il collaudo non è concluso.

Repository privato: il controllo può restituire 404. Per gli ambienti di distribuzione privati si può fornire `RAMBLA_SRT_GITHUB_TOKEN` nell'ambiente di avvio di Resolve (token con accesso di sola lettura ai contenuti del repository). Il plugin non lo salva, esporta o mostra. Senza token dedicato o login GitHub CLI le esportazioni rimangono disponibili offline. Se la variabile dedicata non è impostata, il plugin usa il login GitHub CLI già presente (`gh auth token --hostname github.com`), come il canale AutoCut. Il token resta solo in memoria e non viene inoltrato ai redirect degli asset. Nessun file credenziali AutoCut viene letto o modificato. Per distribuzione non tecnica predisporre asset pubblicamente leggibili o un canale autenticato concordato; il plugin non include un login GitHub.

## Dati e rollback

- Windows: `%APPDATA%/RAMBLA/SRT`.
- Mac: `~/Library/Application Support/RAMBLA/SRT`.
- Preferenze: `state.json`; backup aggiornamenti: `update-backups`.
- Un file stato corrotto è conservato e segnalato: con plugin chiuso rinominalo per ripartire.
- Ripristino manuale installer: con plugin chiuso sposta l'attuale `com.rambla.srt` e rimetti al suo posto la cartella backup scelta. Non toccare altre cartelle.
- SDK o dipendenze strutturali cambiati richiedono un installer nuovo; l'updater di codice li rifiuta.

## Semantica V3.1 conservata

Il Lua originale è in `reference/v3.1`, immutato. Confronto automatico su 40 output del Lua. La V3.1 tratta OUT come limite esclusivo e usa una regola euristica per gli IN/OUT relativi. AutoCut documenta OUT inclusivo: qui **non** è stata importata quella correzione. Questa differenza di un frame e il caso di timeline molto lunghe richiedono collaudo nell'host e una decisione esplicita prima di cambiare il contratto. I timecode SRT usano l'origine HH:MM:SS più i frame reali / fps, inclusi framerate frazionari e DF, come il sorgente fornito.

## Test sviluppo

`node --test tests/*.test.cjs` esegue logica, adapter, stato, updater e installer Windows in directory temporanee. `python tests/generate_oracle.py` richiede `lupa` solo nell'ambiente test e rigenera le fixture eseguendo il Lua originale, con UI/Resolve simulati. `tests/ui-smoke.cjs` richiede Playwright e un browser Edge di test; usa la Session reale, un adapter di prova e directory QA.

`node tools/build-release.cjs` genera `dist/` da una allowlist. Il modulo nativo Blackmagic, i salvataggi, i media, i log, i token e le trascrizioni reali non entrano nel pacchetto. Vedi `VALIDATION.md` per le verifiche eseguite e quelle ancora necessarie.

Dalla 3.2.2, su richiesta dell’utente, il contesto differisce dalla V3.1: testo continuo in ordine temporale, spazi normalizzati, senza timecode generati. Il corpo SRT selezionato resta invariato. Vale anche per COPIA SRT.
