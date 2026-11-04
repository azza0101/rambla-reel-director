# Inventario visivo integrato — verifica del 4 novembre 2026

Richiesta: integrare l'inventario separato di oggetti e volti, provarlo sul girato e verificare la resa. Nessun piano camere scritto dall'agente; i frame annotati manualmente sono riferimenti di valutazione, non istruzioni di montaggio. Il modulo non contiene file, attori o timecode del progetto privato.

## Implementazione e confini

`worker/visual_inventory.py` esegue una richiesta per frame al modello visivo locale. Il programma assegna frame e tempi; il modello descrive più oggetti senza assegnare un'identità al portatore. Categorie generali: cibo, utensile, documento, dispositivo, contenitore, altro o incerto. Le descrizioni restano indizi, non identificazioni certificate del prodotto.

Il contesto gestisce un processo llama.cpp su loopback, senza proxy o redirect. Avvio differito: nessun caricamento del modello se tutti i risultati sono in cache. Chiusura del solo processo posseduto al termine o in caso di errore. Nessun download o installazione globale.

Cache atomica con impronta di sorgente, frame, fps, durata, pesi, eseguibile e prompt. Output troncati o non conformi vengono scartati prima del salvataggio. Un errore di frame non blocca i successivi. Un modello indisponibile non deve annullare il selettore ordinario. La revisione ha individuato inizializzazione troppo precoce e risposte HTTP malformate: test rossi, correzioni e verifica verde.

La sintesi descrive solo apparizioni/scomparse tra campioni. `no_longer_visible` non significa gesto completato o oggetto posato. Voce e proprietà degli oggetti restano sempre non certificate da questo modulo.

L'azione JSONL `analyze_visual_inventory` rende il servizio richiamabile dal worker senza Codex o MCP. Per il direttore sperimentale è collegato a `build_observed_excerpt` con `editorial_mode: sequence_director` e `inventory_config` contenente i percorsi locali `server`, `model`, `projection` (opzionale `ffmpeg`). L'assenza di questa configurazione conserva il comportamento precedente.

Nel direttore il controllo è automatico e limitato a confronti di più candidati con parlante già verificato e dialogo con riferimenti a oggetti. Tre campioni per candidato, budget predefinito 12 frame, massimo configurabile 48. Un gruppo di alternative viene analizzato soltanto se entra interamente nel budget. Il confronto visivo entra nel costo solo quando tutti i candidati con parlante verificato hanno evidenza completa: nessun vantaggio casuale per la prima alternativa esaminata.

La visibilità dell'oggetto è subordinata a parlante, raccordo e ultima take buona. Non abilita candidati bocciati per testo/voce/volto, non inventa reazioni e non cambia i confini delle parole. Gli avvisi editoriali e i flag di azione/contenuto non verificati restano espliciti.

**Non è ancora un'opzione installata nel pannello stabile.** È codice collegato al worker/direttore sperimentale, non una release dell'updater né una riprogettazione automatica della storia recitata.

## Test-first e suite

- Test scritti prima del modulo: schema, identificatori assegnati dall'host, proprietà non certificate, scomparsa diversa da deposizione, campioni e categorie incerte.
- Test rosso/verde del costo oggetti e protezione di parlante/ultima take.
- Test rosso/verde del budget incompleto, per evitare confronti sbilanciati.
- Test di cache, mancato avvio del modello, errore isolato, risposte HTTP malformate e budget zero.
- Suite finale Python: **407/407**. Suite JavaScript: **262/262**.

## Prova reale del modulo di prodotto

Stesso modello locale 4B già disponibile, inventario ora generico e senza proprietà delle mani nel prompt. Dieci campioni noti: presenza dell'oggetto concordante con la lettura visiva in **9/10**. Quattro nuovi campioni intermedi dello stesso passaggio: oggetto presente rilevato in **4/4**. Questi ultimi sono tutti positivi e dello stesso progetto: non provano generalizzazione ad altre scene, assenze o identità.

Prima elaborazione di 14 campioni, compresi caricamento e decodifica: **19,30 s**. Seconda esecuzione: **14/14 cache hit**, **0,157 s**, nessun nuovo avvio del modello. Non sono tempi dell'intero premontaggio.

Il modello continua talvolta a descrivere il salume con nomi imprecisi. Il tipo generico e la presenza non certificano la natura dell'oggetto o la recitazione.

## Replay editoriale reale

Replay automatico dell'estratto problematico su 14 registrazioni candidate: 34 ID di parlato, 22 turni, 1.339 frame. Nessun ID perso/duplicato, nessun riuso retrogrado o jump scoperto rilevato dall'audit. I 22 turni non equivalgono a 22 stacchi fisici: sorgenti contigue restano un hold.

L'ultimo replay ha esaminato 21 campioni con budget massimo 24, 20 riusi da cache e una risposta di frame rifiutata per schema non valido. L'errore resta registrato, non sostituito da un inventario vuoto. Fase inventario circa **5,94 s**; pipeline completa circa **41,53 s** con cache già calde.

**Scelte di sorgente/intervallo cambiate rispetto al selettore senza inventario: zero.** Restano dieci turni con copertura incerta. Nessun nuovo MP4 viene presentato come miglioramento, perché la sequenza è invariata. La percezione degli oggetti è migliorata nel test diagnostico, ma il controllo a valle non recupera alternative già escluse dall'allineamento fra versioni recitate.

## Consegna e limite ancora aperto

Codice e test integrati nel ramo della PR di ricerca #47, senza merge e senza release stabile. Nessuna modifica a timeline o progetti Resolve, nessun invio di girato al cloud. Il replay è una prova reale sul materiale sorgente fuori da Resolve, non un nuovo collaudo nativo della timeline.

Il miglioramento successivo richiede allineamento per episodi recitati coerenti prima del filtro camere: le immagini possono ora contribuire con indizi sugli oggetti, ma non possono da sole rendere equivalenti battute o gesti diversi. Non usare il successo 9/10 come prova che il montaggio complessivo sia già migliore.
