# Memoria delle preferenze — Premontato e Omni-Cut test

Fonte: istruzioni esplicite dell’autore nella chat di sviluppo, fino al 27 ottobre 2026. Questo registro conserva requisiti e decisioni: non afferma che ogni preferenza sia un riconoscimento automatico infallibile. Il comportamento effettivo va verificato nei moduli, nei test e nelle note di versione. Non inserire eccezioni basate sui nomi dei file usati come esempi.

## Controllo del computer e ambito
- OFF richiede di interrompere e rilasciare immediatamente ogni sessione di automazione, incluso il runtime di controllo. Nessun ulteriore input o acquisizione; ripresa solo con autorizzazione esplicita. Codice e file possono continuare. Vale per tutti gli agenti; regola globale già registrata nelle istruzioni dello spazio di lavoro.
- Usare pochi agenti; preferire lavoro individuale per contenere crediti. Il plugin deve funzionare senza Codex e senza MCP obbligatorio.
- Separare Omni-Cut test da Premontato, RMBL e Auto-Cut; riusare il motore Premontato in modo compatibile, senza alterare gli altri prodotti. Nessun merge autonomo su main. Release con tag del prodotto, mai latest globale. Auth pubblicazione gh locale; nessuna chiave/token nell’installer.
- Conservare progetti, timeline, sorgenti e impostazioni. Salvare prima delle modifiche e degli aggiornamenti. Per i test attuali usare il progetto aperto salvato, con operazioni temporanee ripristinate; non moltiplicare progetti sintetici o timeline non richieste.

## Catalogazione giornata
- Inventario ricorsivo della cartella Riprese scelta, senza selezionare ogni clip. PDF completo: trovare scene e mantenere titoli e numerazione; intervalli di pagine sono facoltativi.
- Classificare e spostare gli oggetti originali **interi** nel Media Pool. Non creare subclip, duplicati o SELECTS per simulare la catalogazione; nessuno spostamento dei file sul disco. Una clip può contenere più scene: mantenere i riscontri, scegliere una destinazione primaria solo se sostenibile.
- Riutilizzare trascrizioni Resolve e cache locali. Trascrivere le mancanti una alla volta, salvare checkpoint, continuare dopo errori. Non rifare l’ASR per una correzione della destinazione.
- Confronto semantico con il copione, anche con battute parafrasate; parole generiche, nomi ripetuti o soli sì/no non bastano.
- Per riprese mute o incerte usare pochi frame ridotti, circa ogni 5 s, con cache e numero massimo. Nessuna chiamata Codex/cloud necessaria per questa modalità; riusare Qwen locale quando disponibile.
- Prima di assegnare a una scena diversa, confrontare visivamente riprese vicine affidabili della stessa sequenza di camera/data. La vicinanza da sola non è prova. Non propagare ipotesi in catena come nuovi riferimenti.
- Un primo piano/dettaglio di un’azione può appartenere alla scena riconosciuta nella larga vicina. Valutare contesto, persona/azione, copione e immagini prima di relegarlo a B-roll. Un dettaglio generico senza legame narrativo va in **DETTAGLI E B-ROLL**, categoria separata dal copione.
- Esempi di regressione, mai condizioni di produzione: 7704 → scena 7; 7692 → verificare scena 4 anziché 2; 7717 → contesto della scena esterna della serranda, anziché dettagli generici.
- Bin ordinati con prefissi numerici a zeri: 01, 02, 03 secondo la scena del copione; dettagli/B-roll dopo le scene. Rimozione soltanto di vecchi bin catalogo registrati e completamente vuoti.
- Proposte automatiche modificabili dall’utente; giallo per nessuna destinazione, verde per proposta, senza presentare i punteggi come certezza. Preferire incertezza esplicita a una falsa corrispondenza.

## Pannello e salvataggio
- Righe compatte: numero clip per primo, scena assegnata dopo, nome cliccabile per 1–2 frame caricati su richiesta. Scene leggibili, colori distinti, niente elenco di intervalli nel flusso clip intere.
- Un solo **Applica al Media Pool**: prepara/verifica internamente il riepilogo. Barra reale con fase, file, destinazione, conteggio, verifiche e risultato; segnalare errori e continuare quando possibile.
- Memorizzare ultimo PDF, cartella e checkpoint per progetto. Ripristinare alla riapertura; segnalare PDF cambiato o cartella rimossa. Correzioni manuali preservate durante aggiornamenti delle regole.
- Revisione di battute, still, volti e debug in sezioni chiuse a tendina; pulsanti Apri/Chiudi coerenti. CREA TIMELINE è l’azione esplicita finale, senza checkbox finale ridondante; i veri blocchi devono avere una spiegazione.
- Versione visibile accanto ad Aggiorna e nel titolo. Aggiornamento con fasi e barra, autosave, chiusura/riapertura del pannello; salvataggio progetti Premontato e ripresa sessione. Upload debug GitHub solo dopo conferma dell’utente.

## Montaggio Premontato — preferenze da preservare
- Base: contesto iniziale in master se esiste; poi persona che parla; master per scambi lunghi o rilascio della tensione, non alternanza meccanica. Master non obbligatoria: gestire anche sole strette o solo piano sequenza/master.
- Più take nello stesso file e take separate; preferire ultime take riuscite, eliminare ripartenze/ripetizioni mantenendo informazioni uniche. Prima una camera, struttura predisposta al multicam.
- Chi parla va identificato senza obbligare a conoscere il nome. Non confondere volto visibile, identità e parlante attivo. Associazioni e still correggibili; gruppi duplicati della stessa persona vanno riunibili.
- Non alterare gratuitamente ritmo, pause, respiri o recitazione. Conservare azioni fra battute, uscite/avvicinamenti e passaggi naturali fra scene.
- Profilo VIDEO COLICHE: mantenere strette nel crescendo, reazione prima dello sbotto, larga alla risoluzione. Esempio invito a dormire nel letto → reazione di lui → larga sul rifiuto. Vedere docs/styles/VIDEO_COLICHE.md e runtime/premontato/video_coliche.json.
- Cambi di temperatura ricavati dal senso del testo: richiamo, rivelazione, accusa, ordine o nuovo interlocutore motivano reazione pertinente. Esempio madre che chiama SANDRO → reazione di Ludovica; nessuna condizione sul nome o sul secondo 44.
- Reazione come inserto video sopra il parlato base continuo: normalmente parlante → ascoltatore → ritorno leggibile al parlante prima del turno seguente. Eccezioni motivate dalla gag o dalla regia; mai reazioni sotto **1,5 s** o volto arbitrario di un altro momento.
- Mai jump cut consecutivi sullo stesso campo: continuità, unione di tratti contigui o copertura diversa pertinente. Non creare buchi o troncare parole per imporre un’alternanza.
- Base ordinata su V2/A2, inserti/reazioni su V3; massimo tre tracce video. Tracce audio della timeline mono, senza cambiare le proprietà audio dei file sorgenti.
- Colore stabile per campo/persona: alternative dello stesso campo e persona uguali; campi/persone diversi distinguibili. Stesso campo nello stesso file non cambia colore arbitrariamente.
- Timeline di prova con versione del plugin, ordinate in sottocartelle Media Pool; aprire la timeline appena creata. Nel debug fra scene: gap e titolo progressivo esteso alla durata della scena.
- Dati estratti/cache separati dal piano editoriale: pulizia parlato, allineamento, scelta coperture e controlli locali verificabili. Chiamate Groq solo quando necessarie e configurate, mai piano scritto manualmente dall’agente come risultato del plugin.

## Limiti della memoria
Questo documento è memoria persistente nel repository. Non crea da solo un apprendimento del modello né applica preferenze editoriali alla catalogazione. Le istruzioni di stile eseguibili e le relative cache restano nei moduli dedicati. Ogni futura modifica deve conservare le regole pertinenti e documentare ciò che è implementato, collaudato o ancora richiesto.
