# Omni-Cut test — installazione parallela

Versione 0.2.0: catalogazione per clip originali intere, spostate nei bin scena dopo Applica al Media Pool; visione locale opzionale e schede verde/giallo con preview. Sostituisce il flusso SELECTS della 0.1.x. Dettagli e requisiti: [OMNICUT_VISUAL_CATALOG.md](OMNICUT_VISUAL_CATALOG.md).

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

## Riuso progressivo dei miglioramenti Premontato

L'utente ha chiarito che il prodotto di riferimento è Premontato, non Auto-Cut. Omni-Cut test è generato dallo stesso albero sorgente Premontato con un profilo di build: il motore non viene duplicato né ricopiato a mano.

Per adottare un miglioramento: portare sul branch Omni-Cut il commit Premontato verificato, rieseguire le suite e il collaudo pertinente, incrementare la versione Omni-Cut e ricostruire con build_omnicut_test.ps1. Il builder applica soltanto le differenze di identità; worker, planner, catalogazione, modelli e dipendenze vengono ereditati dal sorgente aggiornato. Non fare merge su main senza autorizzazione.

L'adozione è fissata al commit della build: aggiornare Premontato sul PC non modifica al volo Omni-Cut, e viceversa. Ogni pacchetto può essere confrontato con il commit sorgente e distribuito sul proprio canale. Nessuna estrazione da Auto-Cut è necessaria.

Collaudo di questa build: installer estratto e installato in cartella isolata, 18 moduli confrontati con la trasformazione sorgente, tutti i moduli Python identici. Test nativo dei moduli installati su Resolve 21.1.0.17: timeline OMNI-CUT TEST v0.1.0 nella cartella Omni-Cut test/v0.1.0/Test, due scene, gap, titoli V4, reazione V3 e audio mono corretti; timeline preesistenti preservate. Archivio aggiornamento valido, 4103 file. Apertura contemporanea dei pannelli e ciclo reale con UAC/riavvio non collaudati.

## 0.1.1 — Match girato con copione

Il pulsante esegue inventario, recupero delle trascrizioni e confronto semantico locale. Mostra una riga apribile per clip con le scene proposte; aprendo la riga si vedono gli intervalli, il parlato confrontato e i menu per cambiare scena. Il confronto continua a usare encoder, contesto e battute vicine: le parafrasi non richiedono corrispondenze testuali esatte.

Le proposte vengono incluse nel riepilogo senza conferme individuali. Applica al Media Pool è l'unica azione finale: crea bin e SELECTS con gli intervalli sorgente. Le porzioni senza corrispondenza restano escluse finché non si assegna facoltativamente una scena. Anche con clip fallite si possono applicare i risultati parziali. Non è una garanzia di classificazione corretta: scene mute o senza contesto sufficiente restano da assegnare.

Correzioni: intestazioni Scena 1. / Scena 2: e cue con parentesi minuscole; layout PDF deciso per singolo cue, senza contaminazione da titoli centrati. Le modifiche alla struttura letta invalidano soltanto gli abbinamenti e riusano le trascrizioni. Segmenti Resolve a durata zero vengono conservati come testo senza intervallo utilizzabile; gli altri segmenti della clip non vengono scartati. Gli errori delle clip sono visibili nei dettagli locali.

Collaudo 26 ottobre 2026: 169 test JavaScript e 189 Python superati. Sul catalogo reale, in una copia del checkpoint e senza scritture Media Pool: 4 scene lette, 51 sorgenti, 43 con trascrizioni riusabili, 8 senza parlato utilizzabile, 11,5 secondi, nessuna chiamata ASR o LLM. Due scene hanno proposte utilizzabili; i conteggi degli intervalli non rappresentano una misura di accuratezza. Test nativo Resolve 21.1.0.17 separato nello stesso progetto con una sorgente sintetica: due scene proposte, SELECTS create e rilette a frame 10–60 e 80–140 con audio, seconda applicazione saltata senza duplicati, timeline e impostazioni preesistenti preservate. Nessun nuovo progetto creato.

## 0.2.7 — Catalogo e montaggio

Vedere [contesto, metadati e collaudo](OMNICUT_CATALOG_EDIT_CONTEXT.md). Le indicazioni storiche su SELECTS della 0.1.1 sono superate: la catalogazione attuale sposta solo clip intere.
