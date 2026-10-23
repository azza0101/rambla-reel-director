# RAMBLA Premontato

Da Resolve Studio, il pannello legge la selezione corrente del Media Pool e la timeline di riferimento. Il worker locale confronta le trascrizioni Resolve con il copione, individua la scena corrispondente, propone i confini delle take e prepara una nuova timeline di revisione. I file originali restano invariati. L’analisi dei volti/inquadrature usa OpenCV localmente; non effettua identificazione biometrica e non invia media o copione a servizi cloud.

Il primo target è Windows x64 e una camera. La logica del worker non assume un solo file per take: gestisce anche più take nel medesimo file quando i confini sono confermati. Multicam, correzione dei campi dal pannello e selezione manuale delle alternative sono ancora fuori dal prototipo.

## Creare il pacchetto

Eseguire `tools/build_installer.ps1`. Il comando crea `dist/Install-Premontato.exe` includendo Python 3.13 embeddable e le dipendenze bloccate in `runtime/requirements.lock`; servono PowerShell, .NET SDK 8 e accesso ai download ufficiali di python.org e PyPI. I pacchetti vengono verificati con SHA-256. Non viene incluso `WorkflowIntegration.node`: il setup lo copia dall’SDK locale di Resolve oppure chiede di selezionarlo. Resolve Studio deve essere chiuso e riavviato per registrare l’integrazione.

L’installer chiede elevazione solo per scrivere sotto ProgramData. Crea un backup se trova già `com.rambla.premontato`. Non legge le credenziali GitHub, non le salva e non modifica progetti o timeline Resolve. L’installer è Windows x64; macOS non è ancora predisposto.

## Test e limiti

`node --test tests/unit/*.test.cjs` e `python -m pytest tests/unit -q` coprono adattatore Resolve, protocollo locale e selezione delle take. La pipeline GitHub Actions produce un EXE scaricabile come artifact dopo i controlli. L’EXE locale e il worker possono essere provati senza Resolve; il caricamento del pannello, le chiamate API contro il progetto reale e l’inserimento di una timeline devono essere collaudati in Resolve Studio.

La documentazione SDK locale descrive il caricamento dei workflow plugin ma non chiarisce diritti di ridistribuzione per `WorkflowIntegration.node`. Per questo il binario non viene pubblicato né incorporato nell’installer. Gli avvisi delle dipendenze Python sono in `runtime/THIRD_PARTY_NOTICES.txt` e nelle metadata delle wheel distribuite.
