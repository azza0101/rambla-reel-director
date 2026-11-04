# Ricerca e collaudo del direttore locale — 4 novembre 2026

## Risultato

La ricerca non dimostra ancora un salto nella qualità editoriale della scena difficile. Non basta sostituire Light-ASD, allentare il riconoscimento dei volti o aggiungere un VLM a ogni scelta. Alcune varianti diminuiscono gli avvisi ma mostrano la persona sbagliata. Il ramo conserva quindi il comportamento predefinito e isola i nuovi modi nel worker sperimentale; nessun aggiornamento stabile o nuovo piano di tagli scritto a mano.

Sono implementati un selettore locale della sequenza, una ricerca prudente di eventuali registrazioni simultanee e due correzioni generali dell'audit/ricerca. I benchmark includono registrazioni e trascrizioni reali, oltre ai test sintetici. L'audit degli intervalli non certifica parole equivalenti, recitazione, oggetti o qualità umana.

## Fonti e applicabilità

Le descrizioni seguenti sono una valutazione per questo prodotto, non benchmark dei progetti citati. Nessun codice di questi repository è incorporato nel ramo. I modelli di prova restano fuori dal repository e dall'installer.

| Fonte primaria | Elemento utile | Limite per il nostro girato |
| --- | --- | --- |
| [Stanford, Computational Video Editing for Dialogue-Driven Scenes](https://graphics.stanford.edu/papers/roughcut/) | Ottimizzare una sequenza di campi mediante costi e regole, invece di scegliere ogni taglio isolatamente | Richiede già battute/take allineate. I tempi di pianificazione pubblicati non includono la nostra preparazione e non sono misure di Omni-Cut |
| [EditIQ, IUI 2025](https://arxiv.org/html/2502.02172v1) | Separare contesto del dialogo, salienza visiva e vincoli di continuità; ancorare i suggerimenti alle parole disponibili | Parte da riprese larghe statiche e ritagli della stessa esecuzione. Non risolve direttamente improvvisazioni differenti fra take |
| [LR-ASD](https://github.com/Junhua-Liao/LR-ASD), MIT | Alternativa leggera per il parlante audiovisivo | Il nostro confronto non dimostra maggiore qualità; benchmark pubblici AVA non equivalgono ad accuratezza sul nostro materiale |
| [Cutawan](https://github.com/JeremySNR/cutawan), MIT | Esportazione LR-ASD ONNX con frontend/backend separati: riuso delle feature del contesto | Speaker-aware reframing di podcast; non è un direttore di scene recitate |
| [Agentic-Video-Editor](https://github.com/krshailendra/Agentic-Video-Editor) | Libreria di momenti, costi espliciti, traccia parlata distinta dagli inserti e statistiche della reference | Il README descrive anche un LLM per la struttura narrativa; la sola presenza del solver non garantisce qualità. Nessuna licenza di riuso verificata qui: solo studio delle idee |
| [video-use](https://github.com/xmllist/video-use), MIT | Trascrizione compatta e filmstrip su richiesta, controllo mirato invece di inviare tutto il video | È uno strumento per un agente, non un montatore autonomo da incorporare tale e quale |
| [video-timeline-copilot](https://github.com/ludmila-omlopes/video-timeline-copilot), MIT | Operazioni/intervalli verificabili e revisione dei tagli | Non sostituisce la comprensione della recitazione |
| [speech_dtw](https://github.com/kamperh/speech_dtw), MIT | Allineamento acustico di parlato simile | Un allineamento elastico non prova simultaneità né corrispondenza dei gesti |
| [audalign](https://github.com/benfmiller/audalign), [skellysync](https://github.com/freemocap/skellysync), [polysync](https://github.com/jianshuo/polysync) | Ricerca di sincronismo audio come percorso opzionale | Le take indipendenti restano il caso principale; non assumere sincronismo da nomi/timecode |
| [OpenPodCut](https://github.com/YoYoZ/OpenPodCut), GPLv3 | Durata minima, J/L cut e gestione delle camere mancanti | Richiede mapping camera/persona e tracce microfoniche; non seleziona take indipendenti. Non adottare la soppressione delle interiezioni per le nostre gag |
| [premiere-director](https://github.com/Macadaisical/premiere-director), MIT | Pipeline locale separata da operazioni nell'editor | La funzione Director richiede già camere sincronizzate e assegnate. Non dimostra il nostro caso d'uso |
| [TransNetV2](https://github.com/soCzech/TransNetV2), MIT | Individuare cambi di inquadratura già presenti in un video | Rilevare uno stacco non stabilisce quale campo scegliere fra i rough. Non scaricato o integrato |
| [Qwen3-VL-4B-Instruct GGUF ufficiale](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF), Apache-2.0 | Revisione visiva locale circoscritta; piccolo modello rispetto ai VLM grandi | Una still non identifica il parlante udibile; oggetti e proprietario delle mani possono essere confusi |
| [WhisperX](https://github.com/m-bain/whisperX), [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Possibile recupero di timestamp delle parole quando mancanti | Non rifare trascrizioni/cache valide per risolvere errori nella scelta del video |
| [ghostcut-ai](https://github.com/himuvai47/ghostcut-ai) | Esaminato per confronto | Orientamento a video narrati/B-roll; licenza di riuso non rilevata. Non integrato |

Sono state consultate anche discussioni di montatori su Reddit, tra cui [approccio al girato dialogato](https://www.reddit.com/r/editors/comments/1gx2zat/) e [workflow dialoghi per cinema](https://www.reddit.com/r/AudioPost/comments/1955zqe/). Sono testimonianze di workflow, non prove di prestazioni o accuratezza dei modelli.

Revisioni fissate nella ricerca:

| Repository | Commit |
| --- | --- |
| Junhua-Liao/LR-ASD | `1b6dcd2d8fc2895683de6508ec6294ec47d388ca` |
| JeremySNR/cutawan | `084d0b2933f64800ee5ca1b22269704f060e65f5` |
| xmllist/video-use | `f6a2620d1541163b8a6d5cf1b5ccaaa4a79c3485` |
| ludmila-omlopes/video-timeline-copilot | `64f0323790e1d0f5c88b652149f1dd4dbef39bc4` |
| kamperh/speech_dtw | `6d28979acc4e34d66dcbc9abd67b1317ee2d8a48` |
| himuvai47/ghostcut-ai | `bfb3918c3015a40c3dc8076d5ea12e0c229631c3` |

## Protocollo reale e limiti dei dati

- Un estratto recitato difficile congelato prima delle prove: 34 identificatori di parlato, 22 turni vocali, 14 registrazioni candidate. Il riferimento audio del benchmark è fissato: questa prova non certifica la selezione automatica della migliore scena nell'intera giornata.
- Altre 16 unità da un diverso file, selezionate con criterio uniforme, per un secondo replay. Sono dello stesso progetto, non un test su un film indipendente.
- Nessun piano camere scritto dall'agente. Si riusano trascrizioni, profili vocali, ASD e cache esistenti. Gli script privati contengono gli input del test; il codice di prodotto non contiene nomi file, attori o timecode di questo materiale.
- Le etichette dei 36 casi ASD sono proxy ottenuti da voce riconciliata e soggetto noto del campo. Non sono 36 annotazioni umane delle labbra. Non riportare queste frazioni come accuratezza generale.
- Una riduzione degli avvisi o la copertura di tutti gli ID non dimostra che una variante recitata conservi ogni parola, oggetto o intenzione.

## Esperimenti e decisioni

| Prova | Risultato osservato | Decisione |
| --- | --- | --- |
| Baseline audio/video indipendenti | 11 segmenti decisionali, 10 turni con video non verificato, un hold problematico di 16,16 s | Riferimento; non è una scena risolta |
| Sostituire il controllo identità con ASD molto positivo | 11 turni non risolti; meno scelte utili | Scartato |
| Accettare identità **oppure** ASD forte | 8 turni non risolti, ma apertura sbagliata: parla un uomo e resta il campo della donna | Scartato nonostante il conteggio apparentemente migliore |
| Più frame per riconoscere un volto incerto | Identità sui frame laterali concordanti, senza sovrascrivere un'identità centrale già nota | Nessun miglioramento sull'estratto; non integrato |
| Domanda breve riordinata con contesto forte | Regola generica testata, mantenendo voce, ordine e negazione | Risultato reale invariato. Disponibile solo con flag sperimentale |
| Allineare prima l'intera conversazione e poi filtrare le camere | 9 segmenti decisionali e 11 turni non risolti | Spike scartato; non è sufficiente a risolvere il contesto delle ripetizioni |
| Selettore dell'intera sequenza | Circa 15,9 ms CPU, 2.313 stati esaminati, beam 64, ricerca potata; nessun ID perso/duplicato o riuso retrogrado | Base sperimentale utile. Stessi 10 turni non risolti e nessun salto visivo dimostrato |
| Secondo estratto con il selettore | 16 ID, 11 turni, 4 non risolti, circa 100,2 s dell'intera elaborazione con nuove verifiche/cache | Test di funzionamento e limiti, non confronto di qualità con un umano |
| Usare la separazione stereo per la voce | Tre file: canali quasi duplicati, correlazione circa 0,986–0,988 e differenza di guadagno analoga per entrambi gli attori | Scartato: non sono due microfoni indipendenti |

### Confronto ASD

36 finestre reali identiche da tre registrazioni, stesso preprocessore video/MFCC e stessa logica di tracking. Inferenza ONNX **CPU**; il decoder video può usare il percorso hardware esistente.

| Modello | Visibile / assente / incerto | Concordanze con il proxy | Tempo totale del replay |
| --- | --- | --- | --- |
| Light-ASD esistente | 26 / 7 / 3 | 23/36 | 24,90 s |
| LR-ASD ONNX a due stadi | 19 / 10 / 7 | 22/36 | 17,58 s |

I tempi mescolano campioni già in cache e nuovi: non sono una misura controllata di accelerazione a freddo. LR-ASD si astiene più spesso ma non dimostra migliore selezione. Non viene sostituito il modello del plugin.

Due grafi di prova, circa 3,4 MB, provenienti dall'esportazione Cutawan fissata sopra:

- frontend SHA-256 `f7c055612cd6f1f2da3ab8257567ab68a6b0d69b5e436699a5cf65334dd79461`;
- backend SHA-256 `9453caa09998027995664fd5a3b1fab4ad0de30a92c6beba8c29c3619de510a9`.

### Sincronismo opzionale: falso positivo individuato e corretto

Una ricerca su 13 coppie trovava inizialmente un offset di circa −3,30 s con più ancore concordanti. La camera alternativa mostrava comunque la donna in un campo più largo: nessuna prova di un nuovo controcampo dell'uomo.

La revisione ha inoltre riprodotto un difetto con audio sintetico: cinque ancore concordanti potevano nascondere 5,5 s di audio diverso nel mezzo. È stato aggiunto un test prima della correzione. Ora finestre audio sovrapposte verificano tutto l'intervallo mappato e la cache ha una nuova versione.

**Esito reale dopo la correzione: zero coppie certificate su 13.** Anche la coppia inizialmente promettente viene esclusa per incoerenza interna. Questa è una rinuncia corretta, non una regressione da aggirare abbassando la soglia.

La funzione resta opzionale, locale e prudente. Non estrapola oltre gli intervalli certificati e non sposta l'audio sulla camera selezionata. Non sostituisce il lavoro sulle take indipendenti. Un precedente replay con il filtro meno severo aveva 16 turni non risolti ed è superato, non un risultato da promuovere.

### Qwen visivo locale

Prova isolata con llama.cpp Vulkan esistente, host `127.0.0.1`, Qwen3-VL-4B-Instruct Q4_K_M e proiettore Q8_0. Circa 2,95 GB su Z:, nessuna installazione globale e nessun invio delle immagini al cloud. Server avviato solo per la misura e terminato al termine.

Prima prova: quattro immagini reali, caricamento 6,1 s, richieste circa 0,4–6,6 s. Il modello riconosce spesso uomo/donna e cibo, ma attribuisce un oggetto in primo piano alla donna dietro di esso e confonde un oggetto in un altro campo.

Seconda prova: istruzioni generali su mani/proprietario/astensione, quattro immagini iniziali e sei ulteriori immagini del progetto scelte con indici uniformi. Caricamento 3,0 s; richieste calde circa 0,46–0,62 s. Migliora l'astensione sull'oggetto retto da fuori campo, ma rimangono descrizioni ambigue. Non è una dimostrazione di dieci risposte perfette né di riconoscimento del parlante.

Pesi ufficiali fissati alla revisione `1cd86afb9a95c410a6038ab3b40d8b578c892266`:

- modello SHA-256 `66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a`;
- proiettore SHA-256 `30ba2c7dd3127a4561b6cba9d13d0f711c91bdb38742e2f56d73c8cb596bd06d`.

Non collegato al controllo automatico degli hold >7 s: quest'ultimo resta una richiesta pendente, non un controllo dichiarato superato.

## Codice implementato

- `worker/sequence_director.py`: ricerca deterministica e limitata sui candidati già verificati. Priorità alla persona che parla, raccordi, take bloccata come ultima buona, campo e somiglianza; mai inventare intervalli o perdere un evento per completare il percorso. Conserva l'ordine di ogni sorgente anche attraverso camere interposte. Non è un ottimo globale garantito quando il beam viene potato.
- `worker/acoustic_sync.py`: ricerca NCC multi-ancora, controllo di ambiguità/drift, verifica locale sovrapposta e rifiuto di zone contraddittorie. Un esito non verificato conserva il percorso per take indipendenti.
- `worker/sync_coverage.py`: cache per impronta sorgente/intervallo, errori per singolo file, mapping soltanto locale e compilation diagnostica con audio continuo. Le reazioni richiedono un'altra identità nota, almeno 1,5 s e ritorno al parlante.
- `worker/observed_editor.py`: `sequence_director` e `evidence_director` soltanto su richiesta del chiamante sperimentale. Default `legacy` invariato. `contextual_questions` è un flag separato e spento.
- `worker/observed_camera.py`: un candidato bocciato dal controllo visivo viene escluso per tutte le battute. Prima poteva consumare i retry ricomparendo su un'altra domanda identica. Test di regressione fallito prima della correzione e superato dopo.
- Audit delle durate: confini di turni vocali contigui sullo stesso campo/sorgente non sono falsi flash-cut; i veri frammenti discontinui brevi restano segnalati. Test rosso/verde dedicato.

Replay reale dopo la correzione dei candidati: circa 41,5 s con cache già calde, risultato editoriale invariato (10 turni non verificati). Il difetto era reale, ma non spiega da solo l'hold di 16,16 s. Non attribuire una riduzione di tempo alla patch senza confronto controllato.

## Struttura raccomandata e ciò che manca

La parte veloce non deve decidere da sola che cosa significa una gag. La struttura raccomandata è:

1. Indicizzare una volta riprese/take/campi con campioni video ridotti e provenienza. Riutilizzare le cache; verifiche dense solo intorno ai candidati effettivi.
2. Scegliere una performance narrativa coerente dal **parlato recitato**, con varianti, oggetti e ripartenze. Il PDF dà contesto e ordine delle scene; non elimina gli adlib.
3. Allineare gli episodi recitati fra campi indipendenti, mantenendo i turni vicini e le azioni. Una domanda identica ripetuta davanti a un oggetto diverso non è automaticamente lo stesso evento.
4. Risolvere localmente la sequenza fra alternative ammissibili, con audio distinto dagli inserti e vincoli su riuso, salti e reazioni.
5. Richiedere al VLM piccoli controlli solo su identità/azione/oggetti o hold sospetti, con immagini temporali e ID ammessi. Un dubbio resta dubbio; non proporre tagli arbitrari per superare i sette secondi.

In questo ramo il punto 4 è implementato sperimentalmente; sono migliorati controlli e strumenti per i punti 3/5. I punti 2/3 non sono ancora dimostrati sufficienti sulla scena difficile. Non dichiarare che la struttura raccomandata sia già tutta eseguibile nel pannello.

## Verifica e consegna

La revisione indipendente ha individuato il falso positivo del sincronismo; riprodotto e corretto con test. I nuovi moduli usano dipendenze esistenti. Le misure e i pesi restano nella cartella privata di ricerca su Z:, fuori da Git.

- Suite Python completa: 392 passati, zero falliti (27 nuovi test rispetto alla base a 365).
- Suite JavaScript completa: 262 passati, zero falliti.
- Nessuna nuova timeline applicata via API e nessun collaudo nativo del nuovo direttore dichiarato superato. Questa sessione ha eseguito replay reali fuori da Resolve e studio della reference precedentemente estratta.
- Nessun controllo del mouse, modifica del progetto aperto, credenziale nel codice o aggiornamento del plugin installato.
- Nessun installer/release stabile: questi esperimenti non superano ancora il criterio di accettazione editoriale sul caso difficile.
