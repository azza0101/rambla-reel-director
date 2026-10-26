# Completezza battute e reazioni locali

Autorizzazione: l’utente richiede che il recupero delle battute parziali e la reazione prima della risoluzione diventino meccanismi del plugin, senza Codex. Conferme visive manuali restano disponibili e non costituiscono tagli decisi da Codex.

Scelta implementativa: preferire una ripetizione completa rispetto a una recente troncata, verificando apertura e chiusura nel contesto della battuta con l’encoder locale e i timestamp reali. Evitare inizialmente cuciture fra interpretazioni diverse: unire automaticamente frammenti di performance introduce discontinuità audio e nuove strutture del piano non necessarie quando esiste una ripetizione intera. Segnalare esplicitamente i casi non verificabili.

La reazione viene cercata immediatamente prima della risposta marcata Risoluzione, dopo un beat Tensione, in una stretta alternativa del personaggio che risponde: presenza visiva confermata, pausa RMS e nessuna parola trascritta sovrapposta, durata almeno pari al minimo inquadratura configurato. L’inserto conserva il proprio audio ambiente mono, non è un lip-sync sintetico né una classificazione dell’emozione. Nessun inserto se la pausa/copertura non è verificata. UI mostra still, durata, motivo e comando per escluderlo.

I dati delle nuove scelte fanno parte del piano salvato, vengono validati alla riapertura e applicati dall’adapter. Ricalcolo idempotente, modifiche manuali rispettate; massimo tre tracce video e tre mono come prima. Fasi visibili di verifica completezza e ricerca reazioni. Nessuna dipendenza o chiamata cloud nuova.
