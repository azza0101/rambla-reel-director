# Catalogo → montaggio, v1

Approccio approvato dall’autore nella conversazione (27 ottobre 2026, «ok vai»): dati completi locali collegati al media ID Resolve; sintesi leggibile nei metadati senza sovrascrivere annotazioni. Nessun nome file o bin come prova di appartenenza. Nessuna dipendenza MCP/cloud.

1. Test-first: contesto versionato con scena, ruolo, stato trascrizione distinto da silenzio, prove e identità sorgente. Rifiutare dati di altro progetto/copione o file cambiati.
2. Verificare GetMetadata/SetMetadata Comments su una sola clip del progetto corrente, salvando e ripristinando il valore. Applicazione finale aggiunge/sostituisce solo il blocco Omni-Cut; journal e readback, avviso se API non disponibile.
3. Catalogo salva i contesti su analisi/correzioni/ripristino. Montaggio Omni riusa trascrizioni valide; non ritenta automaticamente ASR di riprese già catalogate senza trascrizione. Il comando Trascrivi esplicito resta disponibile.
4. Sessione: dialoghi separati da coperture senza trascrizione; queste non bloccano la coda né diventano parlato inventato. Errori/assenza di trascrizione restano visibili. Elenco coperture chiuso a tendina con preview; pool strutturato conservato nel piano. Non inserire automaticamente azioni/reazioni prive di intervallo e prova pertinenti: catalogare una scena non verifica un gesto.
5. Suite JS/Python, test nativo read-only sul catalogo reale e test reversibile metadata. Nuovo branch/PR; build test Omni 0.2.7 solo dopo collaudo, no merge/latest globale. Premontato senza contesto mantiene i controlli precedenti.
