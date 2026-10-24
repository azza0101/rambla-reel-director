# Premontato 0.6.0 — pause e durata inquadrature

## Funzionalità
Analisi locale dell’energia audio a finestre 20ms, soglia adattiva, intervalli quieti >=180ms. Non è un classificatore del parlato né un riconoscitore di reazioni. I timestamp delle parole costituiscono protezioni: non si rimuove un intervallo che li attraversa. Margini quieti e pause interne vengono accorciati solo quando confermati dall’audio; si mantengono piccoli margini naturali. Pausa residua obiettivo predefinita 0.45s, durata minima della copertura obiettivo 1.2s. Questi obiettivi hanno eccezioni per proteggere parole, interventi brevi e tempi recitati.

Pause esplicite del copione e blocco manuale per battuta impediscono la compressione; eventuale attesa viene estesa soltanto entro un vuoto realmente misurato e senza includere parole successive. Le risposte brevi mantengono la stessa copertura solo se esiste un’alternativa di qualità comparabile, altrimenti sono segnalate. I valori si ricalcolano dal piano originario, evitando accumulo di tagli quando cambiano le impostazioni. Le correzioni manuali dei frame vengono rispettate.

## Dipendenza audio
Usa FFmpeg locale già installato, cercato nel PATH o in C:/Program Files/FFmpeg/ffmpeg.exe. FFmpeg NON viene ridistribuito in questo pacchetto. Se assente o se la decodifica fallisce, la UI segnala audio non disponibile e conserva le pause. Nel computer di test è presente e sono stati decodificati tutti i tre file. Nessun download runtime, credito o chiamata AI per questa funzione. Modelli e runtime Python rimangono inclusi offline.

## Verifiche
- 39 test unittest Python; 44 test Node; 9 contratti del pacchetto.
- Audio reale dei tre file: ~9s prima analisi; cache locale per le successive. 4.56s rimossi dal piano di riferimento, una pausa protetta e una copertura breve segnalata. Nessuna parola trascritta intersecata dai tagli verificati.
- Resolve test-mcp: timeline tecnica nuova con 17 video + 17 audio, intervalli esatti, durate A/V corrispondenti, 1846 frame a 25fps (73.84s). Timeline precedente ripristinata.
- Browser Edge headless con renderer originale, sessione e worker reali: 12 righe, modifica opzioni, pausa manuale, pulsante timeline abilitato; nessun errore pagina, layout verificato fino a 680px. Le API di selezione e analisi della UI sono alimentate da fixture locali: non è un collaudo end-to-end dell’host Electron.

## Limiti
Non identifica chi parla né le reazioni visive. I rumori e gli errori della trascrizione possono rendere la scelta più conservativa; nessuna qualità editoriale o ascolto umano completo del montaggio viene dichiarato. Il minimo riguarda coperture consecutive della stessa camera, non un allungamento artificiale di ogni battuta. Release sperimentale.

Correzione UTF-8 del worker: prima il PDF arrivava al pannello con 61 caratteri sostitutivi; dopo la correzione 0 caratteri sostitutivi e 55 accenti italiani preservati. Test di regressione sull’identificatore Unicode interno. Flusso reale Session → worker → PDF → scena → inquadrature/audio in cache già misurate → piano → ritmo: 12/12 candidati, nessuna parola trascritta intersecata dalle rimozioni.
