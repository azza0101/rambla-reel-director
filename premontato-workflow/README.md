# RAMBLA Premontato

Da Resolve Studio, il pannello legge la selezione corrente del Media Pool e la timeline di riferimento. Il worker locale confronta le trascrizioni Resolve con il copione, individua la scena corrispondente, propone i confini delle take e prepara una nuova timeline di revisione. I file originali restano invariati. L’analisi dei volti/inquadrature usa OpenCV localmente; SFace confronta localmente i volti e propone gruppi anonimi. I nomi dei personaggi richiedono conferma sulle still. Non invia media, impronte facciali o copione a servizi cloud.

Il primo target è Windows x64 e una camera. La logica del worker non assume un solo file per take: gestisce anche più take nel medesimo file quando i confini sono confermati. Multicam resta fuori dal prototipo. Campo, intervallo, alternativa, pause e personaggi visibili sono correggibili dal pannello.

## Creare il pacchetto

Eseguire `tools/build_installer.ps1`. Il comando crea `dist/Install-Premontato.exe` includendo Python 3.13 embeddable e le dipendenze bloccate in `runtime/requirements.lock`; servono PowerShell, Python con pip, il compilatore .NET Framework incluso in Windows e accesso ai download ufficiali di python.org e PyPI. I pacchetti vengono verificati con SHA-256 e il build verifica che OpenCV esponga `CascadeClassifier` e il modello Haar per le stime d’inquadratura. Il launcher usa il .NET Framework già fornito da Windows e non lo ridistribuisce. Non viene incluso `WorkflowIntegration.node`: il setup lo copia dall’SDK locale di Resolve oppure chiede di selezionarlo. Resolve Studio deve essere chiuso e riavviato per registrare l’integrazione.

L’installer chiede elevazione solo per scrivere sotto ProgramData. Crea un backup se trova già `com.rambla.premontato`.

La versione 0.7.0 mostra avanzamento e stato delle otto fasi di analisi, contatori per clip/still e tempo trascorso. Nelle operazioni senza percentuale interna disponibile la barra della fase rimane indeterminata. La trascrizione Resolve mostra il completamento per clip.

Prima della timeline, la revisione visiva mostra due still per intervallo di massimo dieci secondi. Assegna i gruppi di volti ai personaggi del copione e correggi campo e personaggi visibili in ogni intervallo. La stessa persona può comparire in più gruppi; volti piccoli, profili e occlusioni possono restare incerti. Le identità suggerite non diventano vincoli del montaggio senza conferma. Il piano preferisce, fra corrispondenze di testo comparabili, le riprese che mostrano il personaggio confermato; segnala copertura sconosciuta o fuori campo. Non riconosce automaticamente il parlante dal labiale. Le conferme valgono per l’analisi corrente e vanno ripetute dopo una nuova analisi o riapertura; le still sono conservate nella cache locale per impronta del file.

Il pulsante **Aggiorna** cerca le release private `premontato-vX.Y.Z` del repository GitHub, scarica il pacchetto versionato e ne verifica SHA-256 prima di installarlo. Per autenticarsi riusa in memoria la credenziale DPAPI già registrata da RMBL Auto-Cut; non la copia nell’installer né la salva nel plugin. Servono Auto-Cut installato e un token con lettura delle release. Windows mostra UAC per aggiornare i file in ProgramData. Il bridge `WorkflowIntegration.node` e i dati utente restano intatti; dopo l’aggiornamento chiudi e riapri il pannello da Resolve.

Il pulsante **Invia debug** prepara un registro tecnico locale limitato, senza messaggi degli errori, copione, trascrizioni, file o nomi dei media. Mostra il report prima dell’invio e richiede una conferma esplicita per creare un issue nel repository privato; usa GitHub CLI già autenticata (`gh auth status`) senza incorporare o salvare token. Installa GitHub CLI e accedi con `gh auth login` per usare questa funzione. L’invio reale non è mai automatico.

L’installer è Windows x64; macOS non è ancora predisposto.

## Test e limiti

`node --test tests/unit/*.test.cjs` e `python -m pytest tests/unit -q` coprono adattatore Resolve, protocollo locale e selezione delle take. La pipeline GitHub Actions produce un EXE scaricabile come artifact dopo i controlli. L’EXE locale e il worker possono essere provati senza Resolve; il caricamento del pannello, le chiamate API contro il progetto reale e l’inserimento di una timeline devono essere collaudati in Resolve Studio.

La documentazione SDK locale descrive il caricamento dei workflow plugin ma non chiarisce diritti di ridistribuzione per `WorkflowIntegration.node`. Per questo il binario non viene pubblicato né incorporato nell’installer. Gli avvisi delle dipendenze Python sono in `runtime/THIRD_PARTY_NOTICES.txt` e nelle metadata delle wheel distribuite.
