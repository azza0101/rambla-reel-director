# Catalogazione giornata — Piano d'implementazione V1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Partendo da un bin di riprese e dal copione PDF, creare un catalogo affidabile e riprendibile di appartenenza alle scene, poi materializzarlo in bin Resolve senza alterare gli originali.

**Architecture:** Catalogo canonico locale basato su **membership per intervalli sorgente**, non una clip = una scena. Orchestratore Electron/JS per clip, worker Python per matching conservativo, adapter ufficiale Resolve per bin e riferimenti. Job e journal atomici, con ripresa dopo errore.

**Tech Stack:** DaVinci Resolve Studio, `WorkflowIntegration.node`, Electron/Node, Python worker esistente, `LocalSemanticEncoder`/trascrizioni Resolve esistenti. No MCP, Codex o nuovo modello obbligatorio a runtime.

**Spec:** `docs/superpowers/specs/2026-10-26-day-footage-scene-catalog-design.md`

## Global Constraints

- Lavorare solo in `premontato-workflow/`, su branch isolato da `feat/premontato-workflow`; **nessun merge su main**, nessun RMBL/Auto-Cut.
- Conservare schema parole/timecode sorgente, source media IDs, funzionalità editoriali/ASD v0.11.11 e scelte dell'utente.
- Durante analisi e preview Resolve rimane **read-only**. Media Pool mutato solo su esplicito apply, dopo save e readback. Mai cancellare/trascodificare sorgenti, sostituire mappature audio o alterare altre timeline.
- Coordinarsi con agenti che integrano PR #20/#21 prima di modificare file condivisi `session.js`, `main.js`, `renderer.js`, `transcript_align.py`, `staged_dialogue.py`.
- Un file può appartenere a più scene. Clip priva di dialogo o con evidenza debole = `review`, non scena inventata.
- Subclip nativo solo dopo capability-probe della versione Resolve; `endFrame` potrebbe essere inclusivo. Fallback virtuale/SELECTS.
- Nessuna nuova credenziale, modello o componente MCP nell'installer; nessuna chiamata reale a Groq necessaria per test.
- Non dichiarare completata una integrazione Windows/Resolve sulla base di soli mock.

## Review Focus

1. File con più scene: nessun `MoveClips` dell'originale e range multi-scena distinti — test in Task 2 e Task 4.
2. ASR vuoto/parziale, ripartenze e parole generiche: non classificare a forza; una clip fallita non blocca il job successivo — Task 2/3.
3. Clip modificata o ricollegata prima dell'apply: validazione identità/fingerprint deve impedire scrittura — Task 1/4.
4. Media Pool già organizzato parzialmente al retry: niente bin o materializzazioni duplicate, restore folder/timeline iniziali — Task 4.
5. Scena ancora incompleta mentre ASR prosegue: disponibile in preview ma non considerata versione finale — Task 3/5.

---

## Mappa file

| File | Responsabilità |
| --- | --- |
| **Nuovo** `plugin/day_catalog_resolve.js` | Inventario ricorsivo, preview e apply guarded Media Pool, probe subclip, readback. Nessuna scelta editoriale. |
| **Nuovo** `plugin/day_catalog_store.js` | Manifest v1, fingerprint, atomic write, journal, revisioni/stati e invalidazione mirata. |
| **Nuovo** `worker/scene_catalog.py` | Finestre da trascrizioni con parole, ranking scene, contesto/ambiguità, membership per intervalli, non tagli video. |
| **Nuovo** `tests/unit/day-catalog-resolve.test.cjs` | Fake SDK per inventario, collisioni, dry-run, bin idempotenti, failure/readback. |
| **Nuovo** `tests/unit/day-catalog-store.test.cjs` | Journal e resume/stale/identità. |
| **Nuovo** `tests/unit/test_scene_catalog.py` | Scena multipla, ripartenze, frasi generiche, ordinamento, segmenti incompleti. |
| **Modifica successiva coordinata** `worker/protocol.py` | Nuova azione `catalog_scenes`, progress serializzabile. |
| **Modifica successiva coordinata** `plugin/session.js` | Orchestrazione incremental job per clip; stato del catalogo distinto dall'analisi scena. |
| **Modifica successiva coordinata** `plugin/main.js`, `plugin/preload.js`, `plugin/renderer.js`, `plugin/index.html` | IPC sicuro e tab di catalogazione con preview/apply. |
| **Non modificare** `plugin/resolve_adapter.js` per la prima implementazione se `day_catalog_resolve.js` può usare gli helper esposti/SDk; introdurre modifiche solo dopo coordinamento. |

## Task 1 — Inventario read-only del bin

**Interfaccia:** `scanDayMedia(sdk,{rootFolderId?,rootFolderPath?}) -> {projectId,sourceFolder,media[],warnings[]}`, con ordinamento deterministico per percorso bin + media ID.

- [ ] Scrivere test finto SDK: lettura ricorsiva di bin annidati, esclusione timeline, ID unici, no dipendenza dalla selezione corrente.
- [ ] Eseguire test e verificare FAIL per funzione assente.
- [ ] Implementare in `day_catalog_resolve.js`: props `File Path/FPS/Frames/Start TC/Type`, bin originale e ID; visit set, limiti di profondità, warning su media malformati senza bloccare gli altri.
- [ ] Eseguire test GREEN e suite JS baseline; fermarsi se il worker rileva un progetto Resolve diverso.
- [ ] Commit separato se questa task viene implementata autonomamente.

## Task 2 — Matching conservativo di scena per intervalli

**Interfaccia:** `catalog_scenes({scenes,sources,settings}, on_progress=None) -> {memberships,unassigned,source_status,scene_summary,warnings}`. Le sorgenti hanno `segments[].words[]` con frame originali.

- [ ] Test RED: 2 scene in un unico MP4, 3 ripartenze stessa scena in un file, "ciao" in molte scene, transcript vuoto, frase parafrasata, sorgenti mescolate nell'ordine di acquisizione.
- [ ] Implementare finestre da transcript preservando gli estremi e un ID stabile, ricavando candidati dal matching lessicale + `LocalSemanticEncoder` già in runtime (iniezione provider per test).
- [ ] Voti per scene + controllo della distanza dalle concorrenti; usare ancore diverse, ordinamento del copione e take resets come evidenze; non forzare match deboli e non trattare score come probabilità.
- [ ] Suddividere in membership non sovrapposte per scene diverse; segnalare confini contigui privi di silenzio invece di spostare parole senza prova. Mantenere sotto-range separati se un file ritorna a una scena precedente.
- [ ] Test GREEN; nel contratto i frame sorgente sono semichiusi `[start,end)`, idempotenti e senza editing manuale su test fixture.
- [ ] Eseguire Python suite completa dopo la task.

## Task 3 — Queue e journal incrementali

**Interfacce:** `openCatalogProject(root,identity)`, `upsertSourceJob(...)`, `markSourceResult(...)`, `resumeCatalog(...)`, `invalidateByFingerprint(...)`; nessuna dipendenza da UI.

- [ ] Test RED: 5 clip, trascrizione fallita nella clip 2, le altre 4 completano; riavvio dopo clip 3; clip invariata resta `done`, clip modificata `stale` solo nelle scene dipendenti.
- [ ] Journal atomico versionato con stati `pending/running/done/failed/skipped/stale`; al riavvio `running` torna rieseguibile con provenance; non cancellare risultati passati senza motivo.
- [ ] L'orchestratore usa il recupero trascrizioni Resolve per clip, progressivo e seriale (il bridge può bloccare); checkpoint dopo ogni media. Architettura aperta ad ASR locale opzionale in futuro, ma non includerlo in V1.
- [ ] Distinguere catalogazione provvisoria da `ready_to_edit_final` solo quando tutti i media di input sono risolti o l'utente richiede esplicitamente bozza provvisoria.
- [ ] Test GREEN con scritture/temp files reali e suite Node completa.

## Task 4 — Materializzazione sicura in Resolve

**Interfacce:** `previewCatalogPublish(sdk,catalog) -> {operations,warnings,blocked}`; `applyCatalogPublish(sdk,preview,{confirmed:true}) -> {applied,skipped,failed,readback}`.

- [ ] Test RED: analisi/dry-run non chiama AddSubFolder/MoveClips/AppendToTimeline/SetMetadata; mixed-scene mai sposta originale; binned scene idempotenti; fallimento in terza scena non impedisce successiva; scrittura respinta se `projectId` o source fingerprint differiscono.
- [ ] Implementare un manifest delle operazioni e mapping `scene_id → folder_id`, creare bin necessari e validare ogni operazione con readback `GetSubFolderList/GetClipList`; journal prima/dopo. Restore current folder/current timeline in `finally`.
- [ ] Primary: lasciare originali nei loro bin; creare riferimenti SELECTS per scena da `AppendToTimeline([{mediaPoolItem,startFrame,endFrame,...}])` o subclip nativi bounded **solo dopo probe** in progetto di prova. Verificare la timeline SELECTS (contenuto esatto in frame e audio) prima di considerare la scena pubblicata.
- [ ] Se bounded subclip è supportato su runtime, normalizzare fine inclusiva al boundary e controllare durata/readback; quando non lo è, fallback senza duplicare file o dichiarare errore irreversibile.
- [ ] Eventuale funzione `MoveClips` per originali monoscena deve essere opt-in separato, salvare bin origine, verificare media ID, non cambiare percorso su disco.
- [ ] Test GREEN JS e prova nativa su media sintetici disposable; mai usare il progetto utente per esperimenti API.

## Task 5 — Pannello e integrazione (V1)

**Interfacce:** IPC `catalogInventory`, `catalogAnalyze`, `catalogPreviewPublish`, `catalogApplyPublish`, `catalogResume`, `catalogEditMembership`.

- [ ] Coordinare i file già in lavoro dall'altro agente e recuperare il nuovo HEAD prima di ogni modifica.
- [ ] Test RED per IPC: accesso trusted, validate request, cancel funziona, no operazioni mentre un apply è già attivo, nessun testo privato/paths nei log di supporto.
- [ ] Implementare UI `Cataloga giornata`: radice Riprese, per-clip progress/cache/error; scene ordinate, range/candidate/confidenza relativa, colonna ambiguo, correzioni, preview diff e pulsante Conferma; no "crea timeline" se riferimenti mancanti.
- [ ] Salvare catalogo e bozze senza sovrascrivere l'attuale stato `Session.analyze()`; mantenere la UI di singola-scena utilizzabile e i relativi autosave.
- [ ] Suite Node/Python e smoke Resolve 20/21 (versione reale dell'utente) con 2 scene, un file misto e un errore di trascrizione simulato.

## Task 6 — Collaudo, gate e pubblicazione

- [ ] Test su girato reale: input misti, senza dialogo, ripartenze, ciak se presente, speaker overlapping; misurare cache vuota, cache calda, GPU occupata/libera separatamente.
- [ ] Verificare source frame mapping e readback Resolve, semantica bounded-import, nessun cambio delle timeline esistenti, bin/riferimenti idempotenti.
- [ ] Eseguire confronto gold di assegnazioni e lasciare in `review` ogni dubbio; non inventare target numerici di precisione prima di avere annotazioni umane.
- [ ] Aggiornare README, changelog, test e release separata solo dopo collaudo nativo. PR dedicata **draft** fino al gate Windows/Resolve.

## V2 — Piano separato dopo V1

Un job per scena `ready_to_edit_final`, riutilizzando `buildPlan` Groq/locale e `createTimeline` esistenti con la sola membership di quella scena; versioni, resume, retry/skip e successivo assemblaggio del master in ordine copione. Casi obbligatori: scena 2 fallisce, scena 3 continua; scene provvisorie non entrano nel master finale senza conferma; sorgenti in comune conservano gli originali, frame e audio. Scrivere una spec/piano V2 più dettagliati dopo il collaudo V1, non aggiungere la master globale alla task 5.

## Primo smoke sul PC dell'utente

- Aprire un progetto di prova e importare 2 file: A con 2 scene nello stesso file, B con 1 scena/2 take.
- Verificare read-only inventory + ASR da Resolve, risultato `memberships` con source frame.
- Eseguire preview e confrontare le operazioni con quelle previste.
- Applicare in un progetto disposable, controllare folder IDs, timeline/source mapping e ri-eseguire apply per provare idempotenza.
- Simulare una clip mancante/errore ed eseguire resume. Rifare con file sorgente modificato.
- Confermare che la selezione e la timeline di partenza sono conservate, e che Premontato v0.11.11 continua a funzionare.
