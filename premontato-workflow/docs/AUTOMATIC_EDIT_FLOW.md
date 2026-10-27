# Montaggio automatico — Omni-Cut test 0.2.9

Premi **Analizza e prepara montaggio**. I confini take validi sono accettati automaticamente; se tagliano il parlato o lasciano buchi, il motore conserva la clip intera. Non serve confermare take, volti o direzioni per ottenere il piano.

Il catalogo valido limita le scene al materiale caricato; altrimenti usa la scena riconosciuta dal parlato. Quando il riconoscimento è ambiguo cerca nel copione caricato e mantiene solo intervalli ancorati alle trascrizioni. Questo ambito di ricerca non certifica che tutte le scene siano state girate.

Quando esistono tagli utilizzabili si abilita **Crea timeline**. Il click finale è esplicito; aprire un debug non richiede conferme. Regia, ritmo, take e alternative sono in tendine chiuse. Modifiche manuali effettive devono essere applicate prima della creazione. Una nuova analisi elimina le vecchie bozze. Senza tagli utilizzabili il comando resta disabilitato con una spiegazione.

Resta la preferenza per le ultime take riuscite e le ultime frasi complete dopo una ripartenza, compatibilmente con completezza, copertura del parlante e continuità. La pulizia non sostituisce una frase completa con una falsa partenza successiva; il deduplicatore conserva le differenze informative.

Verifica: suite JavaScript/Python; test headless sul renderer reale con bridge simulato (piano pronto, tendine chiuse, click esplicito, piano vuoto e correzioni pendenti). Il test grafico non equivale alla creazione nativa di una nuova timeline nel progetto utente. Nessuna modifica del progetto Resolve richiesta per questa consegna.

Il test del pannello è ripetibile con `node tools/smoke_automatic_panel.cjs` dalla cartella del prodotto: richiede Playwright e Edge. `PREMONTATO_PLAYWRIGHT_MODULE` e `PREMONTATO_BROWSER` permettono di indicare installazioni esistenti, senza aggiungere dipendenze al runtime distribuito.
