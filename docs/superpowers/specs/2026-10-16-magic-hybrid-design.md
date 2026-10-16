# MAGICO — modalità ibrida economica

Data: 2026-10-16. Specifica da revisionare prima del piano di implementazione.

## Obiettivo approvato

Un pulsante dopo il caricamento o la ricezione dal bridge prepara un montaggio completo, correggibile, senza un agente Codex in esecuzione. Usa le funzioni esistenti per CUT, selezioni, ricerche, download e handoff. APPLICA in Resolve resta una scelta esplicita dell'utente.

Aggiunta richiesta: se manca una copertura video coerente, cercare e scaricare un'immagine pertinente, inserita disattivata su una traccia dedicata nel punto corrispondente.

## Approccio scelto e alternative

- Scelto: coordinatore deterministico sopra i servizi esistenti, con checkpoint persistenti, risultati strutturati e chiamate AI limitate ai passaggi semantici.
- Scartato: agente libero che controlla l'interfaccia e decide le chiamate. Costi e ripetibilità peggiori, dipendenza non necessaria da un agente.
- Rimandato: pipeline obbligatoriamente tutta locale. Richiede verifica dell'hardware e installazione/validazione di ASR, modello linguistico e modello visivo locali.

## Flusso e riuso

1. Salva backup dello stato del progetto, identifica sorgente, FPS nominali, orientamento, range e firma del contenuto. Crea una revisione MAGICO distinta; non sovrascrive le selezioni manuali già presenti.
2. Riusa trascrizione con tempi per parola se la firma coincide; altrimenti usa l'ASR configurato. Il CUT attuale usa Groq: nessuna chiamata a Codex.
3. Riusa il motore CUT e la verifica di ripartenze/confini. Sceglie l'ultima take completa equivalente, conserva testo aggiuntivo distinto, evita di eliminare contenuti solo perché una take precedente era più lunga. Casi incerti conservati e segnalati.
4. Elimina pause con profilo MEDIUM iniziale. Margine finale iniziale 120 ms, adattato al confine di parola e limitato dalla parola successiva. Se il confine è incerto, conserva più audio invece di troncare. Il testo non viene alterato dalla riduzione pause.
5. Congela la mappa sorgente/montaggio pulito e crea il progetto CUT tramite il percorso di conferma esistente, senza una seconda trascrizione. Un solo figlio per revisione; ripresa senza duplicati.
6. Da testo completo e contesto geografico produce un piano strutturato: parole chiave, passaggi da coprire, soggetto/azione/luogo e intervalli in frame. Usa gli stessi artefatti di selezione della sezione 2, quindi tutto resta modificabile nel workflow normale.
7. Esegue ricerche sulle fonti abilitate, iniziando da Pexels e dalle query concrete più trovabili; social e altre fonti disponibili ampliano la ricerca. Query specifica + variante breve, mantenendo il luogo quando è determinante. Deduplica per ID e contenuto.
8. Verifica candidati e pianifica coperture: una buona posizione nei risultati non è prova di coerenza. Controlla soggetto, azione, luogo, tono, durata e campioni visivi. Riusa il ranker locale quando disponibile; l'eventuale verifica cloud usa campioni limitati e il budget configurato. Una copertura non verificata resta da revisionare, mai promossa silenziosamente a scelta sicura.
9. Se nessun video supera la verifica, ricerca immagini con il medesimo contesto. Scarica un'immagine pertinente e la propone disattivata. Se manca anche un'immagine pertinente, lascia il parlato e segnala il passaggio scoperto.
10. Cerca coperture generiche e del luogo con il motore esistente. Le usa nel testo solo dove sono coerenti, senza coprire obbligatoriamente tutto il volto/parlato. Le proposte residue restano disponibili; quelle selezionate per la coda non vengono duplicate dentro e fuori dal montaggio.
11. Scarica i media effettivamente scelti, verifica leggibilità e dimensioni, prepara il pacchetto selettivo esistente con video CUT, subs, parole, coperture e immagini alternative.
12. Se il bridge della sessione corrente è online, invia e aspetta la ricevuta reale. Se è offline, mostra PACCHETTO PRONTO — BRIDGE OFFLINE e consente invio successivo. Non modifica Resolve finché l'utente non preme APPLICA.

## Durate e layout Resolve

- Tutti gli intervalli derivano dalla stessa mappa CUT congelata; un'unica conversione a frame, con FPS reali anche frazionari.
- Copertura video: obiettivo 2–4 secondi, minimo iniziale 1,5 secondi. Non dilata una clip oltre il media disponibile né la accelera arbitrariamente. Se il passaggio è troppo breve, lo lascia scoperto oppure usa una sola copertura coerente su passaggi adiacenti; nessuna fusione di significati differenti.
- Parole evidenziate: clip indipendenti sopra tutti i video, Yellow, senza contenitori compound/Fusion annidati.
- Video di copertura: Purple. Immagini fallback: Purple, disattivate, su traccia RMBL IMMAGINI ALTERNATIVE separata e sotto i titoli; durata dell'intervallo suggerito, mai oltre la fine del CUT.
- Take scartate: Red, disattivate e limitate alla corrispondente frase scelta come da v0075. Audio alternativo non attivo.
- Generiche in coda solo se richieste: Beige, dopo il gap esistente. Subs nativi sul percorso ST1 protetto già disponibile.
- Aggiornamenti parziali continuano a funzionare; il componente coperture comprende le immagini fallback e ne conserva ruolo/abilitazione nella serializzazione e nell'applicazione.

## Sorgenti e limite attuale del bridge

Il CUT nativo di video caricato è disponibile. Il CUT di una guida audio multitraccia proveniente da Resolve non è ancora supportato: MAGICO non può dichiararlo già risolto.

Per supportarlo occorre acquisire la mappa delle clip originali nel range IN/OUT con sorgenti, tracce, offset e FPS, e verificare la firma prima di APPLICA. Il piano ricostruisce i tagli su una nuova timeline di lavoro dal materiale originale; la timeline sorgente e i suoi marker non vengono modificati. Niente reimport della sola guida audio come sostituto del video originale.

Le strutture non ricostruibili fedelmente (retiming o composizioni non gestite) devono produrre un motivo esplicito prima di applicare. Il percorso esistente senza CUT resta disponibile. Il supporto bridge completo è un traguardo distinto e obbligatorio prima di dichiarare MAGICO completo per entrambe le sorgenti.

## Economia, limiti e recupero

- Nessun uso di crediti Codex nel prodotto. Le API già configurate hanno quote/costi propri: nessuna promessa di costo zero.
- Locale: conformazione, analisi audio disponibile, taglio, mapping, filtri, cache, download, export e verifiche strutturali.
- Cloud mirato: ASR e ragionamento editoriale/CUT; verifica visiva solo se necessaria e abilitata. Riusa le impostazioni dei provider esistenti, senza introdurre credenziali nel codice o nell'installer.
- Richieste testuali suddivise sotto il budget del provider; contesto globale compatto condiviso, copertura di tutte le parole/chunk verificata. Niente troncamento silenzioso dei video lunghi. Concorrenza limitata e rispetto dei limiti TPM e Retry-After.
- Cache per firma sorgente, revisione, modello e parametri. Cambio selezione o preset invalida solo le fasi dipendenti.
- Limiti iniziali di ricerca per beat: due query per fonte, fino a sei candidati scaricabili da valutare; espansione entro il budget del run. Budget richieste visibile nelle opzioni avanzate; esaurimento produce output parziale dichiarato, non nuove chiamate illimitate.
- CAPTCHA/login: link alla fonte e ripresa manuale, nessun retry automatico della verifica. Se una fonte è bloccata, prova le altre abilitate; non blocca tutto il montaggio per una sola clip.
- Se il ranker non è disponibile, messaggio esplicito e risultati a confidenza ridotta; non simulare un check visivo riuscito.

## UI e persistenza

Pulsante MAGICO dopo l'ingresso sorgente, con opzioni avanzate compatte: profilo pause, fonti e budget. Impostazione iniziale ibrido economico. Nessuna necessità di attraversare manualmente tutte le sezioni.

Un run persistente per progetto/revisione, con fase, unità completate/totali, percentuale misurata, tempo, avvisi e riepilogo chiamate. Stati: queued/running/waiting_input/ready/partial/failed/cancelled. La barra resta ferma se non avanza il lavoro; nessuna animazione che simuli progresso.

Annulla ferma le nuove chiamate e conserva checkpoint. Riprendi riusa i risultati verificati. Un restart del backend non perde lo stato e non ripete automaticamente una chiamata cloud dall'esito ignoto. Un secondo click non avvia un duplicato.

Riepilogo finale: durata prima/dopo, take mantenute/scartate, parole evidenziate, coperture video verificate, immagini disattivate, passaggi scoperti, fonti bloccate e stato consegna bridge. Link alle normali sezioni per correggere ogni scelta e rigenerare solo il necessario.

## Integrazione prevista

Nuovo coordinatore e store MAGICO separati dal server principale. Adattatori verso CUT, Director, phrase-intents, research/ranking/download, conferma progetto e resolve-preparation. Nessuna duplicazione dei motori esistenti.

Il run registra progetto originale, progetto CUT risultante, revisione mappa, input delle fasi e ID pacchetto/bridge session. Il fallback immagine aggiunge un ruolo esplicito e enabled=false al contratto media, mantenendo compatibilità con i pacchetti precedenti.

## Verifica e criteri di accettazione

- Unit test: ultima take completa, conservazione continuazioni distinte, margine finale e pause senza perdita di parole, mapping e durate frame, minimo coperture, esclusione candidati incoerenti, fallback immagine disattivato.
- Coordinatore con provider finti: esecuzione completa, ripresa/cancel, doppio click, quote, fonte bloccata, immagine mancante e bridge offline; nessuna chiamata cloud reale nei test automatici.
- Prova end-to-end su video lungo con errori, ultimo parlato e pause; controllo della copertura completa della trascrizione e dei confini audio. Qualità editoriale rimane una proposta revisionabile, non una garanzia assoluta.
- Prova Resolve tramite MCP solo per QA, su progetto/timeline dedicati: timing, originali, titoli indipendenti, immagini disattivate, take rosse, marker/audio preesistenti invariati. Prodotto e bridge funzionano senza MCP.
- Consegna progressiva: prima coordinamento su sorgente caricata con media verificati e immagini alternative; poi adattamento sorgente Resolve e prova dedicata. Nessuna etichetta di completamento del supporto Resolve prima del secondo traguardo.

## Autorevisione

Il progetto riusa i motori esistenti, esplicita le dipendenze cloud e il limite attuale del CUT da Resolve. Immagini fallback mai attive automaticamente. Tutte le fasi condividono una sola mappa temporale. Nessuna modifica alla timeline utente durante ricerca/preparazione. Approvazione del piano operativo necessaria dopo la revisione di questa specifica.
