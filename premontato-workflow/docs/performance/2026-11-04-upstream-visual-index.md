# Indice visivo prima dei filtri — confronto reale

## Obiettivo e implementazione

Richiesta: usare le immagini prima della selezione del montaggio, per recuperare alternative che il controllo a valle non poteva più considerare. Il codice è nel direttore sperimentale, senza piano camere scritto dall'agente e senza eccezioni per file, attori o timecode privati.

Con `inventory_config` e `visual_stage: upstream` (predefinito quando è presente la configurazione), `build_observed_excerpt` indicizza il soggetto dei turni osservati e dei candidati semantici preliminari **prima del filtro di equivalenza testuale e dell'allineamento verificato**. Riusa YuNet/SFace e il modello visivo locale già disponibile. Non inferisce la voce dall'immagine e non richiede Codex o MCP durante l'esecuzione.

Identità: almeno due frame coerenti con la galleria di volti associata alle voci mediante prove indipendenti. Un volto secondario di dimensione simile impedisce l'assegnazione dominante; una contraddizione fra identità note non viene risolta a maggioranza. Se necessario vengono provati due campioni interni aggiuntivi. Il soggetto dominante non può porre veto a un altro volto parlante positivamente verificato in un campo a due persone.

Oggetti: fino a tre campioni per intervallo pertinente, con budget globale predefinito 12 e massimo 48. Il budget facciale predefinito è 480 frame, massimo 600. Budget e cache sono separati; zero frame oggetti non avvia inferenze del modello. L'inventario non determina proprietà dell'oggetto, completamento del gesto o equivalenza di performance diverse. I criteri testuali negativi restano attivi. Soltanto domande brevi riordinate, già soggette a contesto forte, voce e identità concordanti, possono riaprire un confronto testuale.

I risultati includono avanzamento della fase, campioni, cache hit, budget esaurito, errori e tempo dell'indice. Il processo locale del modello è avviato solo quando necessario e chiuso dal contesto anche in caso di eccezione. Nessun invio di immagini, audio o testo al cloud.

L'allineamento conserva inoltre l'unione delle alternative positivamente verificate dal percorso precedente e da quello upstream fino alla ricerca globale. Un singolo file può contenere più performance: scegliere un solo percorso locale troppo presto poteva eliminare una battuta di una take successiva. La ricerca globale mantiene ordine sorgente e assenza di sovrapposizioni; l'unione delle alternative non autorizza a concatenare percorsi incompatibili. La copertura per campo conta ciascun turno una sola volta.

L'assenza di `inventory_config` conserva il percorso precedente; `visual_stage: late` consente il confronto con il controllo a valle. Questa integrazione non è un nuovo pacchetto del pannello stabile.

## Errori riprodotti e corretti

- Osservazione di sola identità seguita da richiesta oggetti sullo stesso intervallo: la memoizzazione impediva l'arricchimento. Test rosso/verde, con riuso degli stessi vettori facciali.
- Il percorso upstream ignorava `inventory_frame_budget`. Propagazione verificata passando zero attraverso l'editor, oltre al test di mancata chiamata del modello.
- Un turno successivo poteva sovrascrivere l'inventario di un candidato condiviso con una semplice osservazione di identità. L'arricchimento viene conservato, mentre il requisito oggetti dipende dal turno interrogante.
- Nel campo a due persone il volto dominante poteva appartenere all'ascoltatore. Test rosso/verde: questo indizio non annulla la verifica positiva di un altro volto parlante.
- Nuove alternative positive potevano cambiare il percorso locale e far perdere una corrispondenza già valida di un'altra performance nello stesso file. Test rosso/verde dell'unione dei percorsi fino alla scelta globale.

## Prova sul materiale reale

Stesso estratto problematico, stesse 14 registrazioni candidate, stessi 34 identificatori di parlato osservato e 22 turni. Nessuna modifica al copione o piano camere manuale. Il riferimento senza inventario è stato rieseguito con il codice corrente, non soltanto letto da un vecchio risultato.

| Misura | Riferimento attuale | Indice upstream finale |
| --- | ---: | ---: |
| Alternative, inclusi i 22 turni base | 49 | 53 |
| Turni con copertura incerta | 10 | 10 |
| Durata | 1.339 frame | 1.339 frame |
| Scelte sorgente/intervallo cambiate | riferimento | **0** |
| Eventi persi o duplicati | 0 | 0 |
| Sovrapposizioni/riusi retrogradi/jump scoperti rilevati | 0 | 0 |
| Tempo completo con cache già calde | 34,71 s | 46,68 s |

Indice finale: 231 frame facciali, tutti riusati dalla cache; budget non esaurito. 24 richieste oggetti, 20 riusi validi e quattro risposte rifiutate per schema. Le risposte rifiutate restano errori, non inventari vuoti certificati. Tempo delle osservazioni upstream: 10,36 s. Una prima prova senza tutta la cache facciale ha richiesto circa 83,53 s per la pipeline; non è un benchmark a freddo dell'intero sistema, perché altre cache erano già presenti.

La prima variante upstream aveva peggiorato il riferimento a 11 turni incerti: l'ispezione dei fotogrammi ha mostrato che perdeva un campo utile dell'uomo. Aumentare i tentativi da tre a otto non ha cambiato l'esito, quindi tale modifica è stata rimossa. Conservare i percorsi verificati fino alla ricerca globale ha recuperato la scelta precedente. Non presentare questa regressione corretta come miglioramento rispetto al riferimento.

## Verifica e conclusione

Suite Python: **417/417**. Suite JavaScript: **262/262**. Revisione mirata delle correzioni senza nuovi blocchi seri segnalati. Replay reale sui file sorgente e ispezione di fotogrammi; **nessun nuovo collaudo nativo Resolve, nessuna timeline o progetto modificati**.

**Il montaggio finale non è sensibilmente migliore: è invariato, con un costo aggiuntivo.** Nessun nuovo MP4 viene presentato come miglioramento di una sequenza identica. Il controllo ora arriva prima dei filtri e conserva più candidati, ma non ricostruisce ancora correttamente tutti gli episodi fra versioni recitate diverse. Restano i passaggi incerti del riferimento; superare l'audit di intervalli non certifica recitazione, azioni o corretto soggetto in ogni momento.

Il limite successivo è l'allineamento degli episodi recitati, inclusi domande ripetute e azioni con oggetti. Una galleria facciale e un inventario di oggetti non sono da soli una soluzione a quel problema. Per questo il lavoro rimane nel ramo di ricerca, senza aggiornamento dell'app installata, merge o release stabile.
