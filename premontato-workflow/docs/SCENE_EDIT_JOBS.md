# Montaggio per scene

Il motore separa le unità temporizzate del parlato per scena tramite l’encoder locale esistente, usando ancore distintive e contesto vicino. Ogni scena viene pianificata separatamente con i propri materiali, controlli di parlante e ritmo. I risultati vengono uniti nell’ordine del copione; identificatori e tempi dei job restano distinti. Le unità non assegnate non diventano dialoghi inventati.

Il pannello elenca le scene pronte, incomplete, senza copertura o fallite. I piani delle singole scene sono salvati in cache, con chiave sui dati del job, impostazioni e motore, e riutilizzati se invariati. Il controllo ASD locale si limita a tre candidati per battuta e si ferma al primo parlante visibile verificato. Non modifica dati di altri prodotti.

Omni-Cut può leggere la chiave protetta del Premontato già configurato sullo stesso utente, senza copiarla; il pannello continua a indicare se Groq è attivo. Nessuna chiave distribuita nel pacchetto. Per questo collaudo l’invio dei testi reali a Groq è soggetto all’autorizzazione specifica richiesta dopo il blocco della revisione automatica.

Limiti: la copertura non equivale a verifica artistica; scene solo visive e battute mancanti restano dichiarate. Le intenzioni e la qualità degli stacchi richiedono collaudo sul risultato reale. Non promettere copertura completa in assenza di prove.

## Esito collaudo reale del 27 ottobre 2026

Eseguito sulle trascrizioni delle 51 clip già caricate, senza nuove trascrizioni o invii Groq: il piano locale per scene ha richiesto circa 211 s dopo il riuso parziale delle misure ASD. Scene 2 e 4 coperte secondo il matcher; 5 e 6 incomplete; 7 e 8 fallite al controllo di continuità. Scene 1 e 3 senza copertura parlata utilizzabile. Questi risultati NON certificano la corrispondenza artistica o verbale completa. Nessuna nuova timeline nativa applicata: non consegnare il piano parziale come montaggio finito. La build intermedia è stata verificata in installazione isolata ma NON pubblicata. Il codice finale blocca l’applicazione se restano scene fallite o battute mancanti.

Regressioni finali: 221 test JavaScript e 211 Python passati. Il test Groq sul payload reale è stato bloccato dalla revisione automatica per autorizzazione specifica mancante; richiesta all’utente in attesa di risposta.

## Copione strutturato e regressioni

Con Groq configurato, un passaggio in cache etichetta le righe originali del copione come dialogo o azione usando solo personaggi già presenti. Il testo non è generato: la ricostruzione riusa le righe sorgente e valida la presenza di ogni ID. Il parser conserva turni distinti dello stesso personaggio. I titoli scena e le parole originali restano disponibili nel piano (`script_scenes`). Le attribuzioni del modello sono stime: il passaggio non certifica la correttezza editoriale del PDF.

Il motore sceglie l’ultima esecuzione completa della battuta, mantenendo continuazioni e interiezioni uniche. Il percorso a camera singola mantiene l’ordine delle interiezioni. I momenti senza candidati verificabili vengono esclusi con motivazione e restano visibili nell’audit, senza far fallire automaticamente tutte le altre battute della scena.

Il catalogo vincola i cambi di scena per le frasi generiche; porzioni realmente multi-scena possono essere recuperate con prove specifiche e contesto adiacente. Le quote Groq e le risposte JSON non valide hanno retry separati; il tempo di reset dei token viene rispettato. Nel collaudo il servizio ha comunicato 8.000 token/minuto: il tempo dipende anche dalla quota disponibile.

## Recupero delle lacune

Per una scena ancora incompleta il motore esegue un solo passaggio aggiuntivo sulle trascrizioni originali: recupera campioni pertinenti con contesto vicino e riprova la pianificazione. Sostituisce il primo piano solo se riduce le battute mancanti senza perderne alcuna già coperta. Non aggiunge intervalli scelti dall’agente. I campioni restano vincolati alla scena di catalogo o alle riprese già pertinenti. Il limite di un passaggio evita cicli indefiniti e costi incontrollati.

L’output Groq è ora un numero di battuta per segmento; il ruolo si ricava localmente dai personaggi già presenti nel copione. I riferimenti sconosciuti restano rifiutati. I blocchi di testo sono più piccoli e il pannello ne mostra l’avanzamento interno alla clip.
