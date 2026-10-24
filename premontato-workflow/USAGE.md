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
