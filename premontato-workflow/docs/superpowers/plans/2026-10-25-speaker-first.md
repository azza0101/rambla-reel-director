# Premontato: montaggio automatico centrato sul parlante

Obiettivo approvato: primo montaggio rapido, apertura master, piani sul parlante verificato da audio/video, strette mantenute nel crescendo, larga alla risoluzione. Nomi e riconoscimento facciale non obbligatori.

- [ ] Integrare evidenza ASD locale nel selettore. Manuali prioritari; confronti solo per piani utili, esclusi apertura/risoluzione e battute troppo brevi; cache per file/intervallo/modello, ripiego master per incertezza. Test selezione, errore modello, durata breve, stile e latest take.
- [ ] Integrare sessione e UI: avanzamento per candidato, nessun obbligo di nominare persone, still e SFace su richiesta, revisione automatica non bloccante salvo modifiche manuali. Test flusso e persistenza.
- [ ] Condividere audio PCM delle analisi locali; non generare proxy obbligatori (benchmark primo avvio sfavorevole). Test fingerprint e audio invariato.
- [ ] Collaudo reale da autosave senza nomi/correzioni manuali: 12 battute, apertura larga, primi piani corretti nei passaggi controllati, chiusura e tagli validi; timeline nuova v0.10.0, massimo tre tracce video e audio mono, sorgenti intatte. Misurare primo avvio e cache.
- [ ] Pacchetto autonomo: modello ONNX MIT, licenze e provenienza, versione visibile, suite, build e aggiornamento dedicato. Pubblicazione autorizzata solo canale Premontato e ramo PR19, mai merge/main/latest.

Ruling: esecuzione diretta senza ulteriori agenti, come richiesto per contenere i crediti. Test locali non equivalgono a test GUI o garanzia universale di qualità.
