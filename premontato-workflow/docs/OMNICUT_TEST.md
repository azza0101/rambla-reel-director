# Omni-Cut test — installazione parallela

Omni-Cut test è la variante sperimentale derivata dal codice Premontato, inclusa Catalogazione giornata e debug scene. Non è incorporata in Auto-Cut. Il motore condiviso resta in premontato-workflow, evitando un fork duplicato da mantenere a mano.

Identità installazione: com.rambla.omnicut.test. Nome nel menu Resolve: RAMBLA Omni-Cut test. Prima versione: 0.1.0. Premontato resta com.rambla.premontato, con versione propria.

Dati e autosave separati: %APPDATA%/RAMBLA/Omni-Cut test. Nessuna migrazione automatica di sessioni, credenziali Groq o copioni. L'utente può aprire esplicitamente una copia del proprio progetto Premontato. Se si apre lo stesso file progetto nominato in due pannelli, restano validi i controlli di conflitto già presenti: per esperimenti usare Salva con nome.

Release: omnicut-test-vX.Y.Z, sempre prerelease e mai latest del repository. Asset: Install-OmniCut-Test.exe, OmniCutTest-X.Y.Z.zip e omnicut-test-update.json. Il pulsante Aggiorna ignora release Premontato/RMBL/Auto-Cut; Premontato ignora quelle Omni-Cut. I manifest e l'identità del pacchetto hanno nomi separati. Anche IPC, bootstrap, backup e pipe di avanzamento sono distinti.

L'autenticazione di pubblicazione usa GitHub CLI locale e non entra nei pacchetti. Il download privato riusa in sola lettura la credenziale protetta già prevista da Premontato, se disponibile sul PC; non modifica Auto-Cut e non copia chiavi nell'installer. L'SDK ufficiale non viene distribuito: viene copiato dall'installazione Resolve locale.

Installare l'EXE e aprire Workspace > Workflow Integrations > RAMBLA Omni-Cut test. Non usare l'installer Premontato per questa variante. Potrebbe servire riavviare Resolve perché il nuovo menu appaia.

## Build riproducibile

La build trasforma soltanto i file di identità esplicitamente elencati in tools/omnicut_test_product.cjs. Le decisioni di montaggio Python, gli encoder, i modelli e le dipendenze restano identici. Nessuna modifica ai prodotti già installati.

Eseguire tools/build_omnicut_test.ps1 indicando RuntimePath del runtime Premontato già verificato, Version e OutputDirectory opzionali. Lo staging viene verificato e rimosso al termine. Il builder produce installer, ZIP e manifest separati.

## Limiti di collaudo

Il packaging e il canale aggiornamenti vengono verificati con test automatici, installazione isolata e readback del pacchetto. Un test del motore via SDK non prova da solo l'avvio contemporaneo dei due pannelli né la chiusura/riapertura reale dopo UAC: questi risultati vanno indicati separatamente nel rapporto di consegna.

Suite di consegna: 163 test JavaScript e 186 test Python superati, nessuno saltato. I test del profilo eseguono il codice updater generato contro release miste e verificano il rifiuto di manifest dell’altro prodotto.

## Riuso progressivo dei miglioramenti Auto-Cut

Requisito dell'utente: poter portare miglioramenti Auto-Cut in Omni-Cut test senza copiarli a mano. La separazione dei prodotti non deve diventare una duplicazione dei motori.

Stato attuale: il profilo Omni-Cut riusa automaticamente il codice Premontato durante la build; non riusa ancora un core estratto da Auto-Cut. La base Auto-Cut ispezionata è il checkout locale api-first-v5-cloud, commit 1af7433d6e64c1e96d5f5e022de4680fd97b1c7d: il servizio FastAPI e il worker JSONL di Premontato hanno interfacce diverse. Non collegare la cartella dell'app installata né importare automaticamente l'ultimo HEAD.

Direzione per il nucleo comune: componenti puri per trascrizione normalizzata, segmentazione e ripartenze, ripetizioni, intervalli frame e controlli del piano. UI, regia narrativa, scelta inquadrature e applicazione Resolve restano adattatori specifici. Contratti espliciti: ID sorgente, FPS, intervalli sorgente [inizio,fine), parole originali, stato e provenienza. I timestamp di Resolve, compresi quelli quantizzati, non vanno reinterpretati implicitamente da funzioni Auto-Cut che assumono tempi ASR in secondi.

Ogni adozione deve indicare versione/commit del componente, eseguire i test del componente e i test di montaggio Omni-Cut (incluse reazioni V3 e gap), quindi produrre la sola release Omni-Cut. La versione comune va fissata nella build, non aggiornata al volo mentre il plugin è in uso. Interfacce e componenti vanno estratti prima di introdurre un file lock che dichiarerebbe una condivisione non ancora reale.

Collaudo di questa build: installer estratto e installato in cartella isolata, 18 moduli confrontati con la trasformazione sorgente, tutti i moduli Python identici. Test nativo dei moduli installati su Resolve 21.1.0.17: timeline OMNI-CUT TEST v0.1.0 nella cartella Omni-Cut test/v0.1.0/Test, due scene, gap, titoli V4, reazione V3 e audio mono corretti; timeline preesistenti preservate. Archivio aggiornamento valido, 4103 file. Apertura contemporanea dei pannelli e ciclo reale con UAC/riavvio non collaudati.
