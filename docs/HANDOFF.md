# RMBL B ROLL — handoff tecnico

Aggiornato: 2026-10-09  Versione: `v0049`  Branch di consegna: `feat/api-first-text-first-v1`

## Avvio rapido

- App: `RMBL_B_ROLL_APP.vbs` oppure `python launch_local_v5.py start`.
- Bridge Resolve: `Workspace → Scripts → RAMBLA_B_ROLL`.
- Backend: `backend/app/curation_server.py`.
- UI prodotto: `backend/app/curation_ui_v2.py`, con moduli UI separati per trascrizione, visual beat ed export.
- Bridge nativo: `tools/resolve_bridge/standalone_bridge.py`.
- Versione unica app/bridge: `RAMBLA_VERSION`.

## Flusso Resolve

1. Il bridge mantiene un heartbeat con il backend locale e rileva la timeline focalizzata.
2. **USA AUDIO IN RMBL B ROLL** invia audio e intervalli video esistenti; l'audio può essere riutilizzato solo se la firma della timeline coincide.
3. L'app prepara un handoff senza modificare Resolve.
4. Il bridge riceve il pacchetto nella stessa sessione, si espande e abilita **APPLICA**.
5. La modalità predefinita crea un backup timestampato in `BCK` e applica direttamente alla timeline attiva usando l'IN corrente.

Il bridge espone anche **RICALCOLA AUDIO · IN → OUT**: invia `force_recalculate=true`, impedisce il riuso della guida precedente e renderizza il range IN/OUT letto dalla timeline focalizzata in quel momento. Resolve 21 restituisce i mark relativi all'inizio timeline e può omettere `in` quando coincide con l'inizio: `timeline_range()` normalizza entrambi i casi in frame assoluti. Il ricalcolo forzato rifiuta di partire se non vede almeno un range esplicito, evitando il fallback silenzioso all'intera timeline. Il riepilogo mostra `mark_in`, `mark_out` e `range_source` realmente acquisiti.

La timeline sorgente resta protetta. Le mutazioni Resolve passano dai job di `resolve_handoff_jobs.py`; i calcoli temporali usano FPS e frame iniziale della timeline acquisita.

### Fusion Title sicuri v0049

- `KURA_paper_title_v9` è verificato direttamente in Resolve 21.1: il nome registrato è corretto e il preset viene caricato.
- L'API `InsertFusionTitleIntoTimeline` inserisce sempre su V1: con V1 protetta fallisce, con V1 libera esegue un insert edit e sposta le clip esistenti.
- RMBL genera quindi le parole evidenziate in una timeline trasparente isolata che eredita FPS e timecode dalla sorgente, poi la annida esplicitamente sulla traccia `RMBL TEXT` più alta.
- Il livello annidato è giallo, aggiornabile dalle revisioni successive e non modifica clip, audio o marker esistenti.
- Prova reale su `KURA parlato / KURA_FOTO BAMBINI_v2`: 24 titoli v9, livello su V13, 30 fps, backup BCK creato e verifica di integrità superata.

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
