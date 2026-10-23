# Uso e verifiche manuali

1. Crea una copia di un progetto Resolve con una scena breve e clip sacrificabili.
2. Installa il prototipo solo nella cartella Workflow Integration di Resolve usando il binario `WorkflowIntegration.node` della stessa installazione.
3. Apri una timeline di riferimento, poi seleziona dal Media Pool tutte le clip di una sola scena, in ordine di ripresa.
4. Carica il copione PDF o un file UTF-8 con heading di scena, cue personaggio, dialoghi e azioni. Seleziona il copione intero: il prototipo prova a individuare la scena ascoltata dalle battute e ne mostra la confidenza.
5. Avvia la trascrizione Resolve solo per le clip selezionate. In seguito confronta i timecode restituiti dalla API con il viewer.
6. Esegui l’analisi locale. Verifica che la scena scelta sia quella giusta. Se il copione e la trascrizione mostrano una ripartenza della scena nello stesso file, controlla e correggi i frame dei confini proposti, poi confermali. Esamina ogni beat e la take scelta; una scena ambigua o un dialogo senza corrispondenza blocca la creazione.
7. Crea la timeline solo nel progetto di prova. Confronta in/out sorgente, durata, sync audio, frame rate e timeline di partenza prima di usarla.

Non considerare la scelta “ultima take” come giudizio sulla recitazione. Il criterio usa la copertura delle battute nello stesso clip, poi l’ordine delle clip selezionate. Le take incomplete sono fallback. Nessuna chiamata remota è attiva.
