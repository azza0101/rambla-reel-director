# Assistenza remota v0120

ASSISTENZA e disponibile in alto su app e bridge. Al primo avvio l'invio automatico e spento: l'utente puo attivarlo, disattivarlo o inviare manualmente un report. COPIA DEBUG nella finestra assistenza copia esclusivamente il report sanitizzato. Il precedente COPIA DEBUG del bridge rimane una copia locale dettagliata e non viene caricato automaticamente.

## Dati ammessi
Versione, UUID casuale dell'installazione, sistema operativo senza hostname, architettura, versione Python, componente/fase, categoria tecnica predefinita, tipo di eccezione noto, moduli/funzioni/righe del codice applicativo. Nessun messaggio grezzo, sorgente della riga, variabile locale, progetto, id del progetto, percorso personale, trascrizione, query, video, audio, chiave API o token.

Il report e validato nuovamente prima dell'invio. Dati estranei o alterati bloccano la spedizione. GitHub viene interrogato per verificare che il repository sia privato. Errori ripetuti della stessa installazione/versione vengono raggruppati; ricerca dell'issue esistente evita la duplicazione dopo retry. Limite 10 invii al giorno, massimo 3 per ciclo, retry con attesa crescente. La coda locale resta separata in rambla-data/diagnostics. Il lock di sistema coordina app e bridge, liberandosi anche se un processo si interrompe.

## Accesso GitHub
Si riutilizza il login GitHub CLI. Nessuna credenziale dell'account proprietario e distribuita. Opzionalmente il setup personale puo contenere un token fine-grained dedicato al solo repository, con Contents read e Issues write. Questo permette aggiornamenti e segnalazioni, non push di codice. Il token viene cifrato sul PC destinatario tramite DPAPI per l'utente Windows; non passa in argomenti di comando o log.

Il token incorporato nel setup personale resta comunque estraibile dall'EXE: consegnarlo solo a destinatari fidati. Non pubblicare mai la variante personale, il JSON provisioning o il token. Per prepararla salvare il nuovo token in .runtime-temp/github-distribution-token.txt, aggiungerlo al provisioning come github_distribution_token e usare il normale build personale. Token OAuth/classic completi vengono rifiutati dal provisioning. La revoca o scadenza interrompe l'accesso finche il token non viene sostituito.

## Flusso di assistenza
Errore -> coda locale -> issue privata -> revisione durante una sessione di assistenza -> patch e test -> release -> SEARCH UPDATE. Nessuna sessione Codex viene avviata dal programma e nessun agente e tenuto in ascolto continuamente. Nessuna correzione remota o comando arbitrario viene eseguito dai report. Nessuna chiamata AI e necessaria alla diagnostica.

Il collegamento GitHub e l'invio di un errore non impongono la chiusura di Resolve e non modificano le timeline.
