# Uso e verifiche manuali

1. Crea una copia di un progetto Resolve con una scena breve e clip sacrificabili.
2. Installa il prototipo solo nella cartella Workflow Integration di Resolve usando il binario `WorkflowIntegration.node` della stessa installazione.
3. Apri una timeline di riferimento, poi seleziona dal Media Pool tutte le clip di una sola scena, in ordine di ripresa.
4. Carica il copione PDF o un file UTF-8 con heading di scena, cue personaggio, dialoghi e azioni. Seleziona il copione intero: il prototipo prova a individuare la scena ascoltata dalle battute e ne mostra la confidenza.
5. Avvia la trascrizione Resolve solo per le clip selezionate. In seguito confronta i timecode restituiti dalla API con il viewer.
6. Esegui l’analisi locale. Verifica che la scena scelta sia quella giusta. Se il copione e la trascrizione mostrano una ripartenza della scena nello stesso file, controlla e correggi i frame dei confini proposti, poi confermali. Esamina ogni beat e la take scelta; una scena ambigua o un dialogo senza corrispondenza blocca la creazione.
7. Crea la timeline solo nel progetto di prova. Confronta in/out sorgente, durata, sync audio, frame rate e timeline di partenza prima di usarla.

Non considerare la scelta “ultima take” come giudizio sulla recitazione. Il criterio usa la copertura delle battute nello stesso clip, poi l’ordine delle clip selezionate. Le take incomplete sono fallback. Il montaggio resta locale; l’unica operazione remota facoltativa è l’invio esplicito della diagnostica.

Se il pannello presenta un errore, **Invia debug** mostra un’anteprima tecnica filtrata. Controllala e seleziona la casella di conferma prima di inviare: GitHub CLI (`gh`) deve essere installata e autenticata con accesso `repo`. Il report contiene versione, sistema operativo, tipo di errore e frame tecnici; non contiene il testo del copione/errore, trascrizioni o media. L’invio crea un issue nel repository privato RAMBLA.

## 0.9.0 — Regia e tracce

Nel pannello Regia scegli VIDEO COLICHE. Puoi scrivere note o caricare un file .txt/.md (massimo 20.000 caratteri). Le note sono un promemoria locale, non sono interpretate automaticamente. Dopo l’analisi segna sulle battute Inizio tensione, Risoluzione o Libero. Prosegui mantiene lo stato corrente. Durante la tensione il selettore preferisce le strette e conserva le pause; la risoluzione preferisce la larga e termina la tensione. Sono preferenze tra corrispondenze affidabili, subordinate alla visibilità del parlante: la copertura mancante viene segnalata. Le reazioni prima delle risposte richiedono scelta manuale.

Salva direzioni e ricalcola applica profilo e marcatori: ricalcola le scelte precedenti, quindi applica prima lo stile e poi le correzioni delle clip. Il salvataggio di sole note conserva il piano esistente. Applica prima le bozze non correlate (take, clip, ritmo, revisione visiva): il pulsante protegge tali modifiche prima del ricalcolo. Il progetto e l’autosave conservano anche le direzioni non ancora applicate. Il profilo Alternanza standard ignora i marcatori narrativi. La memoria dello stile è docs/styles/VIDEO_COLICHE.md.

Le timeline generate usano tre coppie di tracce: V1/A1 master e larghe blu, V2/A2 medie verdi, V3/A3 strette e dettagli arancio. Le inquadrature incerte sono sulla prima traccia in Tan. Solo il formato delle tracce audio create è mono: non vengono modificati gli attributi o la mappatura delle clip sorgente. Posizioni, colori, conteggi e sincronizzazione sono verificati; se Resolve non rispetta il layout la nuova timeline viene annullata.

Le nuove timeline includono v0.9.0 nel nome e vengono create sotto Premontato / v0.9.0 / Revisioni; i test usano Premontato / v0.9.0 / Test. La cartella e la timeline attive vengono ripristinate dopo la creazione.

Per un recupero manuale: salva il progetto Resolve, chiudi il pannello Premontato e Resolve e avvia dist-0.9.0/Install-Premontato.exe. La versione 0.9.0 carica esplicitamente i moduli Utility/Management di Windows PowerShell, trasmette gli errori reali dell’installer e controlla la versione installata su disco prima del riavvio.

## 0.9.1 — versione visibile e avvio del pannello

Corregge il blocco del preload sandbox della 0.9.0. La versione compare accanto ad Aggiorna e nel titolo della finestra, anche prima dell’avvio dell’interfaccia. Un pannello 0.9.0 bloccato richiede reinstallazione manuale della 0.9.1: il suo pulsante Aggiorna non può essere utilizzato finché il preload non si avvia.

## 0.9.2 — collaudo delle riprese e correzioni dell’allineamento

Le finestre semantiche rispettano i cambi di voce osservati come indizi di confine, completano le frasi oltre pause brevi e non prendono in prestito l’attacco della battuta successiva. La visibilità confermata del parlante viene considerata prima della qualità della trascrizione. Gli abbinamenti con poche parole comuni al copione richiedono un controllo esplicito di completezza, anche quando la somiglianza semantica è alta: le parafrasi e le ripetizioni parziali restano possibili.

L’apertura senza clip selezionate non viene più presentata come assenza del collegamento a Resolve. Le pause segnaposto senza parlato vengono escluse dalla trascrizione; i progetti precedenti contenenti un segnaposto al frame -1 possono essere riaperti mantenendo la validazione dei segmenti parlati. L’analisi dei campi decodifica il video in sequenza per evitare ricerche ripetute nei GOP.

## 0.9.3 — completezza e reazioni integrate

Il motore locale confronta anche l’attacco delle battute lunghe, conserva una versione completa invece di una ripetizione recente ma parziale e separa i tentativi interrotti da sospensioni esplicite. I margini automatici non includono parole delle battute adiacenti. Se mancano indizi sufficienti rimane necessaria la revisione: nessuna garanzia di trascrizione o scelta perfetta.

Nel profilo VIDEO COLICHE, un beat Risoluzione preceduto da Tensione può ricevere una stretta silenziosa del personaggio che risponde prima dell’apertura sulla larga. Servono una ripresa alternativa associata alla stessa battuta, presenza confermata nelle still, pausa audio misurata, nessuna parola trascritta sovrapposta, durata minima configurata e nessun fotogramma già usato altrove nel piano. Il plugin mostra la still esatta e un comando per escludere l’inserto; l’esclusione resta salvata anche quando ricalcoli stile, campi o take. Il suo audio ambiente resta collegato su traccia mono. Non classifica emozioni e non inventa reazioni: senza requisiti mostra il motivo dell’assenza.

Significato, attacco e ricerca delle reazioni sono calcolati nel runtime del plugin, senza Codex, Groq o altre chiamate cloud. La conferma di campi/personaggi e i marcatori Tensione/Risoluzione rimangono controlli dell’utente. Le note libere restano un promemoria.


## 0.9.4 — collegamento e aggiornamento nel processo Resolve

Gli aggiornamenti ricaricano il pannello nello stesso processo Electron registrato da Resolve. La versione e i moduli vengono riletti senza avviare una finestra esterna. Il collegamento viene conservato; una inizializzazione SDK fallita può essere ritentata cliccando sullo stato in alto. Gli errori di selezione clip sono separati dallo stato del collegamento.

Se una versione precedente ha già riaperto il pannello fuori da Resolve, chiudi Premontato e aprilo una volta da Workspace > Workflow Integrations > RAMBLA Premontato. Avviarlo direttamente con Electron non ripristina la registrazione del plugin nel programma.


## 0.9.5 — controllo inquadrature e conferme

I gruppi volti restano visibili; la stessa persona può avere più gruppi, ai quali puoi assegnare lo stesso personaggio. Clicca una miniatura per ingrandirla. I frame interi e i controlli dei singoli intervalli sono chiusi per impostazione iniziale: aprili con «Apri controllo inquadrature». Chiudere la sezione non elimina le modifiche.

Accanto alla creazione timeline sono elencati i passaggi mancanti con collegamenti diretti. La conferma finale delle battute non sostituisce «Conferma e ricalcola il montaggio» della revisione visiva. Le correzioni in bozza continuano a bloccare la timeline finché non vengono applicate.


## 0.9.6 — controllo volti su richiesta

Anche i gruppi volti sono chiusi inizialmente: «Apri controllo volti» mostra miniature e associazioni ai personaggi. Il comando è indipendente da «Apri controllo inquadrature». Chiudere una sezione non elimina le associazioni o le correzioni e non sostituisce la conferma visiva richiesta.

I gruppi sono generati nel runtime locale con YuNet/SFace; non sono gruppi importati dal catalogo IntelliSearch. Il comando IntelliSearch avvia separatamente l’analisi nativa Resolve; gli eventuali metadati People delle clip sono informativi.


## 0.9.7 — timeline dalle sorgenti analizzate

Dopo l’analisi puoi cambiare selezione o cartella nel Media Pool: la creazione ritrova le clip del progetto tramite gli ID salvati. Non occorre riselezionare le riprese o rifare l’analisi per un semplice cambio selezione. Restano i controlli su progetto/timeline, file originali e proprietà Resolve (percorso, durata, fps e timecode). Una sorgente rimossa o ricollegata a un altro file interrompe la creazione prima di aggiungere la timeline.

Il pannello mostra «Creazione timeline in corso» e risultato o errore accanto al pulsante.


## 0.9.8 — avanzamento aggiornamenti e apertura timeline

Aggiorna mostra immediatamente una barra, tempo trascorso e fasi: credenziale locale, ricerca release, manifest, download, verifica, salvataggio, installazione e riapertura. La ricerca resta indeterminata finché il servizio risponde; download e fasi con quantità note mostrano percentuali misurate. Dopo 15 secondi senza eventi il pannello indica l’attesa senza simulare avanzamento. Errori e assenza di aggiornamenti terminano lo stato di attesa.

«Crea premontato» apre ora la nuova timeline dopo averne verificato la creazione; quella di partenza resta intatta. Il pannello aggiorna il proprio riferimento alla timeline attiva, così è possibile continuare a lavorare con la stessa analisi. Le prove automatiche possono continuare a richiedere esplicitamente il ripristino della timeline precedente.


## 0.9.9 — campi e personaggi a tendina

Il controllo visivo è raccolto nella tendina «Campi e personaggi», chiusa all’apertura. La casella di conferma, il comando di ricalcolo e lo stato restano all’esterno. Chiudere la tendina non perde le correzioni. Il collegamento alla conferma mancante vicino alla timeline apre direttamente la tendina.


## 0.9.10 — elenco battute a tendina

L’elenco completo di battute, trascrizioni, alternative e campi In/Out è raccolto in «Battute e scelte di montaggio», chiuso inizialmente. Il titolo riporta il numero di battute abbinate e non abbinate. La conferma finale, le indicazioni sulle tracce, gli eventuali blocchi e il comando Crea timeline restano all’esterno.
