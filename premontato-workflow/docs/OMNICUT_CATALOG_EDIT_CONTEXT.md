# Omni-Cut test 0.2.7 — Contesto catalogo e montaggio

Applica al Media Pool aggiorna i bin e salva cinque campi personalizzati: OmniCut Scena, OmniCut Ruolo, OmniCut Trascrizione, OmniCut Tags, OmniCut Data. Il JSON completo rimane anche nel checkpoint locale, collegato al media ID. Il journal viene salvato prima della scrittura e il risultato viene riletto; eventuali errori sono avvisi, non cancellano il catalogo né fermano le altre clip. Ripetere Applica è idempotente e aggiorna anche le clip già nel bin giusto.

Le modalità Search All e Metadata Search di IntelliSearch includono metadati inseriti e personalizzati secondo la [guida ufficiale, pagina 40](https://documents.blackmagicdesign.com/SupportNotes/DaVinci_Resolve_21_New_Features_Guide.pdf). Cercare per esempio OMNICUT_SCENA_03 oppure DETTAGLI E B-ROLL. Visual Only usa l’indice AI distinto. Non scriviamo nei dati interni facciali/visivi: l’API documentata AnalyzeForIntellisearch avvia l’analisi, non importa descrizioni esterne nell’indice. La ricerca nel pannello Resolve non è stata collaudata con input UI in questa consegna.

Il campo JSON usa escape Unicode per evitare alterazioni attraverso l’SDK. I campi umani non vengono riscritti. Se i metadati personalizzati non sono disponibili, il fallback aggiunge un blocco OmniCut in Comments, preservando gli appunti ASCII; annotazioni Unicode vengono conservate senza riscrittura e l’assenza di fallback è segnalata. Un probe iniziale su Comments ha evidenziato una conversione del separatore Unicode tramite SDK Python: il valore precedente è stato ripristinato. Il collaudo finale preferisce metadati personalizzati e sintesi ASCII.

## Uso

1. Aggiornare Omni-Cut test alla 0.2.7.
2. Nel catalogo ripristinato premere Applica al Media Pool: non occorre rifare trascrizione o classificazione solo per scrivere i metadati.
3. In Analizza scena scegliere le riprese e lo stesso copione completo; premere Analizza e prepara montaggio. I testi validi del catalogo sono riusati.
4. Le riprese catalogate senza trascrizione non bloccano i dialoghi: compaiono sotto Materiali visivi dal catalogo, chiuso inizialmente. Anteprime caricate solo al clic. Il comando Trascrivi selezionate rimane disponibile per un retry esplicito.

Un copione diverso, un estratto con fingerprint differente, un altro progetto o un file cambiato non riusano il contesto precedente. L’assenza di trascrizione è distinta dall’assenza di audio: le otto clip del test contengono tutte un flusso audio PCM, senza testo utilizzabile nel catalogo. Le clip visive hanno automatic_insert:false: sono conservate nel pool del piano, non inserite automaticamente senza un intervallo/azione pertinente. Una selezione solo visiva mostra il materiale e spiega il limite, senza inventare una timeline. Planner dialoghi, reazioni V3 e regia esistenti restano invariati.

## Collaudo 27 ottobre 2026

- 213 test JavaScript e 205 Python superati, nessuno saltato. Inclusi percorso IPC Analizza, cache, guardie identità, clip senza testo, pool senza dialoghi, metadati idempotenti, errori non bloccanti e tendina/preview lazy.
- Resolve Studio 21.1.0.17, progetto corrente preservato: 51 sorgenti verificate, 43 trascrizioni riusate, 8 materiali senza testo (6 B-roll, 2 coperture di scena), 0 ASR, 0 chiamate esterne, 0 scritture Media Pool nel test di preparazione. Primo passaggio 958 ms, ripetizione 923 ms: tempi del preflight, non dell’intero montaggio. Il checkpoint è copiato per il test.
- Probe nativo su clip sintetica temporanea nello stesso progetto: scrittura/rilettura cinque campi personalizzati, JSON Unicode, note umane preservate, seconda scrittura invariata. Clip e bin sintetici rimossi, progetto salvato; timeline e impostazioni preservate. Nessun nuovo progetto creato.
- Non sono stati testati un nuovo montaggio completo con queste 51 clip, la ricerca via UI IntelliSearch o il ciclo reale UAC/chiusura/riapertura del pannello.

## Resolve 21.1.2: ricerca separata

L’[annuncio Blackmagic](https://md.linkedin.com/company/blackmagic-design/) del 27 ottobre 2026 conferma scripting per spostare, rifilare/estendere clip, eliminare gap e silenzi, copiare attributi, gestire effetti audio/video e proprietà di transizione, oltre ad album foto. Le firme SDK 21.1.2 non sono ancora verificate localmente e la versione non è stata installata. Non è stata trovata conferma di nuove API per popolare/interrogare l’indice visivo o facciale IntelliSearch. Nessuna nuova dipendenza dalla 21.1.2 in questa build.
