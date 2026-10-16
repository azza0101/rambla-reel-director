# MAGICO ibrido economico — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un pulsante prepara CUT, selezioni editoriali, coperture verificate, immagini alternative disattivate e pacchetto Resolve, senza Codex nel runtime.

**Architecture:** Un coordinatore persistente esegue adattatori dei motori attuali, senza comandare l'interfaccia e senza chiamare il proprio server HTTP. I contratti di fase sono JSON verificati e identificati da firma/revisione. Prima consegna su video caricato; seconda sul materiale originale multitraccia acquisito dal bridge, con APPLICA sempre manuale.

**Tech Stack:** Python/FastAPI, Pydantic, asyncio, JSON atomico, FFmpeg/ffprobe, JavaScript esistente, provider Groq/Gemini configurati e ranker disponibile.

**Spec:** `docs/superpowers/specs/2026-10-16-magic-hybrid-design.md`.

## Global Constraints

- Esecuzione singola, nativa e sequenziale; niente implementer/subagent. Branch autorevole già concordato: `feat/api-first-text-first-v1`; mantenere la storia verificata v0075, senza riattivare vecchi vincoli di branch/workspace superati dalle istruzioni dell'utente.
- Nessuna dipendenza GPT/OpenAI/Codex nel runtime; MCP solo per QA se Resolve è aperto, mai requisito del prodotto.
- Riutilizzare CUT, Director, phrase-intents, research, media preparation e handoff; nessun secondo motore equivalente e nessun agente che controlla la GUI.
- APPLICA manuale; ricerca/preparazione non modificano timeline. Originali read-only, firme verificate prima dell'applicazione, backup BCK e marker protetti.
- Pause MEDIUM; margine finale iniziale 120 ms, limitato dall'inizio della parola successiva. Confini incerti conservativi.
- Coperture obiettivo 2–4 s, minimo 1,5 s, senza media stirati o allungati oltre la sorgente. Titoli singoli Yellow sopra tutti i video; coperture Purple, coda Beige.
- Immagini fallback Purple, `enabled=false`, traccia `RMBL IMMAGINI ALTERNATIVE` sotto i titoli. Take alternative Red disattivate come v0075.
- Due query per fonte/beat, massimo sei candidati per prima valutazione. Default operativo: massimo 12 chiamate cloud per run, di cui massimo 4 visive; modificabili nelle opzioni avanzate. ASR incluso nel totale. Esaurimento porta a risultato parziale esplicito.
- Mai retry automatico CAPTCHA/login; link alla fonte e ripresa manuale. Chiamata dal risultato ignoto dopo crash: non ripeterla automaticamente.
- Non migrare/distruggere selezioni manuali: salvare backup e creare revisione MAGICO isolata. Annullamento e ripresa senza duplicazione di figli CUT o pacchetti.

## Review Focus

1. Backend chiuso durante una chiamata cloud: segnalare esito ignoto senza doppio addebito; test Task 1 e 2.
2. Utente cambia file o selezioni mentre MAGICO lavora: rifiutare pubblicazione sulla revisione diversa; test Task 1 e 4.
3. Ultime consonanti e ripetizioni con continuazioni nuove: conservare audio/contenuti distinti, anche VFR e FPS frazionari; test Task 3.
4. Risultati di luoghi omonimi o fonti non verificabili: nessun video attivo spacciato per coerente; test Task 5 e 6.
5. Immagine fallback e generica selezionata insieme: nessuna attivazione involontaria o duplicazione dentro/coda; test Task 6 e 7.

## File map e contratti condivisi

- Nuovi `backend/app/magic_models.py`, `magic_store.py`: validazione e persistenza; `magic_runner.py`: coordinatore; `magic_services.py`: adattatori ai motori; `magic_routes.py`, `magic_ui.py`: API e controlli osservabili.
- Nuovo `backend/app/magic_editorial.py`: scelte strutturate e limiti economici; `magic_coverage.py`: giudizi media e intervalli in frame. Non duplicano ricerca/download o CUT.
- Nuovo `backend/app/resolve_cut_source.py`: snapshot originale multitraccia e rimappatura, separato dalla costruzione CUT standalone esistente.
- Modifiche mirate a `curation_server.py`, `cut_pass_routes.py`, `cut_pass.py`, `cut_boundaries.py`, `api_first_director.py`, `transcript_intents.py`, `beat_research.py`, `broll_timeline_export.py`, `resolve_textplus_timeline.py`, `resolve_bridge.py`, `resolve_native_cut.py`, `curation_ui_v2.py`, `tools/resolve_bridge/standalone_bridge.py`.
- `MagicOptions`: pause_mode=medium, end_margin_ms=120, providers, max_cloud_requests=12, max_visual_requests=4, queries_per_provider=2, candidates_per_beat=6. Valori positivi, fonti conosciute, nessuna chiave segreta.
- `MagicContext`: source_project_id, output_project_id opzionale, source_signature, cut_revision opzionale, run_id. Solo riferimenti e metadati persistibili.
- `MagicProgress`: phase, completed, total, message. Stati run: queued/running/waiting_input/ready/partial/failed/cancelled.
- `MagicServices.run_phase(phase: str, context: MagicContext, options: MagicOptions, report: Callable) -> Awaitable[dict]`. Risultati di fase atomici, schema e firme verificati prima del commit.
- `CoverageDecision`: beat_id, asset_id, provider, role=coverage/fallback_image/generic, enabled, edited_in_frame, edited_out_frame, source_in_frame, source_out_frame, verdict=verified/uncertain/rejected, reason. Nessuna selezione attiva con verdict diverso da verified.
- `MagicStore.create_or_resume(project_id, signature, options) -> dict`, `read(run_id) -> dict`, `transition(run_id, **changes) -> dict`, `checkpoint(run_id, phase, result, input_signature) -> None`.
- Esecuzione test: interpreter della `.venv` esistente; cartelle temporanee sotto `.test-tmp` con mkdir standard sul drive Windows. Stesso workaround verificato per i test v0075, nessuna modifica globale ai permessi.

### Task 1 — Store persistente e budget verificabile

**Files:** Create magic_models.py, magic_store.py; test `tests/unit/test_magic_store.py`.
**Produces:** Contratti sopra; artefatti `projects/{pid}/magic/{run_id}/run.json`, risultati per fase e registro chiamate con started/completed/unknown.
- [ ] Scrivere test `test_duplicate_start_reuses_run`, `test_signature_change_rejects_resume`, `test_crash_preserves_unknown_call`: stesso input riusa ID, firma cambiata non pubblica, richiesta iniziata non viene rimessa in coda automaticamente.
- [ ] Eseguire i test e osservare RED; implementare scritture atomiche, lock per progetto, contatori cloud/visivi senza credenziali e cancellazione persistente.
- [ ] Verificare GREEN con `python -m pytest -p no:cacheprovider tests/unit/test_magic_store.py -q`; commit del solo task.

### Task 2 — Coordinatore riprendibile e API

**Files:** Create magic_runner.py, magic_services.py (Protocol), magic_routes.py; modify curation_server.py per registrazione; test `tests/unit/test_magic_runner.py`, `test_magic_routes.py`.
**Consumes:** MagicStore, MagicOptions, MagicContext. **Produces:** `MagicRunner.start(project_id, options)`, `cancel(run_id)`, `resume(run_id)` e GET stato persistente.
- [ ] RED: finti servizi completano cut/editorial/research/selection/preparation/delivery in ordine; cancel impedisce nuove chiamate; restart riusa checkpoint, timeout ignoto va waiting_input; 13a chiamata con budget12 non parte.
- [ ] Implementare POST `/projects/{pid}/magic`, GET `/projects/{pid}/magic/latest`, GET `/magic/{run_id}`, POST `/magic/{run_id}/cancel` e `/resume`; nessun HTTP loopback. Attesa quota reale esplicita e ricezione bridge separata da preparazione.
- [ ] GREEN: `python -m pytest -p no:cacheprovider tests/unit/test_magic_runner.py tests/unit/test_magic_routes.py -q`; commit.

### Task 3 — CUT riusabile e protezione chiusura parole

**Files:** Modify cut_pass_routes.py, cut_pass.py, cut_boundaries.py; implement adattatore cut in magic_services.py; tests `tests/unit/test_magic_cut.py`, test_cut_pass.py, test_cut_boundaries.py.
**Produces:** Fase cut restituisce output_project_id, source_signature, cut_revision e mappa congelata; stesso servizio usato dalla UI CUT manuale.
- [ ] RED: pausa dopo consonante finale conserva fino a 120 ms ove liberi; parola successiva limita margine; ultima parola non scompare; take più lunga con concetto distinto conservata; run ripreso conferma un solo figlio.
- [ ] Estrarre solo l'operazione oggi chiusa nelle route in servizio richiamabile; riusare trascrizione, gruppi, controllo ripartenze/confini, pause e conferma. Non usare la preview renderizzata come sorgente Resolve.
- [ ] GREEN: test nuovi + regressioni CUT e source signature; verificare allineamento su media locale senza chiamate AI automatiche nei test; commit.

### Task 4 — Scelte editoriali e artifact delle selezioni

**Files:** Create magic_editorial.py; modify magic_services.py, api_first_director.py, transcript_intents.py; test `tests/unit/test_magic_editorial.py`.
**Produces:** Highlight/coverage in indici parola e frame puliti, contesto geografico e piano Director compatibile con il workflow attuale.
- [ ] RED: tema Egitto/polizia turistica non genera polizia americana; ogni chunk coperto una volta; keyword max tre parole; introduzione e parlato significativo possono restare visibili; testo aggiornato durante il run non sovrascritto.
- [ ] Riutilizzare provider/schema e salvataggi del Director; richiesta globale compatta più blocchi, sotto limite input+output del provider. Una risposta incompleta non sostituisce il testo. Scegliere provider già configurato senza nuove dipendenze OpenAI.
- [ ] GREEN: `python -m pytest -p no:cacheprovider tests/unit/test_magic_editorial.py tests/unit/test_transcript_intents.py -q`; commit.

### Task 5 — Ricerche contestuali e verifica dei candidati

**Files:** Create magic_coverage.py; modify magic_services.py, beat_research.py; tests `tests/unit/test_magic_coverage.py`, `test_magic_research.py`.
**Consumes:** Piano Task4, budget Task1. **Produces:** CoverageDecision verificati con motivazione e riferimenti ai candidati esistenti.
- [ ] RED: limite2query/fonte e6candidati, duplicati rimossi; clip geograficamente errata rifiutata; ranker indisponibile non risulta successful; CAPTCHA sospende soltanto fonte interessata; verifica visiva4/12 non oltrepassata.
- [ ] Usare ricerca attuale e ranker disponibile, Pexels prima e altre fonti abilitate dopo; query contestuale e breve trovabile. Giudizio visivo da campioni entro budget, non dal solo titolo. Se il check è indisponibile, registrare uncertain e provare alternative.
- [ ] GREEN su test sopra con provider finti e fixture locali, nessuna ricerca reale automatica; commit.

### Task 6 — Scheduling e immagini fallback disattivate

**Files:** Modify magic_coverage.py, magic_services.py, broll_timeline_export.py; tests `tests/unit/test_magic_schedule.py`, `test_magic_image_fallback.py`.
**Produces:** Coperture e immagini con ruoli e enable espliciti, intervalli validi e nessuna sovrapposizione non prevista.
- [ ] RED: niente video verified porta a immagine pertinente scaricata enabled=false; immagine mancante lascia gap dichiarato; beat<1,5s non produce flash; fine video mai superata; generica usata nel testo non duplicata in coda.
- [ ] Riutilizzare ricerca e download immagini esistenti. Pianificare intervalli 2–4s rispettando minimo1,5s e sorgente disponibile; non unire frasi semanticamente diverse. Conservare ID beat, motivo, ruolo e disabilitazione nei payload e nelle selezioni normali.
- [ ] GREEN su schedule/fallback e regressioni broll/image; commit.

### Task 7 — Export e layout delle immagini alternative

**Files:** Modify resolve_textplus_timeline.py, curation_server.py, resolve_native_cut.py; tests `tests/unit/test_magic_resolve_payload.py`, `test_magic_resolve_images.py`.
**Consumes:** Decisioni Task6 e preparazione selettiva esistente. **Produces:** Pacchetto standard con immagini alternative riconoscibili e receipt di consegna reale.
- [ ] RED: immagine alternativa su traccia dedicata sotto i titoli, Purple e disattivata; normali B-roll attivi invariati; export solo subs non scarica immagini; base video e marker invariati; bridge offline genera ready ma non delivered.
- [ ] Riutilizzare still-to-video frame exact e inserimento media esistenti, aggiungendo distinzione di traccia/ruolo e SetClipEnabled(False). Proteggere vecchi media durante refresh selettivo; nessun nuovo CreateFusionClip per i titoli.
- [ ] GREEN con regressioni export/handoff/subtitle/title e immagini; commit. Traguardo 1 pronto per test su video caricato.

### Task 8 — UI MAGICO e revisione dei risultati

**Files:** Create magic_ui.py; modify curation_ui_v2.py; tests `tests/unit/test_magic_ui.py`.
**Consumes:** API Task2. **Produces:** Pulsante dopo ingresso sorgente, opzioni avanzate, progressi, cancel/resume e collegamenti alle sezioni esistenti.
- [ ] RED: reload riaggancia run, doppio click non duplica, avanzamento fermo senza unità completate; riepilogo distingue video verificati, immagini disattivate e passaggi scoperti; attesa CAPTCHA ha link e ripresa.
- [ ] Integrare UI compatta coerente con accordion attuali, nessuna barra indeterminata falsa; rendere disponibili tutti i risultati nel normale progetto CUT senza bloccare modifiche manuali a run finito.
- [ ] GREEN: test UI + parsing JavaScript e verifica browser del caricamento/stato; commit.

### Task 9 — Sorgente Resolve multitraccia e CUT sicuro

**Files:** Create resolve_cut_source.py; modify resolve_bridge.py, standalone_bridge.py, magic_services.py, resolve_native_cut.py; tests `tests/unit/test_resolve_cut_source.py`, `test_magic_bridge_cut.py`.
**Produces:** `capture_cut_source(timeline, mark_in, mark_out) -> dict`, `remap_source_cut(snapshot, cut) -> list[dict]`, snapshot legato a firma sorgente/progetto/timeline e range originali.
- [ ] RED: IN/OUT non zero, più tracce AV, FPS30000/1001, ultima clip e vuoti; sorgente modificata rifiutata; retiming/composizioni non supportate fermate prima di APPLICA senza mutazioni.
- [ ] Acquisire sorgenti originali e offset delle clip; dichiarare capability supportata solo se la ricostruzione è verificabile. Ricostruire su nuova timeline da originali, preservando organizzazione e sync; non importare la guida audio come video. Adapter continua a non richiedere MCP.
- [ ] GREEN: fake adapter + regressioni bridge/native CUT; QA MCP solo su progetto test aperto e timeline dedicate, verificando audio/marker/sorgente invariati. Traguardo 2 verificato prima di dichiarare entrambe le sorgenti supportate; commit.

### Task 10 — Verifica completa, versione e consegna

**Files:** RAMBLA_VERSION, docs/HANDOFF.md; tests `tests/integration/test_magic_hybrid.py`.
- [ ] RED→GREEN: video lungo con take sbagliate, pause, parola finale, candidatura incoerente, immagine fallback, una fonte CAPTCHA, ripresa dopo restart, budget esaurito e handoff offline/online. Provider finti nei test ripetibili.
- [ ] Provare run reale su fixture utente salvata in copia con chiamate entro budget visibile; verificare testo completo, correttezza coperture e confini del CUT, rendendo espliciti avvisi editoriali.
- [ ] Eseguire suite CUT/Resolve/export/MAGICO e regressioni UI. Nessuna routine di agenti revisori: revisione finale in questa chat e handoff per Normal Chat come da AGENTS; correggere ogni difetto concreto prima della consegna.
- [ ] Incrementare versione unica app/bridge da quella effettivamente installata, salvare evidenze e limiti, aggiornare runtime senza perdere progetti. Pubblicazione su branch concordato solo dopo verifiche, niente force-push. Commit e stato TESTABLE=YES solo con percorsi effettivamente verificati.

## Autorevisione del piano

Spec coperta da Task1–10: economia/recovery1–2, CUT3, selezioni4, coerenza5, immagini/durate6, handoff7, UI8, sorgente Resolve9, test/consegna10. I contratti MagicContext/CoverageDecision e i nomi fase coincidono nei consumatori. Tutti i cinque Review Focus hanno test assegnati. I due traguardi sono espliciti; nessuna dichiarazione di supporto multitraccia basata sul solo percorso di video caricato. Il piano resta da revisionare prima dell'implementazione; esecuzione nativa sequenziale già scelta dall'utente.
