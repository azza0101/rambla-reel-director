# VIDEO COLICHE — direzioni di montaggio

Profilo in evoluzione. Le indicazioni esplicite per la scena prevalgono sulle preferenze generali.

## Tensione e distensione

Durante un momento tensivo o un crescendo, mantenere le inquadrature strette fino al sollievo o alla risoluzione. Evitare alternanze gratuite: la larga dà contesto, varia uno scambio prolungato oppure accompagna il cambio emotivo e distende. La varietà non deve interrompere un crescendo.

Prima dello sbotto, valorizzare il primo piano di reazione del personaggio che sta per rispondere, se esiste una copertura adatta e verificata. Passare alla larga nel punto di risoluzione. Non inventare reazioni o utilizzare un primo piano di un altro momento senza revisione.

### Esempio fornito dall’autore

Quando lei invita lui a dormire nel suo letto: tenere prima un primo piano di lui, lasciando salire la tensione; passare alla larga quando lui rifiuta, per distendere. Il rifiuto, in questo caso, è il cambio emotivo su cui aprire il campo.

## Uso del profilo

Queste sono preferenze narrative, subordinate a corrispondenza del dialogo, continuità, copertura disponibile e conferma dei personaggi. Se manca la copertura, segnalarlo nella revisione. Non trasformare ogni pausa in tensione né ogni battuta finale in risoluzione.

Fonte: indicazione diretta dell’autore, 24 ottobre 2026.


Direzione aggiornata: la master serve soprattutto a dare contesto all’inizio, variare scambi prolungati e distendere dopo il crescendo. Durante la tensione mantenere le strette. Negli scambi lunghi si può riaprire al cambio di parlante, con copertura affidabile, senza una cadenza fissa di tagli. Il criterio automatico iniziale considera circa 30 secondi consecutivi di copertura stretta con almeno due interlocutori, fuori dal crescendo; non forza ritorni su monologhi o dialoghi brevi. Questa soglia è un’indicazione tecnica conservativa, non una regola stilistica assoluta.


## Reazioni e continuità

Durante una proposta che crea tensione, inserire la reazione di chi ascolta prima del rilascio sulla larga, quando la copertura è verificata. La reazione può coprire la coda della battuta precedente conservandone l’audio. Non inventare espressioni o attribuzioni personali.

Mai accorciare un intervallo con un jump cut sullo stesso campo: conservare la continuità oppure usare una copertura diversa. Unire fisicamente i tratti contigui della stessa ripresa. Conservare le azioni tra le battute, per esempio l’uscita di lei e l’avvicinamento di Claudio, usando la take larga ancorata ai dialoghi; verificare la durata del raccordo.


## Svolte di temperatura e reazione del destinatario

Indicazione dell’autore, 26 ottobre 2026: un richiamo improvviso, un’accusa, una rivelazione, un ordine o un cambio di interlocutore possono cambiare la temperatura della scena. Leggere il testo e il contesto della battuta per individuare il punto della svolta, la persona coinvolta e la priorità di mostrarne l’ascolto. Non usare il volume audio o il solo punto esclamativo come prova sufficiente.

Esempio editoriale: quando la madre chiama «SANDRO!», cercare subito dopo il richiamo la reazione di Ludovica, mantenendo sotto l’audio della madre che prosegue. L’esempio non deve diventare una condizione sul nome SANDRO, sul file o sul secondo 44. L’istante va ancorato alle parole temporizzate; la copertura deve appartenere al momento narrativo pertinente e superare i controlli di ascolto e continuità. Se manca un candidato verificato, segnalarlo invece di prendere un volto silenzioso arbitrario.

## Inserto e ritorno al parlante

Preferenza generale: parlante → ascoltatore → ritorno al parlante prima della chiusura della sua battuta, poi eventuale cambio di turno. La reazione è un inserto motivato e non deve automaticamente diventare la nuova inquadratura principale. Lasciare un ritorno leggibile, evitando un brevissimo lampo del parlante.

Eccezioni intenzionali: si può restare sull’ascoltatore quando sta per prendere la parola, quando la sua reazione è la chiusura della gag o quando la regia richiede di sospendere sul suo volto. Non trasformare A–B–A in un’alternanza meccanica. Motivare l’eccezione nel piano editoriale.

Vincoli confermati: ripresa base e parlato completi su V2/A2; reazioni solo video su V3, almeno 1,5 secondi. Non accorciare una reazione sotto questa soglia per far entrare il ritorno: saltare l’inserto o usare una copertura continua pertinente.

## Stato di implementazione al feedback sulla 0.11.9

Questo documento conserva le preferenze dell’autore; non è un prompt letto automaticamente dal motore. Nella 0.11.9 Groq classifica unità di parlato, non svolte editoriali. Le reazioni locali sono ancorate allo stesso beat e vincolate alla coda: validateOverlay richiede offset + durata = durata della battuta. Per applicare le nuove preferenze servono eventi narrativi strutturati dal testo (con ancore verificabili), ricerca della copertura pertinente e supporto a inserti interni con ritorno. Le due nuove regole sono salvate ma non ancora eseguite dalla 0.11.9.


## Profilo editoriale 0.11.11
Il motore legge le direzioni e le preferenze curate in runtime/premontato/video_coliche.json con un passaggio Groq testuale, separato dalla classificazione del parlato e con cache propria. Le osservazioni Gemini del video di riferimento non sono verificate sul filmato originale e non sono importate direttamente come regole o timecode. Le preferenze includono reazioni motivate, ritorno leggibile al parlante, mantenimento del piano a due nelle gag fisiche se la copertura lo consente, distensione sulla larga disponibile e conservazione dei respiri già presenti. Non si autorizzano parole troncate, pause inventate o reazioni sotto 1,5 secondi.

Il modello propone soltanto eventi e ancore testuali reali; il codice locale conserva la responsabilità di selezionare le riprese e temporizzare gli inserti. Questa versione implementa eventi di ascolto e distensione, non un riconoscitore generale di azioni fisiche o oggetti. Il semplice consiglio di mantenere il piano a due non costituisce una verifica automatica del gesto. Se non c’è spazio per una reazione e un ritorno leggibile, o non c’è prova di ascolto, l’intenzione resta segnalata in revisione.
