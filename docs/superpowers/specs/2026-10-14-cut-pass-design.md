# CUT opzionale — specifica plugin

## Obiettivo approvato

Pulire un video parlato prima del workflow B-roll, conservando l'ultima take completa di ogni frase ripetuta e la penultima come alternativa. Prima fase esclusivamente nel plugin; nessuna operazione sulla sessione Resolve durante lo sviluppo.

Caso reale: progetto `20662ddac185`, `TEST-autocut_v1`, sorgente `IMG_1545.MOV`, 185.52 secondi, 30 FPS, 1080×1920. Guida audio già estratta: 185.364 secondi. La differenza audio/video deve essere verificata e non deve troncare automaticamente la coda.

## Flusso

Pass opzionale CUT fra caricamento sorgente e revisione/selezione parole. Trascrizione integrale con timestamp misurati per parola, analisi dei tentativi, proposta modificabile, ascolto originale e anteprima concatenata del montaggio pulito. Il workflow normale usa il testo pulito solo dopo conferma esplicita della proposta.

## Decisioni editoriali

Riconoscere tentativi consecutivi della stessa frase, comprese ripartenze parziali, senza eliminare ripetizioni intenzionali o frasi simili che aggiungono informazioni. Conservare l'ultimo tentativo completo; gli accoppiamenti incerti restano visibili per revisione. Conservare sempre gli intervalli della penultima take quando esiste. Mostrare per ogni taglio motivo, intervallo originale e testo. L'utente può tenere/ripristinare un intervallo e scegliere una take diversa.

Pause: accorciare soltanto quelle lunghe con margini di respiro modificabili; evitare tagli sulle consonanti. Nessuna cancellazione basata soltanto su parole riempitive che abbiano valore semantico. Progressi derivano da fasi e quantità realmente completate.

## Contratto temporale

Piano versionato con firma sorgente, FPS razionale, intervalli mantenuti IN inclusivo/OUT esclusivo in frame, tempi originali delle parole, tempi ricompattati, decisioni e alternative. Un solo algoritmo costruisce la mappa originale→montaggio e il testo derivato. Le parole eliminate non entrano nella base pulita. Modificare i tagli invalida gli artefatti downstream: non riusare selezioni temporalmente obsolete in silenzio.

Mantenere trascrizione originale immutabile e progetto recuperabile. Timestamp stimati non possono diventare automaticamente un piano di taglio: segnalare il limite e richiedere allineamento misurato.

## Interfaccia

CUT facoltativo, analizza, riepilogo durata prima/dopo, tagli proposti, take alternative, revisione/ascolto, anteprima pulita, conferma e torna all'originale. Salvataggio automatico di bozza e revisione confermata; ripresa dopo chiusura.

## Export successivo verso Resolve

Preparare il contratto del pacchetto, senza implementare mutazioni Resolve in questa fase. L'export futuro dovrà creare backup, compattare video/audio insieme, riallineare il workflow con la mappa e collocare le take alternative intere disattivate su tracce superiori. Non sostituire un intervallo di tempi originali con quello ricompattato per errore.

## Verifica

Ripartenze incomplete, tre take simili con ultima valida, ripetizioni intenzionali, pause, finale del file e FPS frazionari. Dimostrare che ogni parola mantenuta cade nel segmento corretto dopo compattazione e che la penultima conserva gli IN/OUT originali. Verificare caricamento, anteprima, salvataggio e ripristino sul caso reale, senza rigenerare piani editoriali o applicare modifiche in Resolve.
