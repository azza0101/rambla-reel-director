# Montaggio per scene

Il motore separa le unità temporizzate del parlato per scena tramite l’encoder locale esistente, usando ancore distintive e contesto vicino. Ogni scena viene pianificata separatamente con i propri materiali, controlli di parlante e ritmo. I risultati vengono uniti nell’ordine del copione; identificatori e tempi dei job restano distinti. Le unità non assegnate non diventano dialoghi inventati.

Il pannello elenca le scene pronte, incomplete, senza copertura o fallite. I piani delle singole scene sono salvati in cache, con chiave sui dati del job, impostazioni e motore, e riutilizzati se invariati. Il controllo ASD locale si limita a tre candidati per battuta e si ferma al primo parlante visibile verificato. Non modifica dati di altri prodotti.

Omni-Cut può leggere la chiave protetta del Premontato già configurato sullo stesso utente, senza copiarla; il pannello continua a indicare se Groq è attivo. Nessuna chiave distribuita nel pacchetto. Per questo collaudo l’invio dei testi reali a Groq è soggetto all’autorizzazione specifica richiesta dopo il blocco della revisione automatica.

Limiti: la copertura non equivale a verifica artistica; scene solo visive e battute mancanti restano dichiarate. Le intenzioni e la qualità degli stacchi richiedono collaudo sul risultato reale. Non promettere copertura completa in assenza di prove.

## Esito collaudo reale del 27 ottobre 2026

Eseguito sulle trascrizioni delle 51 clip già caricate, senza nuove trascrizioni o invii Groq: il piano locale per scene ha richiesto circa 211 s dopo il riuso parziale delle misure ASD. Scene 2 e 4 coperte secondo il matcher; 5 e 6 incomplete; 7 e 8 fallite al controllo di continuità. Scene 1 e 3 senza copertura parlata utilizzabile. Questi risultati NON certificano la corrispondenza artistica o verbale completa. Nessuna nuova timeline nativa applicata: non consegnare il piano parziale come montaggio finito. La build intermedia è stata verificata in installazione isolata ma NON pubblicata. Il codice finale blocca l’applicazione se restano scene fallite o battute mancanti.

Regressioni finali: 221 test JavaScript e 211 Python passati. Il test Groq sul payload reale è stato bloccato dalla revisione automatica per autorizzazione specifica mancante; richiesta all’utente in attesa di risposta.
