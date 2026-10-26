# Changelog

## 0.12.1 — trial: debug scene

- Gap di due secondi tra scene e numero scena su V4 per tutta la durata.
- Opzione disattivabile, salvata nel progetto; piano di montaggio invariato.
- Titoli alpha locali con cache e verifica nativa di durata e traccia.


## 0.12.0 — Catalogazione giornata (prova)

- Inventario ricorsivo indipendente da clip selezionate e timeline aperta.
- ASR Resolve seriale, riuso trascrizioni, risultati progressivi e checkpoint locali.
- Matching locale lessicale/semantico per intervalli multi-scena e ripartenze, con revisione conservativa.
- Compatibilità con quantizzazione Resolve: preroll di un frame conservato nei dati grezzi e limitato ai frame disponibili; parole puntuali conservate senza inventare durate, intervalli incerti da verificare.
- Correzione scena/range, preview confermata, bin scena e SELECTS con readback audio/video, retry/idempotenza e originali preservati.
- Pannello separato, stato provvisorio, packaging con moduli esplicitamente ammessi. Nessuna nuova dipendenza, modello o chiamata Groq per catalogare.

Build sperimentale: molte proposte reali richiedono revisione. Installer collaudato in destinazione separata; aggiornamento con elevazione UAC non certificato. Dettagli in docs/DAY_CATALOG.md e nel rapporto di collaudo.
