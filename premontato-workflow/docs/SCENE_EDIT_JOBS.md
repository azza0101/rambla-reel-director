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

## Ricontrollo autorizzato del 28 ottobre 2026

L’autore ha confermato esplicitamente l’invio a Groq dei soli testi del copione e delle trascrizioni, usando la chiave locale esistente; nessun media inviato. Il recupero mirato sul codice cafe945 è terminato in 124,5 s senza ridurre le sei lacune già rilevate. Questo test non certifica il montaggio completo.

È stato riprodotto un ulteriore difetto nel preparatore delle frasi: il limite fisso di 10 frame separava anche parole della stessa frase dopo un normale respiro (0,4 s a 25 fps), indebolendo il contesto dato al classificatore. Il limite ora è di un secondo espresso nel frame rate della sorgente; punteggiatura, separazione dei segmenti e limite massimo dell’unità restano applicati. I tempi e gli indici delle parole originali non cambiano. Sul materiale di prova le unità scendono da 2.524 a 2.368 e quelle di al massimo due parole da 970 a 854. Non è una garanzia di corrispondenza del parlato.

227 test JavaScript e 224 Python passati dopo questa correzione. Avviata una nuova classificazione reale; l’esito complessivo non è ancora certificato. La verifica nativa in sola lettura del 28 ottobre conferma i 19 elementi base della timeline PARZIALE, i quattro titoli e le tre tracce mono, con 47 timeline totali; il piano precedente delle scene complete era identico e non è stata creata un’altra copia.

## Priorità del contenuto e contesto degli inviti

Il precedente selettore del riferimento dava precedenza al parlante visibile, e premiava il numero di parole osservate, prima di verificare la corrispondenza con la battuta. Il contenuto ora viene selezionato con pertinenza semantica e precisione/copertura del testo; la camera e le ultime take sono preferenze fra varianti comparabili. Non si forza una master dal contenuto meno pertinente. La successiva scelta delle inquadrature resta distinta.

Gli inviti generici e i pronomi non formano ancore autonome di scena. Senza un’ancora distintiva vengono mantenuti nel contesto vicino o dichiarati senza copertura. Nel recupero di una lunga battuta distintiva possono essere controllate anche clip catalogate nella scena immediatamente adiacente: occorrono identità del media verificata e riscontri di contenuto, non soltanto un punteggio semantico alto. Gli inviti generici non aprono questo recupero tra scene.

227 test JavaScript e 232 Python passati. Prova mirata reale della scena 5 con queste regole: 32,8 s, quattro battute coperte secondo il motore; il riferimento e l’invito provengono ora dall’episodio pertinente e la prosecuzione viene recuperata nei materiali adiacenti. Nessun piano o intervallo scritto dall’agente. Si tratta di un test mirato; non certifica il montaggio dell’intero copione. La riclassificazione globale avviata prima delle ultime modifiche resta un test del codice precedente, non va presentata come collaudo globale delle nuove regole.

## Quota giornaliera e stato finale del 28 ottobre

La verifica globale del codice corrente è stata interrotta alla quota giornaliera effettiva del modello Groq: limite 200.000 token, 199.797 già usati e 1.312 richiesti. La richiesta minima poteva ancora riuscire, mentre quella reale veniva rifiutata: il limite al minuto non spiegava il blocco. Le intestazioni al minuto non bastano a diagnosticare la disponibilità giornaliera.

Classificazione, strutturazione del copione e passaggio editoriale ora distinguono la quota giornaliera da quella al minuto. La quota giornaliera interrompe i retry con errore GROQ_DAILY_QUOTA e attesa indicata dal servizio. Il ciclo per scene propaga il blocco senza provare inutilmente tutte le successive; i checkpoint delle scene già completate vengono riusati alla ripresa. Nessuna chiave, organizzazione o contenuto del messaggio server viene mostrato.

231 test JavaScript e 232 Python passati, comprese le quote e i checkpoint. La timeline nativa della scena 5 è stata realmente creata e aperta: OMNI-CUT TEST v0.2.12 - SCENA 5 - TEST CONTESTO, ID 4a3f3dfd-0712-42da-946d-7f3218fcc330, quattro segmenti e audio, un titolo, tre tracce mono; verificate le 47 timeline precedenti e le impostazioni. La 0.2.13 aggiunge la gestione della quota senza cambiare la scelta dei tagli verificata nella 0.2.12.

La riclassificazione intermedia senza il nuovo selettore di contenuto ha richiesto 1.282,9 s, circa 21,4 minuti. I relativi conteggi non sono una certificazione del codice corrente. Il test mirato della scena 5 sul codice corrente ha richiesto 32,8 s. La velocità del primo passaggio e il montaggio globale rimangono da certificare; non dichiarare che tutte le scene funzionino. Nessun aggiornamento pubblicato o installazione attiva sostituita. La build 0.2.12 era stata verificata in isolamento; una nuova build 0.2.13 deve includere il fix delle quote.
