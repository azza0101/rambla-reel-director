# Passaggio di consegne — Premontato / Omni-Cut test

**Destinatario:** sviluppatore o MCP che deve integrare le funzioni in un software esistente.

**Stato verificato:** 16 novembre 2026. **Commit di codice analizzato:** `e2789c2e945213e204c8df93e7af8285c5c312e3`.

**Repository:** `azza0101/rambla-reel-director`; cartella prodotto `premontato-workflow/`; ramo `feat/omnicut-independent-av-scene6-20261029`; [PR #37](https://github.com/azza0101/rambla-reel-director/pull/37), bozza. Il ramo contiene anche la precedente PR #47, unificata il 5 novembre. Non è `main`.

> **Punto essenziale:** il codice più recente è su GitHub, ma gran parte del direttore sperimentale non è collegata al normale pannello installato. L'ultimo confronto reale non ha dimostrato un miglioramento del montaggio. Non confondere codice esistente, test unitari, collaudo Resolve e risultato editoriale approvato.

## 1. Cosa va integrato e cosa vuole l'autore

Un motore che prende girato, trascrizioni e copione e produce un primo montaggio dialogato rivedibile in DaVinci Resolve. Le riprese possono contenere più take nello stesso file o take separate, anche con campi girati in tempi diversi. La modalità base deve funzionare senza multicam sincronizzato, senza agente Codex e preferibilmente senza servizi esterni. Il copione dà struttura e contesto, ma la recitazione effettiva e le improvvisazioni non devono essere eliminate perché assenti dal PDF.

Preferenze editoriali: ultimo tentativo **buono e coerente** per campo/persona; primo piano di chi parla quando pertinente; master facoltativa iniziale, per azioni ampie, scambi lunghi e distensione; reazioni motivate dell'ascoltatore sul video, con audio della performance sotto e ritorno al parlante quando serve. Nessun jump cut esposto fra take dello stesso campo; se serve copertura, altra persona pertinente, attraversamento del taglio e durata minima 1,5 s. Questa durata riguarda le coperture obbligatorie, non ogni stacco. Non inventare parlato, identità, azioni o timecode. Scene mute e azioni importanti devono restare nel risultato anche senza trascrizione.

UI richiesta: progressi reali, risultati e incertezze leggibili, sezioni di debug facoltative, correzioni opzionali, creazione della timeline con clic esplicito, salvataggio/ripresa e versione visibile. Le preferenze complete sono in [USER_RULES.md](USER_RULES.md) e [VIDEO_COLICHE.md](styles/VIDEO_COLICHE.md). Sono requisiti: la loro presenza nel file non significa che siano tutti già eseguiti dal motore.

## 2. Versioni, prodotti e confini

| Oggetto | Stato e significato |
| --- | --- |
| Premontato | Prodotto separato, cartella sorgente condivisa `premontato-workflow/`, ID `com.rambla.premontato`. Ultima release stabile Premontato trovata: `premontato-v0.11.11`, 26 ottobre. |
| Omni-Cut test | Profilo sperimentale dello stesso albero, ID `com.rambla.omnicut.test`; impostazioni, cache e update separati. Ultima prerelease trovata: `omnicut-test-v0.2.30`, 28 ottobre, target `6779f912542f3f57d7fbaca14f28bf4298b8edf7`. La versione effettivamente installata va letta dal PC: non è stata verificata in questa consegna. |
| Ramo ricerca | HEAD sopra indicato, successivo alla 0.2.30. Contiene fix e moduli sperimentali non inclusi automaticamente nella release 0.2.30. Non c'è stata una release che dimostri l'integrazione dell'intero nuovo direttore nel pannello. |
| PR #37 e #36 ecc. | #37 è basata sul ramo Nemotron #36; la storia comprende PR precedenti impilate. Il ramo #37 contiene già gli antenati: non integrare solo il diff della PR e supporre che includa tutti i file necessari. |

Tag di release Omni-Cut: `omnicut-test-vX.Y.Z`, prerelease e non `latest` dell'intero repository. Premontato usa `premontato-vX.Y.Z`. Non toccare RMBL, Auto-Cut, ComfyUI o dipendenze globali. Non fare merge su `main` senza istruzione esplicita.

## 3. Architettura e contratto per la fusione

Il pannello Windows/Resolve è in `plugin/` (Electron, controller, sessione, bridge, updater). Il motore riutilizzabile è in `worker/` (Python), richiamabile anche senza Resolve. `tools/omnicut_test_product.cjs` genera la variante Omni-Cut applicando trasformazioni d'identità; non è un secondo motore duplicato. `tools/build_omnicut_test.ps1` produce gli asset di prova con runtime fornito. `tools/build_installer.ps1` riguarda Premontato. I requisiti del runtime sono bloccati in `runtime/requirements.lock`; `worker/requirements.txt` elenca i requisiti Python principali.

Il bridge ufficiale `WorkflowIntegration.node` permette al pannello di interagire con Resolve. Non viene redistribuito negli archivi: l'installer lo recupera dall'SDK locale. Il Resolve MCP è uno strumento di sviluppo e ispezione, non una dipendenza del prodotto finale. Le API hanno limiti che variano con versione e build: i collaudi nativi indicati sotto usano Studio **21.1.0.17**, non costituiscono certificazione universale.

Il worker usa JSON Lines su stdin/stdout: `protocol: 1`, `request_id` stringa, `action`, `payload`; lo stdout contiene eventi `progress`, poi `ok` o `error`, identificati dalla richiesta. Non mescolare log arbitrari nello stdout. Test di connettività:

```json
{"protocol":1,"request_id":"probe-1","action":"ping","payload":{}}
```

La risposta contiene `status: "ok"` e `result.ready: true`. Le azioni sono registrate in `worker/protocol.py`: tra le principali `extract_pdf_script`, `parse_script`, `catalog_scenes`, `align`, `analyze_shots`, `analyze_audio`, `prepare_dialogue`, `build_staged`, `route_scene_edits`, `build_observed_excerpt`, `audit_observed_edit`, `analyze_voice_evidence`, `analyze_visual_inventory`. Per schema effettivo e valori obbligatori leggere il `dispatch` e i test corrispondenti, non inventare campi da questo elenco.

Confini: dati privati, media, trascrizioni, embedding, modelli e log non sono nel repository. Le sorgenti e i frame hanno identificatori e provenienza; gli intervalli di pianificazione sono generalmente `[start_frame,end_frame)` nella frequenza della sorgente. Alcune API Resolve/import hanno estremi diversi: usare i contratti del modulo specifico e readback, mai conversioni a intuito. Nessun piano scritto manualmente dall'agente deve diventare un risultato automatico.

## 4. Flusso catalogazione giornata

### Comportamento attuale Omni-Cut

1. Inventario ricorsivo del bin sorgente Resolve e delle sottocartelle; PDF diviso in scene, titoli e numerazione.
2. Riutilizzo di `GetTranscription` quando disponibile; altre clip una alla volta con Resolve, checkpoint progressivi e ripresa dopo errore. Una trascrizione vuota non prova che la clip sia senza audio. Non ritrascrivere automaticamente solo per cambiare assegnazione.
3. Confronto locale fra parlato, copione e contesto vicino con encoder semantico; parole generiche non bastano come ancora. Una clip può includere più scene, ma l'organizzazione corrente assegna **un bin primario per clip intera**, senza dividere o duplicare l'oggetto.
4. Per clip mute/incerte si può usare Qwen3-VL-Embedding-2B locale: campioni indicativi ogni 5 s, massimo 24, fino a 640 px, e cache. È un confronto di embedding scena/immagine, non una comprensione certificata di un gesto. Le scene vicine affidabili possono fornire riferimenti visivi; la sola prossimità non è prova e le ipotesi non devono propagarsi come nuove ancore.
5. Proposte verdi e incertezze gialle, righe modificabili e anteprime su richiesta. Categoria separata **DETTAGLI E B-ROLL**; un dettaglio pertinente a una scena non va perso soltanto perché è stretto.
6. `Applica al Media Pool` è una mutazione esplicita: salva il progetto, crea/riusa bin numerati, sposta gli **oggetti originali interi** mediante `MoveClips`, con journal, readback e ripetizione idempotente. Non sposta i file fisici. Conserva le altre timeline e non cancella bin estranei/non vuoti.
7. Il contesto catalogato può essere riutilizzato nel montaggio tramite checkpoint e metadati personalizzati `OmniCut Scena`, `Ruolo`, `Trascrizione`, `Tags`, `Data`; controllare progetto, copione e fingerprint. I metadati sono ricercabili come metadati Resolve: non sono scrittura nell'indice visivo/facciale privato di IntelliSearch. Il pool di clip senza parlato non prova che un inserto visivo sia stato automaticamente montato.

**Attenzione alle versioni:** la V1 iniziale Premontato 0.12.0 usava timeline SELECTS non distruttive con intervalli; [DAY_CATALOG.md](DAY_CATALOG.md) la descrive storicamente. L'autore ha poi esplicitamente chiesto clip intere nei bin e nessuna SELECTS/subclip nella catalogazione Omni-Cut; [OMNICUT_VISUAL_CATALOG.md](OMNICUT_VISUAL_CATALOG.md) e [OMNICUT_CATALOG_EDIT_CONTEXT.md](OMNICUT_CATALOG_EDIT_CONTEXT.md) prevalgono per questo comportamento. La documentazione storica non equivale alla versione corrente.

## 5. Flusso montaggio e stato reale

### Pannello / motore preesistente

- `pdf_script.py`, `script_parser.py`: PDF, scene, dialoghi, azioni; pagine opzionali.
- `transcript_align.py`, `scene_edit_jobs.py`, `staged_dialogue.py`: unità temporizzate, contesto, routing per scena, corrispondenze/alternative, pulizia, validazione ID e checkpoint; evitare di trasportare da una scena all'altra una frase generica.
- `shot_analyzer.py`, `active_speaker.py`, `speaker_identity.py`: scala stimata, volti, tracce e prova audio/visiva. Un volto in campo non dimostra da solo che stia parlando; etichette e punteggi non sono probabilità calibrate.
- `automatic_editor.py`, `edit_selector.py`, `editorial_director.py`, `continuity_editor.py`, `listening_reaction.py`: preferenze, candidate, ritmo/reazioni e vincoli. Il pannello permette debug/correzioni e avvia creazione esplicita di timeline di revisione. Le preferenze non sono una garanzia che ogni scena sia montata bene.
- `plugin/` gestisce scelta provider, sessioni, autosave, progressi, scene e applicazione. L'analisi può proseguire con lacune segnalate e una bozza dichiarata incompleta, secondo la versione del flusso; non spacciare il risultato per montaggio completo.

### Direttore ricerca — opt-in, non rollout nel pannello

- `observed_editor.py`: `build_observed_excerpt` lavora su un intervallo di performance osservata, conserva ID e tempi, raggruppa turni e cerca alternative; `editorial_mode` ha default `legacy`, altri modi `independent_av`, `sequence_director`, `evidence_director` sono sperimentali. Il fixture di benchmark fissa l'estratto: **non** dimostra selezione autonoma di una giornata intera.
- `voice_identity.py`, `diarization.py`, `voice_fusion.py`: WeSpeaker primario e Nemotron diarization opzionale, con astensione e prove indipendenti. I cluster sono locali alla registrazione; non supporre che una etichetta speaker uguale fra file sia la stessa persona. L'evidenza secondaria non autorizza da sola l'enrolment facciale.
- `observed_camera.py`, `performance_spine.py`: scelta performance e allineamento vincolato, audit di ID, intervalli, riuso, jump e durata. Un pass tecnico non verifica contenuto recitato, oggetti o intenzione.
- `independent_av.py`: rappresentazione distinta di audio e video, reazioni soltanto con evidenza positiva dell'altra persona e audio base invariato. Un hold parlato oltre 7 s genera una **richiesta di revisione**; la chiamata Qwen per tale richiesta non è collegata e lo stato `pending_model` non è un controllo riuscito.
- `sequence_director.py`: beam search locale su candidati ammessi, con ordine, vincoli di raccordo e priorità editoriali. Beam limitato: non garantisce ottimo globale né recupera una performance scartata prima.
- `acoustic_sync.py`, `sync_coverage.py`: sincronismo opzionale solo con ancore audio verificate, rifiuto di ambiguità/drift e fallback al percorso per take indipendenti. Non usare timecode vicini come prova di multicam.
- `visual_inventory.py`, `upstream_visual.py`: osservazioni di oggetti e identità prima della selezione. Su `build_observed_excerpt`, `inventory_config` e `visual_stage: upstream` attivano il percorso, `visual_stage: late` il confronto precedente; senza configurazione il default esistente resta. `inventory_config` richiede `server`, `model`, `projection`, `ffmpeg` opzionale. Default budget oggetti 12, max 48; volti 480, max 600. Budget zero disabilita inferenze sugli oggetti. Un volto dominante di ascolto non deve annullare una prova positiva di un altro parlante.
- Le alternative verificate da percorsi diversi sono mantenute fino alla selezione globale, incluse take diverse dello stesso file. Non sono un'autorizzazione a concatenare versioni narrative incompatibili.

La ricerca >7 s, il modello visivo e l'editor sperimentale **non** sono una funzione completa e verificata disponibile via Aggiorna. Non rendere attivo questo percorso di nascosto nel programma ricevente.

## 6. Modelli, runtime e pesi

Verificare hash, condizioni di licenza, revisioni e formato nel pacchetto/lock prima della distribuzione. Nessun download automatico in analisi per gli esperimenti; collocare eventuali pesi grandi su Z: o storage configurato, non riempire C:. I percorsi sono configurazione locale, non dati da committare.

| Ruolo | Modello e configurazione verificata | Stato / limiti |
| --- | --- | --- |
| Semantic matching | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`, ONNX quantizzato `model_quint8_avx2`; SHA256 `98a01d88b7de996cdea58c32ca71208c09968d143798814b2ea09d3439dc334f`; tokenizer e altri hash in `runtime/models/semantic/model-lock.json`. | CPU ONNX Runtime, riuso del modello e cache embedding; similarità non è probabilità. |
| Volti / scala | YuNet `yunet.onnx`, SHA256 `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`; SFace INT8 Apache-2.0, SHA256 `2b0e941e6f16cc048c20aee0c8e31f569118f65d702914540f7bfdc14048d78a`. | YuNet inferenza CPU; volti piccoli/profili, occlusioni e gruppi duplicati possono dare errori. SFace non identifica automaticamente il nome o il parlante. |
| Parlante attivo | Light-ASD TalkSet ONNX, MIT, hash `87fd38c0d3ebb9b31abff607662820c2622aef6ce54e1f808528f50e1ba77c38`; pin e conversione in `runtime/models/active-speaker/model-lock.json`. | CPU; PCM mono 16 kHz, MFCC e crop tracciati; logit non probabilità. Campioni locali non certificano una battuta intera. |
| Impronte voce | WeSpeaker ResNet34 VoxCeleb ONNX, `PREMONTATO_VOICE_MODEL`, SHA256 `5ef208a9da1453335308a6b6f4e6dfbd7e183a38b604de0a57664f45d257fe94`. | Sperimentale; `worker/voice_identity.py` descrive licenza e configurazione. Ambiguità → unknown. |
| Diarizzazione | NVIDIA **Nemotron-3-Diarization** Q8_0, revisione `f667ed73aee57d40cc39428eb768b4fd87a0a29e`, 107.012.128 byte, SHA256 `08456d9e22cd9a323c0364d98375f3746d6e68507ebb705cd46438c534c7a3a1`; NeMo-Speech.cpp ufficiale v0.2.0. | Complemento opzionale a WeSpeaker, non il modello Nemotron Transcribe 3.5 mostrato dall'utente e non un sostituto della trascrizione. Preset `v3-offline`; cache e fallback GPU→CPU validati. |
| Catalogo visivo | Qwen3-VL-Embedding-2B e codice/ambiente ufficiale locali. | Non incluso nell'installer; configurazione `OMNICUT_VISION_HOME` o `catalog-vision.json` con `python`, `deps`, `code`, `model`; inferenza locale opzionale. |
| Inventario oggetti | Qwen3-VL-4B-Instruct GGUF `Q4_K_M`, revision `1cd86afb9a95c410a6038ab3b40d8b578c892266`, modello SHA256 `66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a`, `mmproj` Q8_0 SHA256 `30ba2c7dd3127a4561b6cba9d13d0f711c91bdb38742e2f56d73c8cb596bd06d`. | ~2,95 GB, llama.cpp locale; sperimentale, l'inventario non prova proprietà dell'oggetto o gesto. |
| Testuale locale | Gemma 4 12B QAT Q4_0 GGUF con `llama-server.exe` selezionato dall'utente. | Documentato in [LOCAL_GEMMA.md](LOCAL_GEMMA.md); non è dimostrato migliore dell'online sul montaggio completo; pesi/runtime esterni. Liquid e altri Qwen sono stati esplorati, ma non risultano scelta produttiva validata da questi rapporti: non dedurre prestazioni dai nomi. |
| Trascrizione | Resolve `GetTranscription` / `TranscribeAudio`. | Tecnologia/profilo di inferenza interno non certificato da questa integrazione; velocità dipende da media, GPU, altre applicazioni e cache. Whisper non è stato stabilito qui come sostituto migliore. |
| Online opzionale | Groq / OpenRouter, esplicitamente configurati nel pannello. | Inviare solo dati autorizzati; non includere credenziali nel codice, log, installer o handoff. Quote, disponibilità e qualità variano. Nessun passaggio online implicito se il modello locale fallisce. |

`PREMONTATO_DIARIZATION_RUNTIME`, `PREMONTATO_DIARIZATION_MODEL`, `PREMONTATO_DIARIZATION_DEVICE`, opzionali `PREMONTATO_DIARIZATION_CPU_RUNTIME` e `PREMONTATO_DIARIZATION_CACHE_DIR` configurano l'adattatore; `PREMONTATO_CACHE_DIR` configura cache condivisa. `PREMONTATO_GPU_VIDEO=0` disattiva il lettore GPU opzionale. Per lock e avvisi completi: `runtime/models/*/model-lock.json`, `runtime/THIRD_PARTY_NOTICES.txt`, `tools/prepare_models.ps1`.

## 7. Test reali, risultati negativi e tempi

I numeri sono misure dei casi descritti, **non benchmark generali**. I dati privati e le annotazioni non sono pubblicati nel repository.

| Prova | Risultato / limite |
| --- | --- |
| Catalogo iniziale V1 su Resolve 21.1 | Due scene, tre MP4 sintetici, uno senza audio; riuso una trascrizione, ripresa da checkpoint, sei membership, due SELECTS rilette e seconda applicazione senza duplicati. Storico SELECTS, non comportamento Omni-Cut clip intere. [Rapporto](performance/2026-10-26-day-catalog-validation.md). |
| Lettura 5 clip reali | 5/5 trascrizioni riusate, 27 proposte: 3 auto-ready, 24 review; ~2 s matching. Non è precisione rispetto a gold umano. |
| Catalogo reale Omni-Cut | 51 clip/8 scene: prova iniziale 35 proposte e 16 senza destinazione/conflitto; ~616,9 s con cache parziali e 4,4 s al riavvio. Versioni successive 40 scene + 11 B-roll con cache, non verifica di accuratezza delle 51. Regole vicino/visione hanno corretto esempi specifici senza hardcode. [Rapporto](OMNICUT_VISUAL_CATALOG.md). |
| MoveClips | Test nativo su un oggetto originale, readback, applicazione ripetuta, ripristino del bin. Non equivale a validare tutte le assegnazioni della giornata. |
| Scena 5 | Pianificata e applicata nativamente in Resolve; test locale di scena su cache ~32,8 s. Il run globale era incompleto per quota Groq; in prova intermedia lunga si sono osservati ~1.282,9 s con attese. [Rapporto](SCENE_EDIT_JOBS.md). |
| Lettura 4K, 1 minuto | CPU ~2 fps 14,77 s; D3D11 ~2 fps 8,62 s. Ridurre a 0,5 fps ha perso tutti i volti in una clip di 4,8 s, quindi non adottato come default. Benchmark locale, PC in uso. [Dettagli](OMNICUT_VIDEO_READ_PERFORMANCE.md). |
| Director con vincoli più stretti | Quattro scene dialogate non hanno trovato percorso continuo; solo sei decisioni delle altre scene. Non rilasciato. Allargare gap ha reintrodotto ripetizioni ed è stato scartato. [Stato](EDITORIAL_PROTOTYPE_STATUS.md). |
| Voce ibrida Nemotron | 104 ancore confrontate con etichette Resolve: WeSpeaker 81 concordi/1 discordante/22 unknown; ibrido 85/1/18. Etichette proxy, non DER umano. Su un estratto 68 unità: 49→54 voci identificate. [Rapporto](performance/2026-10-29-nemotron-hybrid-evidence.md). |
| Nemotron tempi | Clip 424,8 s: adattatore GPU 2,07 s con PCM già estratto; altra clip 98,4 s CPU 2,889 s, cache 0,0065 s. Esclusi trascrizione, estrazione audio e avvio a freddo. |
| Audio/video indipendenti | Stesso estratto, quattro reazioni da 1,6 s, audio renderizzato identico al riferimento automatico confrontato. Resta un hold di 16,16 s e 10 turni non verificati. Anteprima 640×360, 53,56 s; test fuori da Resolve, non qualità umana. [Rapporto](performance/2026-10-29-independent-av-scene-check.md). |
| ASD alternativo / soglie | Ridurre gli avvisi con ASD forte ha prodotto un campo sbagliato sull'ascoltatrice. Variante scartata; LR-ASD non ha dimostrato selezione migliore. Non premiare metriche numeriche che peggiorano le immagini. [Rapporto](performance/2026-11-04-evidence-first-director.md). |
| Sync opzionale | Nell'ultimo confronto 0/13 coppie hanno superato la verifica audio severa. Non inventare sincronismo o forzare la modalità multicam. |
| Inventario visivo 4B | Presenza oggetto 9/10 su campioni noti, 4/4 su nuovi positivi dello stesso passaggio; 14 frame 19,30 s con caricamento e 0,157 s in cache. Non misura gesti, proprietà delle mani, assenze o generalizzazione. [Rapporto](performance/2026-11-04-visual-inventory-integration.md). |
| Indice visivo a monte, confronto finale | 14 registrazioni, 34 eventi, 22 turni: alternative 49→53, 10 turni incerti invariati, **0 scelte video cambiate**; 1.339 frame. Cache calda 34,71→46,68 s; quattro risposte oggetto rifiutate per schema. Non è un miglioramento del montaggio. [Rapporto](performance/2026-11-04-upstream-visual-index.md). |
| Reference umana | Timeline `V4-MCP` di un progetto privato, 25 fps, 5:37; estrazione locale di video/audio/sottotitoli, FCPXML e still; non pubblicata. Un confronto precedente ha identificato alternanza fra gesto, domanda, risposta e ascolto e separazione audio/video. Le versioni recitate non sono frame-equivalenti. L'autore ha successivamente espresso un dubbio sul nome: verificare la reference esatta con lui/Resolve prima di usarla come gold definitivo. |

Nel test finale i dieci turni incerti comprendono sette battute brevi con identità vocale sconosciuta e tre turni con voce nota ma copertura del parlante non verificata. Le battute non sono automaticamente mancanti: può restare l'immagine dell'ascoltatore sotto la voce dell'altro. La verifica tecnica non certifica la qualità di questi passaggi.

Altre correzioni e regressioni registrate: cache oggetti richiesta dopo identità, budget oggetti zero, inventario condiviso che si perdeva fra turni, volto dominante dell'ascoltatore che annullava una prova positiva del parlante, candidata rigettata riproposta su un'altra domanda, falsi flash-cut per confini vocali contigui, fallback CPU dopo output CUDA diarizzazione invalido. Dettagli e RED/GREEN nei rapporti di performance.

## 8. Cosa manca davvero / ordine consigliato

1. **Performance narrativa coerente:** scegliere contenuto recitato e ripartenze prima delle camere, conservare improvvisazioni e distinguere risposte ripetute che appartengono a oggetti/domande diversi. Le differenze fra esecuzioni non sono solo parafrasi da allineare localmente.
2. **Allineamento per episodi fra take indipendenti:** rappresentare domanda → oggetto/gesto → risposta → correzione come eventi con provenienza e incertezza. Considerare più take nello stesso file e registrazioni realmente multicam solo se verificate. Non forzare sincronismo.
3. **Piano A/V integrato:** audio coerente, coperture video e ritorno al parlante; evitare cambi take/campo e salti temporali incoerenti. Confronto di azione e oggetti ancora non certificato.
4. **Scene mute:** catalogazione visiva non equivale all'inserimento narrativo di serranda, uscita o movimento. Serve un piano delle azioni con tempi verificati.
5. **Revisione mirata dei casi incerti:** il trigger >7 s esiste come richiesta pendente; verificare candidati/clip brevi con un modello locale se utile e misurare precisione e latenza. Non presumere che Qwen o una singola still capiscano labiale, intenzione o una sequenza intera.
6. **Qualità misurabile:** reference umana confermata, almeno una scena ulteriore e girato diverso, annotazioni e metrica indipendente su speaker visibile, eventi conservati, ripetizioni, azioni, raccordi, ASR e preferenza editoriale. Test ID/durata non sostituiscono visione e ascolto.
7. **Integrazione nel software ricevente:** integrare in fasi opt-in con contratto/versione e fallback; mantenere separati analisi, anteprima, applicazione Resolve e rollback. Aggiornare UI e packaging solo dopo test locali e nativi, compatibilità canale/SDK e valutazione editoriale. Non promuovere l'esperimento come funzione pronta senza queste prove.

## 9. Come riprodurre e integrare senza Codex

Dal checkout esatto, usare un ambiente Python isolato con dipendenze bloccate e i modelli previsti. Su questo PC il runtime della precedente installazione di prova è stato usato per la suite; per altri PC costruire un runtime proprio, senza riutilizzare o modificare ambienti di altri prodotti. `python tools/run_python_tests.py` raccoglie anche i test di contratto packaging; da `premontato-workflow/`, `node --test --test-isolation=none tests/unit/*.test.cjs` richiede Node compatibile. Verificare le versioni effettive prima dell'esecuzione.

Da Python, importare il worker con la directory `worker/` nel `sys.path`; per integrazione fra processi preferire il protocollo JSONL sopra. `build_observed_excerpt` richiede sorgenti con identità/percorso/fps/durata, unità temporizzate per media e intervallo reference: leggere gli esempi nei test e `tools/voice_identity_benchmark.py`, mai inviare soltanto un testo privo di tempi. `tools/render_observed_av.py` può rendere un piano diagnostico locale con FFmpeg già presente: una preview riproducibile non è automaticamente un montaggio approvato.

Separare test unitari, fixture sintetiche, replay con dati reali, valutazione umana e test nativo Resolve. Scrivere cache su storage configurato e includere impronte di file/modello/parametri; fallimenti non diventano successi in cache. Loggare fasi, durata, percorso di fallback e stato incerto senza chiavi o contenuti privati. Non registrare video, trascrizioni o face embeddings nel repo.

## 10. Riferimenti pratici e verifica di questa consegna

- [README prodotto](../README.md), [Omni-Cut e packaging](OMNICUT_TEST.md), [catalogo visivo](OMNICUT_VISUAL_CATALOG.md), [catalogo→montaggio](OMNICUT_CATALOG_EDIT_CONTEXT.md), [lavoro per scena](SCENE_EDIT_JOBS.md), [GPU video](OMNICUT_VIDEO_READ_PERFORMANCE.md), [regole autore](USER_RULES.md).
- [Stato esperimenti editoriali](EDITORIAL_PROTOTYPE_STATUS.md), [ricerca locale](performance/2026-11-04-evidence-first-director.md), [indice upstream e risultato negativo](performance/2026-11-04-upstream-visual-index.md), [Nemotron](performance/2026-10-29-nemotron-hybrid-evidence.md), [A/V indipendente](performance/2026-10-29-independent-av-scene-check.md).
- I fix fino a `e2789c2` risultano già sul ramo remoto #37; non è stata trovata una modifica non committata nel checkout del ramo analizzato al momento della ricognizione. Altri checkout hanno modifiche relative ad altri prodotti o un lock con sole differenze di fine riga: non copiarle o pubblicarle come fix Omni-Cut senza analisi specifica.
- Fix successivo incluso con questa consegna: il loop JSONL azzera la richiesta prima di ogni riga. Prima, un JSON malformato dopo una richiesta valida restituiva erroneamente il `request_id` precedente, rischiando di attribuire l'errore all'operazione sbagliata. Regressione con processo reale: richiesta valida → JSON malformato → richiesta valida, con ID `first`, `null`, `last`; nessuna modifica delle decisioni editoriali.
- Verifica del 16 novembre sul checkout di questa consegna: **418 test Python e 262 JavaScript passati**; percorso di errore del protocollo riprodotto prima della correzione e ripetuto dopo. Controllati anche i collegamenti relativi di questo documento. Nessun nuovo replay del girato o collaudo nativo Resolve in questa consegna.
- Il file è un inventario e una guida di integrazione, non una release, un nuovo test nativo o un'attestazione che l'app installata abbia già tutte queste funzioni. I risultati storici riportano date e condizioni originali; ripetere i test per ogni nuova integrazione.
