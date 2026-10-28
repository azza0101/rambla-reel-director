# Montaggio per scene — stato verificato al 28 ottobre 2026

## Stato attuale

Branch: fix/omnicut-scene-isolated-edit-20261027, PR #32. Codice del pacchetto candidato: a567096. Nessun merge su main, nessuna release pubblicata e nessuna sostituzione del plugin attivo.

La scena 5 è stata realmente pianificata dal software e applicata in Resolve. Il collaudo globale dell’ultima versione NON è completato: è stato interrotto alla quota giornaliera Groq. Non dichiarare che tutte le scene, tutte le inquadrature o il primo passaggio dell’intera giornata funzionino già correttamente e rapidamente.

## Meccanismo integrato

Il preparatore conserva tempi e indici originali delle parole. Un respiro interno non spezza più automaticamente una frase dopo 10 frame: il confine è espresso nel frame rate della sorgente, con punteggiatura e durata massima ancora rispettate. Il parser conserva turni separati dello stesso personaggio. Con Groq configurato, una classificazione in cache distingue dialoghi e azioni usando gli ID delle righe originali, senza riscrivere il testo.

L’encoder locale assegna porzioni temporizzate alle scene tramite contenuto distintivo e contesto vicino. Una clip può appartenere a più scene. Pronomi e inviti generici non sono ancore autonome; seguono il contesto oppure restano senza copertura. Catalogo e identità del media sono verificati prima del riuso. Non si spostano parole o intervalli per farli corrispondere al copione.

Ogni scena viene pianificata indipendentemente. Groq assegna numeri di battuta agli ID originali, con ruoli ricavati dal copione e validazione degli ID. Il software sceglie il contenuto della battuta prima della camera: un volto visibile o una master non possono prevalere su un testo meno pertinente. Precisione, copertura e pertinenza sostituiscono il precedente premio alla sola lunghezza del testo. Le ultime take sono preferite fra esecuzioni comparabili.

La deduplicazione locale confronta anche parafrasi: due esecuzioni equivalenti non diventano automaticamente due momenti narrativi. Le continuazioni uniche e le interiezioni significative restano preservate. La scelta di camere, parlante attivo, continuità e reazioni usa i moduli esistenti. Le stime facciali e semantiche non sono certificazioni artistiche.

Una scena incompleta ha un solo recupero aggiuntivo nelle trascrizioni originali: contesto vicino e riclassificazione mirata degli ID originali. Per lunghe battute distintive si possono controllare clip della scena di catalogo immediatamente adiacente, soltanto con riscontri di contenuto; un invito generico non abilita questo recupero. Il secondo piano sostituisce il primo solo se riduce le lacune senza perderne altre già coperte.

Le scene complete hanno checkpoint versionati per dati, impostazioni e motore. Errori temporanei non diventano risultati definitivi; classificazioni e misure valide vengono riusate. L’assemblaggio segue l’ordine del copione e può includere gap e titoli scena. Un piano con lacune non è presentato come montaggio completo. Scene solo visive e dati trascritti insufficienti restano limiti aperti.

## Cause accertate

- Un’unica scena dominante poteva essere cercata in tutte le riprese.
- Il PDF poteva mescolare azioni e dialoghi o fondere turni distinti.
- Pausa di 10 frame e frammenti brevi indebolivano il contesto.
- Evidenza del parlante e quantità di parole potevano precedere la correttezza del contenuto.
- Ripartenze parafrasate potevano essere conservate entrambe.
- Frasi generiche attiravano materiale di altri episodi.
- Il servizio distingueva quote al minuto e giornaliere, mentre il client ripeteva l’attesa breve.

Le correzioni sono regole generiche con regressioni sintetiche: nessuna eccezione su nomi di file privati, personaggi o timecode; nessun piano di taglio scritto dall’agente.

## Groq, quote e credenziali

Il 28 ottobre l’autore ha autorizzato esplicitamente l’invio dei soli testi di copione e trascrizioni. Nessun video, audio o immagine inviato. La chiave locale esistente non viene mostrata o distribuita. Omni può leggere la chiave protetta del Premontato dello stesso utente senza copiarla.

Quota osservata del modello: 8.000 token/minuto e 200.000 token/giorno. Alla diagnosi erano usati 199.797 token e la richiesta reale ne richiedeva 1.312. Una richiesta sintetica minima riusciva ancora: le intestazioni al minuto non bastavano a diagnosticare il blocco giornaliero.

Classificazione, copione e passaggio editoriale ora riconoscono la quota giornaliera con errore GROQ_DAILY_QUOTA e attesa indicata dal servizio. Il ciclo per scene interrompe i tentativi sulle successive; i checkpoint completati restano riusabili. I retry per quota al minuto restano distinti da quelli per JSON non valido. Nessuna organizzazione, chiave o messaggio server integrale viene esposto.

## Verifiche effettive

231 test JavaScript e 232 Python passati. Inclusi: confini fra scene, inviti generici, sorgenti multi-scena, parafrasi duplicate, continuazioni uniche, tempi originali, selezione del contenuto prima della camera, quote nelle tre fasi Groq e riuso dei checkpoint alla ripresa.

Resolve Studio 21.1.0.17, progetto test-mcp, senza automazione del mouse:

- Assemblaggio precedente PARZIALE delle scene 2/4/5/8: quattro titoli e tre gap di due secondi; conservate 46 timeline preesistenti. Rilettura del 28 ottobre confermata, senza duplicarlo inutilmente.
- Nuova scena 5 con il codice corrente di selezione: timeline OMNI-CUT TEST v0.2.12 - SCENA 5 - TEST CONTESTO, ID 4a3f3dfd-0712-42da-946d-7f3218fcc330, cartella Omni-Cut test / v0.2.12 / Test. Quattro segmenti e relativi audio, un titolo e tre tracce mono. Verificati gli intervalli sorgente e la conservazione delle 47 timeline precedenti e delle impostazioni.
- La 0.2.13 aggiunge il fix della quota; non cambia la scelta dei tagli collaudata nella 0.2.12. Il test nativo della scena 5 non è un collaudo globale dell’intero copione.

## Tempi osservati e limiti

Sul materiale di 51 clip: recupero mirato intermedio 124,5 s senza riduzione delle lacune; riclassificazione intermedia dopo il cambio delle frasi 1.282,9 s, circa 21,4 minuti, con molte attese Groq. Questi sono test del codice intermedio e non certificano il montaggio globale corrente. Prova mirata della scena 5 sulle nuove regole: 32,8 s riusando gran parte della cache.

Le unità di analisi del girato sono passate da 2.524 a 2.368, quelle di al massimo due parole da 970 a 854. Non è una misura di qualità artistica né una garanzia di accelerazione universale. Il primo passaggio, il consumo del budget Groq e le scene non ancora coperte richiedono ulteriore collaudo.

## Build di prova

La build locale 0.2.12 dal commit c621a40 ha superato validazione ZIP, vecchio updater, installazione isolata e probe runtime: SDK recuperato localmente, nessuna credenziale distribuita, altri prodotti preservati. La nuova 0.2.13 dal commit a567096 include il fix giornaliero e ha superato gli stessi controlli isolati: 4.111 file validati, 18 moduli JavaScript corrispondenti, worker Python identico al sorgente e probe runtime riuscito. EXE locale in dist-omnicut-test-0213/Install-OmniCut-Test.exe; SHA-256 dello ZIP: 6fa312f9d5dfc4fb0b95a23d5f2113fc8e8eeb54f50ae1c12230c2d43206599d. Nessuna pubblicazione automatica sul canale stabile o come latest del repository.
