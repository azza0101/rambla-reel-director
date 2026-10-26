# Catalogazione giornata V1 — collaudo Windows/Resolve

Data: 26 ottobre 2026. Build di prova 0.12.0, non release stabile.

## Provenienza e perimetro

Spec/piano PR22, design commit 1300fe9196918eea195fab17bae19adbf43b955e, letti integralmente. Ultimo feat/premontato-workflow verificato prima di implementare: 52244b93f9437b04e430132d918fe744f8b02bb0. Branch separato feat/premontato-day-catalog-20261026 parte da 70f2689bdf12e9579846bb744de8e28a0f6f19d5 (PR23, integra PR20/21): dipendenza esplicita, nessuna sovrascrittura dei branch originali. Solo premontato-workflow/. Nessun merge/main, nessuna modifica ad altri prodotti, nessun agente aggiuntivo, nessun controllo del mouse.

Moduli nuovi: inventario/materializzazione, manifest/queue/review, matcher locale, IPC e pannello. Analizza scena, piano editoriale Groq, ASD e reazioni V3 non modificati dal catalogatore. Solo il worker protocol espone una nuova azione; il resto delle modifiche condivise collega IPC/pannello e packaging.

## Automatici

151 test Node passati (zero skip), 184 test Python passati su Windows. Python include sia unittest sia nove funzioni di contratto packaging prima non raccolte dal solo unittest; nessuna installazione di pytest. RED→GREEN osservati per moduli mancanti, multi-scena dentro un solo segmento Resolve, parole sovrapposte, contesto di battute condivise, checkpoint/copione cambiato, handle inventariati, readback audio, provenienza del punteggio contestuale e allowlist updater. Retry dopo append fallito coperto senza duplicare le scene precedenti/successive. git diff --check pulito.

## Native, non mock

Resolve risponde come **21.1.0.17**, progetto utente iniziale salvato/ripristinato. Progetti sintetici isolati; originali di produzione non importati, spostati o alterati negli esperimenti API.

- PDF test letto dal parser prodotto; due scene, tre MP4 (due file con dialoghi multi-scena/take ripetute, uno realmente senza audio).
- GetTranscription/TranscribeAudio nativi: una trascrizione già presente riusata, altre elaborate una per volta. Il file senza audio fallisce, il lavoro successivo continua.
- Sei membership: scena1 [0,69) e [183,250), scena2 [92,167), per entrambi i file parlati. Estremi dalle parole ASR, non da un piano scritto dall’agente.
- Pausa dopo la prima clip e nuovo controller: ripresa dal checkpoint, senza ritrascrivere clip completate.
- Due cartelle scena e due SELECTS realmente nel Media Pool; sei clip video e sei riferimenti audio riletti. GetSourceStartFrame/GetSourceEndFrame e durata coerenti con il catalogo. Secondo apply: due skip, zero nuove timeline.
- Originali ancora nel bin iniziale; timeline di riferimento vuota intatta. Folder/timeline iniziali ripristinati all’interno di apply. Dopo il ritorno al progetto utente: ID, impostazioni, numero/ID e contenuti delle timeline verificati invariati; folder riacquisita per ID (gli handle vecchi non sono validi dopo LoadProject).
- Stesso smoke ripetuto dal comando tools/day_catalog_native_smoke.cjs e sui JS/Python/runtime realmente estratti e installati dall’EXE in una destinazione isolata. Exit0.

Probe preliminare su MP4 sintetico25fps: bounded import25..74 produce subclip50frame (fine inclusiva), Append25..74 produce [25,74),49frame. MoveClips roundtrip provato solo su subclip sintetica; non entra nel comportamento prodotto. **V1 usa SELECTS**, per non generalizzare un solo probe a tutti fps/codecs. Readback non conforme = scena non pubblicata; le altre proseguono.

Nessuna verifica visiva del pannello Electron dopo OFF. I comandi e l’orchestrazione sono testati, ma non dichiarati collaudati con click reali.

## Girato reale e prestazioni

Gate aggiuntivo read-only sul progetto utente: GetTranscription grezzo su cinque clip reali ha riprodotto quattro errori iniziali (preroll di un frame e parole con start=end). Correzione RED→GREEN nel reader/matcher: conservazione dei raw frame e del testo, limitazione solo alla disponibilità fisica del file entro un frame, nessuna durata assegnata alle parole puntuali, status review per timing incerto. Nuova lettura nativa: **5/5 trascrizioni riusate, zero errori, 27 proposte (3 auto_ready, 24 review), matching 2.034s**, nessuna scrittura o nuova ASR nel progetto utente. Il matcher era esplicitamente vincolato al worker di questa implementazione.


Cinque sorgenti reali, ASR già disponibile, copione16scene: 26 proposte su9scene, 4 auto_ready e22 review. Non c’è un gold umano completo: questi numeri descrivono le proposte, **non una precisione misurata**. Gli incerti non sono pubblicati automaticamente. Tempi matching locale: prima inizializzazione encoder **2.19s**, ripetizione stesso worker **0.119s**, risultati identici. Nessuna nuova trascrizione/Groq in questa misura.

Smoke nativo della copia installata: completamento dopo pausa **2.899s**, run checkpoint caldo **0.089s**. L’ASR Resolve era già caldo in questi replay: non sono tempi di ingestione a freddo per un’intera giornata. La prima prova ASR sintetica ha richiesto circa25s di chiamata complessiva, includendo apertura/ripristino progetto: non è un benchmark ASR isolato. Non effettuato confronto GPU occupata/libera; non sono stati avviati/fermati altri programmi per crearlo.

Gli handle vengono riutilizzati dopo l’inventario, con fingerprint verificato per clip: evitata una nuova scansione dell’intero bin per ogni trascrizione. L’encoder esistente è condiviso; nessun nuovo modello, proxy, scansione video o chiamata Groq. Cache trascrizioni e manifest sono separati dal progetto di montaggio; file o copione cambiato invalidano le dipendenze e richiedono revisione.

## Distribuzione

EXE e ZIP costruiti con runtime esistente e modelli pinned; nessuna credenziale copiata. WorkflowIntegration.node escluso dagli archivi e copiato solo dall’SDK locale durante installazione. Installazione reale dell’EXE sotto review: file JS e matcher confrontati SHA256 con i sorgenti, runtime CPU probe passato, SDK locale verificato; plugin di produzione intatto. Una segnalazione ONNX relativa a un provider opzionale compare nel log: il provider CPU richiesto e i successivi test inferenza/nativi passano.

La build è candidata a prerelease dedicata con suffisso catalog-test e latest=false. Il selettore stabile esclude quel tag; usare EXE per questa prima prova, poiché gli updater precedenti non accettano i nomi dei nuovi moduli. L’updater nuovo include whitelist esplicita e test Windows. L’applicazione completa del ZIP alla copia isolata è stata interrotta perché attendeva elevazione UAC Windows: **non dichiarata collaudata**. La validazione completa ValidateOnly passa separatamente senza scritture: 4101 file. L’installer è stato invece realmente installato e verificato nella destinazione temporanea.

## Limiti / decisioni di review

Self-review, senza secondo agente per preferenza di costo dell’utente. Integrazione V1 utile e nativamente funzionante, ma non certificata come classificatore automatico definitivo di una giornata: molte proposte reali richiedono verifica. Nessun montaggio globale, nessun riconoscimento di scene mute, nessuna garanzia su build Resolve non provate. Se inizialmente non c’è una timeline aperta, non è disponibile un’API affidabile per riportare la UI allo stato nessuna timeline dopo aver creato SELECTS. Dettagli d’uso in ../DAY_CATALOG.md.

## Gate definitivo del pacchetto

Installer definitivo estratto/installato in destinazione isolata: hash di reader, matcher, controller, IPC, UI, performance e main confrontati con i sorgenti, runtime CPU e SDK locale verificati. Stesso EXE: smoke nativo con inventario senza timeline aperta, due scene/sei membership, una clip senza audio, pause/resume, due SELECTS e secondo apply con due skip. Run dopo pausa2.119s, checkpoint caldo0.080s (ASR caldo). Poi lettura/matching delle cinque clip reali usando **JS, Python e runtime del pacchetto installato**: 5/5 trascrizioni riusate, zero errori,27proposte/3auto_ready/24review,2.289s matching. Originale progetto/clip/timeline preservati. Nessuna verifica visiva del pannello Electron, nessuna applicazione completa updater con UAC dichiarata passata.
