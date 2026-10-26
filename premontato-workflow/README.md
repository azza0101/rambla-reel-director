# RAMBLA Premontato

**0.12.0 — Catalogazione giornata, build di prova:** inventario ricorsivo di un bin, trascrizioni Resolve riusate/progressive, assegnazioni per intervalli con revisione e SELECTS per scena. [Istruzioni e limiti](docs/DAY_CATALOG.md), [collaudo nativo](docs/performance/2026-10-26-day-catalog-validation.md). Il montaggio esistente resta separato.

Da Resolve Studio, il pannello legge la selezione corrente del Media Pool e la timeline di riferimento. Il worker locale confronta le trascrizioni Resolve con il copione, individua la scena corrispondente, propone i confini delle take e prepara una nuova timeline di revisione. I file originali restano invariati. L’analisi dei volti/inquadrature usa OpenCV localmente; SFace confronta localmente i volti e propone gruppi anonimi. I nomi dei personaggi richiedono conferma sulle still. Media e impronte facciali restano locali. Groq, se attivato per il montaggio, riceve i testi; la catalogazione giornata non usa Groq.

Il primo target è Windows x64 e una camera. La logica del worker non assume un solo file per take: gestisce anche più take nel medesimo file quando i confini sono confermati. Multicam resta fuori dal prototipo. Campo, intervallo, alternativa, pause e personaggi visibili sono correggibili dal pannello.

## Creare il pacchetto

Eseguire `tools/build_installer.ps1`. Il comando crea `dist/Install-Premontato.exe` includendo Python 3.13 embeddable e le dipendenze bloccate in `runtime/requirements.lock`; servono PowerShell, Python con pip, il compilatore .NET Framework incluso in Windows e accesso ai download ufficiali di python.org e PyPI. I pacchetti vengono verificati con SHA-256 e il build verifica che OpenCV esponga `CascadeClassifier` e il modello Haar per le stime d’inquadratura. Il launcher usa il .NET Framework già fornito da Windows e non lo ridistribuisce. Non viene incluso `WorkflowIntegration.node`: il setup lo copia dall’SDK locale di Resolve oppure chiede di selezionarlo. Resolve Studio deve essere chiuso e riavviato per registrare l’integrazione.

L’installer chiede elevazione solo per scrivere sotto ProgramData. Crea un backup se trova già `com.rambla.premontato`.

La versione 0.7.0 mostra avanzamento e stato delle otto fasi di analisi, contatori per clip/still e tempo trascorso. Nelle operazioni senza percentuale interna disponibile la barra della fase rimane indeterminata. La trascrizione Resolve mostra il completamento per clip.

Prima della timeline, la revisione visiva mostra due still per intervallo di massimo dieci secondi. Assegna i gruppi di volti ai personaggi del copione e correggi campo e personaggi visibili in ogni intervallo. La stessa persona può comparire in più gruppi; volti piccoli, profili e occlusioni possono restare incerti. Le identità suggerite non diventano vincoli del montaggio senza conferma. Il piano preferisce, fra corrispondenze di testo comparabili, le riprese che mostrano il personaggio confermato; segnala copertura sconosciuta o fuori campo. Non riconosce automaticamente il parlante dal labiale. Le conferme e le bozze vengono salvate nella sessione Premontato e recuperate alla riapertura. Una nuova analisi invalida le conferme; le still sono conservate nella cache locale per impronta del file.

Il pulsante **Aggiorna** cerca le release private `premontato-vX.Y.Z` del repository GitHub, scarica il pacchetto versionato e ne verifica SHA-256 prima di installarlo. Per autenticarsi riusa in memoria la credenziale DPAPI già registrata da RMBL Auto-Cut; non la copia nell’installer né la salva nel plugin. Servono Auto-Cut installato e un token con lettura delle release. Windows mostra UAC per aggiornare i file in ProgramData. Il bridge `WorkflowIntegration.node` e i dati utente restano intatti; dalla versione 0.8.0 il pannello mostra download/verifica/estrazione/installazione e si riavvia automaticamente dopo i salvataggi. Il passaggio iniziale da una versione precedente richiede ancora una riapertura manuale per caricare il nuovo updater.

Il pulsante **Invia debug** prepara un registro tecnico locale limitato, senza messaggi degli errori, copione, trascrizioni, file o nomi dei media. Mostra il report prima dell’invio e richiede una conferma esplicita per creare un issue nel repository privato; usa GitHub CLI già autenticata (`gh auth status`) senza incorporare o salvare token. Installa GitHub CLI e accedi con `gh auth login` per usare questa funzione. L’invio reale non è mai automatico.

L’installer è Windows x64; macOS non è ancora predisposto.

## Test e limiti

`node --test tests/unit/*.test.cjs` e `python -m pytest tests/unit -q` coprono adattatore Resolve, protocollo locale e selezione delle take. La pipeline GitHub Actions produce un EXE scaricabile come artifact dopo i controlli. L’EXE locale e il worker possono essere provati senza Resolve; il caricamento del pannello, le chiamate API contro il progetto reale e l’inserimento di una timeline devono essere collaudati in Resolve Studio.

La documentazione SDK locale descrive il caricamento dei workflow plugin ma non chiarisce diritti di ridistribuzione per `WorkflowIntegration.node`. Per questo il binario non viene pubblicato né incorporato nell’installer. Gli avvisi delle dipendenze Python sono in `runtime/THIRD_PARTY_NOTICES.txt` e nelle metadata delle wheel distribuite.

## Salvare e riprendere un lavoro (0.8.0)

Apri progetto, Salva e Salva con nome gestiscono file .premontato.json. Contengono copione, riferimenti alle riprese, trascrizioni, analisi, still, correzioni confermate e bozze dei campi; non copiano i video. Conserva quindi le riprese nei loro percorsi. I progetti restano locali e non vengono inviati con la diagnostica.

L’autosave scrive dopo le modifiche applicate, dopo le bozze (circa un secondo), ogni minuto mentre il pannello è inattivo e prima della chiusura/aggiornamento. Alla riapertura recupera il lavoro e il file con nome da metadati locali separati. I salvataggi sono atomici; se il file con nome cambia esternamente, il recupero rimane locale e il file esterno non viene sovrascritto automaticamente. Se una ripresa cambia o manca, analisi e trascrizioni precedenti vengono invalidate. Le bozze non diventano tagli finché non premi Applica; la timeline resta bloccata quando restano modifiche da applicare.

Il progetto Resolve viene salvato tramite SaveProject nella libreria attiva: prima dell’aggiornamento, prima/dopo la creazione della timeline e periodicamente quando il pannello è inattivo. Un salvataggio fallito interrompe l’aggiornamento e mostra il motivo; il solo recupero Premontato non sostituisce il salvataggio Resolve. L’aggiornamento richiede ancora l’autorizzazione UAC di Windows. Riavvia solo il processo Electron del pannello, mantenendo gli argomenti originali; Resolve resta aperto. La riconnessione SDK dopo il rilancio dal vero contesto Resolve richiede ancora collaudo.


Premontato 0.10.0: selezione del parlante con Light-ASD TalkSet locale (CPU/ONNX), senza nomi obbligatori. Apertura sulla master, piani stretti con evidenza audio/video e ritorno alla master alla risoluzione suggerita dal profilo VIDEO COLICHE o dai marcatori. Il rilevamento narrativo automatico usa segnali testuali conservativi, non comprende universalmente tensione o intenzioni. Le stime del parlante usano brevi campioni e non garantiscono tutta una battuta. In caso incerto si preferisce una master disponibile; non si inventa copertura.

Still e gruppi SFace si preparano solo con «Apri controllo visivo facoltativo»; le correzioni manuali hanno priorità. Audio PCM mono 16 kHz privato condiviso tra pause e parlante, cache invalidata da modifica delle riprese o del modello. Nessun proxy obbligatorio, servizio cloud o credito esterno.

Il modello ONNX MIT da circa 4 MB è incluso, con provenienza e hash in runtime/models/active-speaker. tools/export_active_speaker.py riproduce la conversione in ambiente di sviluppo separato; Torch non è richiesto né incluso nel plugin.
