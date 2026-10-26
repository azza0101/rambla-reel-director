# Omni-Cut test 0.2.0 — clip intere e catalogazione visiva locale

## Uso

Caricare il PDF aggiornato dal pannello, leggere le cartelle Resolve e scegliere la cartella delle riprese. Match girato con copione riusa le trascrizioni, confronta semanticamente il parlato e propone una scena per ogni clip intera. Le prime proposte dal parlato sono visibili mentre prosegue la coda. Solo le clip mute o incerte passano alla fase visiva, dopo la fase trascrizioni per evitare due modelli in concorrenza sulla GPU.

Le schede sono ordinate per scena e nome file: verde significa match proposto, giallo significa nessuna destinazione proposta. Il verde non certifica l'accuratezza del riconoscimento. Il numero della scena è evidenziato e preserva la numerazione del titolo nel copione. Il menu permette di cambiare scena o lasciare la clip al suo posto. Cliccando sul nome si apre/chiude una preview di uno o due JPEG, estratta soltanto su richiesta. I conteggi mostrano scene e clip, senza intervalli.

Applica al Media Pool salva il progetto e sposta gli oggetti originali interi nei bin scena, dentro la cartella sorgente scelta. I nomi dei bin derivano dai titoli del copione, sanitizzati soltanto per caratteri incompatibili; titoli uguali vengono distinti dal progressivo. Non crea subclip o timeline SELECTS e non muove i file sul disco. Le clip senza scena restano nel bin corrente. Le timeline non vengono modificate. Le eventuali vecchie SELECTS non vengono cancellate automaticamente.

Ogni file ha un solo bin di destinazione. Se contiene più scene si usa la scena predominante solo quando emerge abbastanza chiaramente; altrimenti resta giallo. I riscontri alternativi sono conservati nel checkpoint. La selezione manuale della scena vale per l'intera clip.

## Visione senza servizi esterni

Il modulo opzionale usa Qwen3-VL-Embedding-2B con codice ufficiale già presente sul PC. Non genera testo o piani di montaggio: confronta vettori delle immagini con vettori delle descrizioni d'azione e dei titoli delle scene. Le azioni lunghe vengono separate in frasi, evitando una singola descrizione troppo generica. Il testo resta in italiano.

Campionamento: circa un frame ogni cinque secondi, ridimensionato a massimo 640 pixel di larghezza; massimo 24 frame distribuiti sull'intera clip. L'encoder lavora a risoluzione inferiore. Non dimostra da solo un gesto dinamico come bussare: ambiente, oggetti e azioni forniscono indizi; scene visivamente simili possono restare ambigue. La decisione usa soglia di similarità, margine e accordo tra frame. I punteggi non sono probabilità calibrate. Se il parlato forte è già sufficiente, la visione non viene eseguita. Un conflitto con un parlato debole lascia la clip senza assegnazione.

Frame ed embedding sono in cache locale, identificati da file, dimensione, mtime, impostazioni e pesi del modello. Cambiare PDF riusa i vettori delle immagini e ricalcola il confronto con le nuove descrizioni. Il checkpoint conserva l'assegnazione e riprende le clip non completate. Lo spostamento nei bin non richiede nuova estrazione delle immagini. Il processo visivo viene terminato al termine della catalogazione o della pausa per liberare memoria.

Nessuna chiamata Codex, Groq o altra API cloud durante questo flusso. Il lavoro di sviluppo non è incluso in questa affermazione. Nessun server MCP è necessario all'utente.

## Dipendenze locali opzionali

Il runtime principale incluso resta invariato. Il modello visivo e il suo ambiente Torch non sono incorporati nell'installer: su questo PC viene riusato in sola lettura l'ambiente Qwen esistente. Non vengono installate dipendenze globali, scaricati modelli o modificati RMBL/ComfyUI. In assenza dell'ambiente visivo il match del parlato continua e il pannello mostra il motivo locale.

La directory opzionale è ricercata tramite OMNICUT_VISION_HOME o nella directory Qwen dello spazio di lavoro di questo PC. Per altri percorsi, creare catalog-vision.json nella cartella dati Omni-Cut con campi python, deps, code e model: rispettivamente interprete Python isolato, directory dipendenze, checkout ufficiale con src/models/qwen3_vl_embedding.py e directory locale Qwen3-VL-Embedding-2B. Nessuna credenziale è richiesta. Codice ufficiale: https://github.com/QwenLM/Qwen3-VL-Embedding (Apache-2.0); non redistribuiamo qui pesi o dipendenze del modello.

## Sicurezza applicazione

Analisi e anteprime non mutano Resolve. L'unica applicazione usa l'anteprima corrente e una conferma finale con Applica al Media Pool. Vengono verificati progetto, sorgenti, identità e bin dopo MoveClips. Il journal salva destinazione e origine prima dello spostamento, gestisce ripresa e seconda applicazione senza duplicati. Una ripresa dopo interruzione riconosce uno spostamento già eseguito soltanto verso la destinazione registrata e con identità del file invariata. Le anteprime accettano solo ID presenti nel catalogo, mai percorsi dal renderer.

## Collaudi

Test automatici di classificazione, campionamento, ambiguità, azioni mute, ripresa, selezione manuale, spostamento/idempotenza, invalidazione sorgente e preview sicure. Rendering reale del pannello in browser headless isolato con fixture: colori, anteprima e assenza di overflow orizzontale. Nessun controllo del mouse dell'utente.

Test nativo Resolve 21.1.0.17: spostato e riletto un oggetto originale, seconda applicazione saltata, nessuna timeline creata. Poi ripristinato l'oggetto nel bin iniziale ed eliminato il bin temporaneo; identità delle 51 clip e impostazioni del progetto preservate. Test locale Qwen su clip reali senza trascrizione: primo avvio circa 46 s per caricamento e inferenza iniziale; esempio successivo 1,4 s di inferenza per 14 frame, più estrazione. Sono esempi misurati, non una garanzia per ogni clip o PC.

Suite di consegna: 178 test JavaScript e 195 Python superati. Preview reale: due JPEG, 13–22 KB ciascuno nel campione. Il motore ha proposto automaticamente la scena esterna per la clip 7715 usando sei frame e nessun match del parlato; la still di controllo mostra la donna davanti alla serranda. Questa verifica puntuale non misura l'accuratezza di tutte le altre assegnazioni. Chiusura/riapertura reale con UAC e distribuzione dell'ambiente Qwen su un PC pulito non collaudate.

Prova completa su copia del catalogo reale: 51 clip, 8 scene del PDF, 35 proposte di destinazione e 16 clip senza destinazione o in conflitto. Prima esecuzione completa con alcune cache già presenti: 616,9 s; ripresa a cache aggiornata: 4,4 s. Nessuna chiamata cloud, nuova ASR o scrittura Media Pool durante questa prova. I 35 match sono proposte, non 35 etichette con accuratezza certificata.

I due nuovi moduli JavaScript sono distribuiti sotto runtime/premontato, directory già supportata da installer e updater precedenti. Non si amplia la whitelist degli eseguibili plugin del vecchio updater. Il readback del pacchetto installato deve verificare anche questi moduli, oltre al codice Python e al caricamento del controller.
