# Montaggio per scene — stato verificato al 27 ottobre 2026

## Cause accertate e correzioni integrate

Il vecchio percorso sceglieva una scena dominante e cercava le sue battute in tutti i materiali. Ora separa le unità temporizzate con l’encoder locale, pianifica ogni scena indipendentemente e assembla nell’ordine del copione. Una clip può contenere porzioni di più scene. Frasi generiche non bastano per superare il contesto di catalogo; servono ancore specifiche.

Il parser separa turni distinti dello stesso personaggio. Con Groq configurato un passaggio in cache distingue dialoghi e azioni usando gli ID delle righe originali; non riscrive il testo. I titoli e i personaggi del copione restano disponibili nel piano. Le attribuzioni del modello sono stime, non una certificazione del PDF.

La deduplicazione conserva l’ultima esecuzione completa e le continuazioni uniche. Il confronto semantico locale riconosce anche ripartenze formulate con parole diverse: prima potevano essere scambiate per nuovi momenti. Gli intervalli provengono sempre dalle parole originali, mai da timestamp generati dal modello o scelti dall’agente.

Le scene con battute mancanti hanno un solo recupero aggiuntivo: ricerca nelle trascrizioni originali, contesto vicino e riclassificazione mirata di ID originali, senza forzare un abbinamento. Il nuovo piano è accettato solo se riduce le lacune senza perdere battute già coperte. Errori temporanei del recupero sono riprovabili alla successiva esecuzione, non diventano checkpoint definitivi. Le scene complete riusano la cache.

Groq restituisce numeri di battuta; il ruolo si ricava dai personaggi del copione. Gli ID sconosciuti sono rifiutati. I blocchi sono di 20 unità, con avanzamento e retry separati per quota e JSON non valido. Viene rispettato il reset dei token comunicato dal servizio (nel test: 8.000 token/minuto). Omni può leggere la chiave protetta del Premontato dello stesso utente senza copiarla. Nessuna credenziale è inclusa nei pacchetti.

## Test automatici

227 test JavaScript e 221 Python passati nell’ultima esecuzione. Sono coperti isolamento delle scene, sorgenti multi-scena, ripartenze, parafrasi duplicate, continuazioni uniche, intervalli originali, ripresa dopo errore e rifiuto dei piani incompleti come montaggi finiti. Non equivalgono a verifica artistica del girato reale.

## Collaudo reale e nativo

Dati reali: 51 clip già caricate nel progetto test-mcp, copione di otto scene. Nessuna nuova trascrizione eseguita. Un primo piano Groq ha richiesto circa 343 s; il successivo recupero circa 248 s. Il test locale aggiornato, con classificazioni e misure già in cache e rete disabilitata, ha richiesto 12,6 s. Sono tempi osservati sul materiale e sullo stato di cache specifici, non stime universali per minuto di video.

Nel risultato locale aggiornato le scene 2, 4, 5 e 8 risultano coperte secondo il motore. La 6 conserva una lacuna; la 7 quattro. La 3 non ha dialogo utilizzabile nelle trascrizioni correnti; la 1 non ha copertura parlata. Alcune frasi del PDF non compaiono letteralmente nelle trascrizioni: l’assenza letterale non dimostra che non siano state recitate o parafrasate. Il recupero mirato esterno aggiornato resta da verificare: un nuovo invio è stato bloccato dalla revisione automatica per autorizzazione non verificabile nel contesto attuale, ed è stata richiesta conferma specifica. Nessun aggiramento del blocco.

Resolve Studio 21.1.0.17: applicazione SDK nativa realmente riuscita delle scene complete 2, 4, 5 e 8, in una nuova timeline di prova denominata PARZIALE, con quattro titoli scena e tre gap di due secondi. ID f97f95ce-4cbc-4202-9bea-b3303a3be392. Verificati rilettura sorgenti e intervalli, tre tracce audio mono, conservazione delle 46 timeline precedenti e delle impostazioni del progetto. Collocazione: Omni-Cut test / v0.2.11 / Test. Nessun controllo del mouse. Una precedente timeline diagnostica con ripetizioni è stata rinominata SCARTATA; non è il risultato finale.

Il test nativo prova l’assemblaggio e la conservazione del progetto, non il completamento delle scene ancora incomplete. Il piano dell’intero copione resta bloccato per la creazione finché mancano battute o scene falliscono; non viene presentato come film finito. Restano da validare qualità editoriale globale, scene solo visive e casi con trascrizione insufficiente.

## Consegna e distribuzione

Branch fix/omnicut-scene-isolated-edit-20261027, PR #32, senza merge su main. La build isolata 0.2.11 dal commit 6658d09 ha superato smoke installer, controllo integrità e compatibilità del vecchio updater; NON include le successive correzioni di recupero mirato/deduplicazione semantica. Non è stata pubblicata una nuova release o aggiornata l’installazione attiva. Non distribuire una build precedente dichiarandola equivalente al codice corrente.
