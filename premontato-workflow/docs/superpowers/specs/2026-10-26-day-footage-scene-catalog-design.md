# PREMONTATO — Catalogazione automatica del girato per scena (design V1)

**Data:** 26 ottobre 2026  
**Stato:** proposta di progettazione; **non** è codice prodotto né una release.  
**Base osservata:** `feat/premontato-workflow` @ `52244b93f9437b04e430132d918fe744f8b02bb0` (v0.11.11); verificare nuovamente prima di implementare.

## Obiettivo utente

Importare/avere in Resolve tutte le riprese di una giornata in un unico bin ("Riprese"), caricare il copione PDF in Premontato, trascrivere/riusare trascrizioni progressivamente, riconoscere quali **intervalli** corrispondono a quali scene e ritrovarsi il Media Pool organizzato per scene, senza dover classificare manualmente ogni file. Poi elaborare il montaggio scena per scena, senza riavviare l'intera giornata per una scena fallita. Funzionamento locale e autonomo durante l'uso; Codex/MCP non richiesti a runtime.

**Successo visibile V1:** catalogo con scene nell'ordine del copione, coperture/ambiguità, progressione per singola clip, bin dedicati con riferimenti selezionabili in Resolve, originali intatti, ripresa automatica dopo errore/interruzione. Il montaggio dell'intero film è la fase V2, su fondazioni già versionate per scena.

## Tre approcci considerati

1. **Spostare tutti i media originali in bin per scena.** Semplice con `MediaPool.MoveClips`, ma un unico MP4 può contenere più scene: una clip originale vive in un solo bin. Non adottare come comportamento predefinito.
2. **Catalogo virtuale per intervalli sorgente + bin scena in Resolve.** **Raccomandato.** Originali nella posizione iniziale; membership molti-a-molti (una clip, scene differenti); per ogni scena, riferimenti/materializzazione sicura in Resolve, eventualmente subclip nativi dove supportati o una timeline SELECTS non distruttiva. Supporta ingestion incrementale.
3. **Un'unica timeline di tutte le riprese e poi dividerla.** Accoppia troppe operazioni, non risolve i casi ambigui e rende fragile il retry; non adottare.

Questa è una scelta tecnica proposta, non una preferenza già approvata dall'utente.

## Stato del codice su cui innestarsi

- `plugin/main.js`: bridge ufficiale `WorkflowIntegration.node`, IPC e recupero trascrizioni.
- `plugin/resolve_adapter.js`: `snapshot`, `getSelectedTranscriptions`, scansione ricorsiva del Media Pool con `analyzedMediaItems`, verifica degli ID, e `createTimeline`. Attualmente richiede una timeline aperta, anche per lo snapshot.
- `plugin/session.js`: una sola analisi globale su media selezionati, scena singola o combinazione selezionata, worker Python seriale.
- `worker/script_parser.py`: produce `scenes[]` con `scene_id`, `heading`, `beats[]`.
- `worker/transcript_align.py`: confronti lessicali, semantici, scena; è costruito per identificare la scena di un insieme di riprese, non per catalogare singoli intervalli di tutta la giornata.
- `worker/staged_dialogue.py`: montaggio con Groq e controllo parlante; riutilizzare **per scena**, non lanciarlo contemporaneamente su tutti i file.
- V0.11.11 ha regia Groq separata, reazioni interne V3, base V2/A2 e revisioni; **non** alterarle in questa feature.
- PR #20/#21 ottimizzano encoder/PCM/RMS e ASD; coordinarsi prima di toccare file in comune.

**Distinzione:** Premontato usa già il bridge Resolve ufficiale, NON invoca il progetto open-source Resolve MCP a runtime. Il MCP serve come catalogo di API e come eventuale ambiente di sviluppo/probe; non aggiungerlo come dipendenza obbligatoria al plugin installato.

## Ricerca di API e componenti riusabili

| Operazione | API Resolve / riferimento MCP | Esito e limiti |
| --- | --- | --- |
| Inventario bin e clip | `GetRootFolder`, `GetSubFolderList`, `GetClipList`, `GetMediaId`, `GetClipProperty` | Compatibile con il traversal già usato in `resolve_adapter.js`. Gli ID vanno riverificati prima di scrivere. |
| Trascrizione su media già importati | `MediaPoolItem.TranscribeAudio(...)`, `GetTranscription(...)` tramite bridge installato | Riutilizzare quella già presente; se manca, schedulare per clip con avanzamento e validazione parole/timecode. |
| Bin scena | `AddSubFolder(parent,name)`, `MoveClips([item],folder)` | API dirette disponibili; MCP ha `media_pool.organize_clips` e `move_clips`. Il movimento delle sorgenti deve essere opt-in, con readback e registrazione provenienza. |
| Annotazioni scena/take | `GetMetadata`, `SetMetadata`, `AddMarker` | Metadati/proposte separati dai dati sorgente; non sovrascrivere annotazioni utente esistenti senza conferma. |
| Subclip fisici per segmenti multi-scena | `MediaStorage.AddItemListToMediaPool([{media,startFrame,endFrame}])`, helper MCP `import_bounded_media` | **Capability probe obbligatoria**: un test dell'MCP su Studio 21.1.1 ha trovato fine inclusiva. Non presumere stessa semantica su tutte le build/fps/file. Conservare mapping all'originale. |
| Ciak/slate opzionali | Resolve 21 `AnalyzeForSlate` + metadata `Scene`, `Take`, `Angle`, `Shoot Day` | Richiede modello Extras, disponibilità non garantita e verifica degli eventuali metadati proposti. Non necessario per V1; non sostituisce ASR. |
| IntelliScript | Resolve 20 Studio UI | Crea una timeline da copione e trascrizioni; non risolve catalogazione incrementale per intervalli né fault isolation. Nessun equivalente pubblico via scripting dato per scontato. |
| Search/trascrizioni terze | StoryToolkitAI (GPLv3) | Buon riferimento per ricerca trascrizioni e gruppi; non incorporare codice GPL in Premontato. |

Riferimenti da riprovare prima dell'implementazione:
- Resolve scripting API: https://github.com/samuelgursky/davinci-resolve-mcp/blob/main/docs/reference/resolve_scripting_api.txt
- MCP ingest: https://github.com/samuelgursky/davinci-resolve-mcp/blob/main/docs/kernels/media-pool-ingest-kernel.md
- MCP bounded import e cautela endFrame: https://github.com/samuelgursky/davinci-resolve-mcp/blob/main/docs/SKILL.md
- Resolve 20 IntelliScript (Blackmagic): https://documents.blackmagicdesign.com/SupportNotes/DaVinci_Resolve_20_New_Features_Guide.pdf
- Resolve 21 AI Slate ID (Blackmagic): https://documents.blackmagicdesign.com/SupportNotes/DaVinci_Resolve_21_New_Features_Guide.pdf
- StoryToolkitAI: https://github.com/octimot/StoryToolkitAI

## Modello canonico (sidecar locale, schema v1)

`CatalogProject`:
- `project_id`, `script_fingerprint`, `source_root_folder_id`, `catalog_version`, `created_at`, `updated_at`.
- `scenes[]`: `scene_id`, `ordinal`, `heading`, `beat_ids[]` — l'ordine viene dal copione; gli heading possono ripetersi.
- `sources[]`: `media_id`, `path`, `original_folder_id`, `original_folder_path`, `fps`, `duration_frames`, `start_tc`, `file_size`, `mtime_ns`, `transcript_status`.
- `memberships[]`: `membership_id`, `media_id`, `scene_id`, `source_start_frame`, `source_end_frame`, `confidence`, `runner_up_margin`, `evidence[]`, `status` (proposed/auto_ready/review/confirmed/rejected), `source_take_hint`.
- `materializations[]`: `membership_id`, tipo (virtual / selects_timeline / native_subclip / moved_original), ID Resolve creato, bin ID, base sorgente e readback.
- `jobs[]`: `job_id`, `kind`, `source_id` o `scene_id`, `status` (pending/running/done/failed/skipped/stale), `attempts`, `error_code`, `checkpoint`.
- `warnings[]` e `unassigned_ranges[]`, mai accorpare automaticamente gli incerti alla scena più probabile.

Gli intervalli sono **source-relative [start_frame,end_frame)**, canonici per il montatore e coerenti con le parole ASR originali. Tradurre la semantica dell'API bounded-import solo al confine dell'adapter dopo probe; non alterare `source_start_frame`/ `source_end_frame` del catalogo. Gestire fps sorgente diverso da timeline, timecode sorgente e drop-frame. `media_id` del subclip è distinto dall'originale e non sostituisce l'ID della sorgente canonica.

## Algoritmo e priorità delle evidenze

1. Selezionare il bin radice da catalogare, normalmente `Riprese`, inventariare ricorsivamente senza dipendere dalla selezione corrente. Non importare di nuovo file già presenti. Escludere timeline/compound/non-video secondo capacità, segnalando eccezioni.
2. Parse del PDF una volta. Snapshot di ID e fingerprint media, verifica parole/timecode, recupero trascrizioni già presenti. Trascrivere soltanto clip mancanti **una per volta**, con checkpoint dopo ogni clip; non richiedere l'intero girato prima di mostrare risultati provvisori.
3. Costruire finestre di parlato da parole/segmenti mantenendo tempi sorgente e indizi di interruzioni. Recuperare corrispondenze lessicali, embedding semantici locali esistenti e ordine delle battute, distinguendo cue di troupe/ripartenze/aggiunte; minimizzare nuove chiamate Groq. Eventuale Groq su casi ambigui è facoltativo e solo testo, con cache e consenso esplicito sulla rete.
4. `SceneMembership`: per ciascuna finestra assegnare scena solo con evidenza indipendente sufficiente, margine dal secondo candidato e coerenza locale. Non classificare una scena soltanto per "ciao", "sì" o un nome ricorrente. Rafforzare con eventuali ciak verificati/scene metadata. Una stessa ripresa può avere più `membership` per scene diverse o più take della stessa scena.
5. Accorpare finestre vicine della stessa scena senza attraversare passaggi ad altre scene o blocchi non parlati ambigui. Confini da timecode ASR e silenzi validati; se un confine non è sicuro, proporre un intervallo incerto, non inventare un taglio. Mantenere i segmenti senza audio/scene come `unassigned`.
6. Le decisioni ad alta affidabilità diventano `auto_ready`; le altre restano `review`. Soglie calibrate su riprese reali, non probabilità inventate. Visuale e Light-ASD soltanto sulle scene che verranno poi montate.
7. Cache per clip, scena, versione algoritmo/copione e fingerprint. Modificare un file invalida quel file e le scene toccate, non tutta la giornata.

**Regola di completezza:** un catalogo provvisorio può apparire prima della fine della trascrizione; una scena non è `ready_to_edit_final` finché gli altri file del perimetro non sono stati esaminati o l'utente non sceglie esplicitamente di montare una versione provvisoria, che va marcata e ri-versionata quando arriva nuova copertura.

## Organizzazione proposta nel Media Pool

```text
Riprese/                               ← file originali dove già si trovano
Premontato - Catalogo Giornata/
    01_SCENA_01 - INT SALONE/
        SELECTS_SCENA_01             ← timeline/refs, non altera originali
        [subclip nativi, se capability confermata]
    02_SCENA_02 - EXT STRADA/
        SELECTS_SCENA_02
    ...
    98_DA_VERIFICARE                 ← riferimenti/proposte, NON spostamenti impliciti
    99_SENZA_DIALOGO                 ← materiale non riconosciuto, non scartato
```

- Il default è **non spostare né duplicare indiscriminatamente gli originali**. Una clip multi-scena è referenziata in più scene mediante intervalli; preferire subclip nativi bounded se un probe non distruttivo in progetto di test conferma comportamento; altrimenti timeline SELECTS per scena con range sorgente e manifest.
- Un'opzione avanzata `Sposta originali mono-scena` potrà usare `MoveClips` **soltanto** per clip totalmente ed esclusivamente attribuite a una scena, previa anteprima, conferma, save Resolve e readback. Salvare bin d'origine per ripristino manuale/automatico controllato. Mai cancellare o rinominare clip originali.
- Bin scena nominati con ordinale + heading sanitizzato/troncato e ID logico conservato nel manifest; supportare heading duplicati, caratteri Windows non validi, collisioni e nuove esecuzioni idempotenti.

## Interfaccia proposta

Nuovo tab `Cataloga giornata`, distinto dall'attuale `Analizza scena`:
- `Sorgente: Riprese` (seleziona bin radice) + `Copione PDF` già caricato;
- `Analizza girato`: progresso per clip con trascritto/in cache/errore, scene provvisorie disponibili da subito;
- tabella scene nell'ordine copione con clip/secondi attribuiti, `pronta` / `da verificare` / `errore`, livello di evidenza e range;
- correzione manuale dell'appartenenza e dei confini, anteprima `Organizza Media Pool` (dry-run), pulsante separato di conferma applicazione;
- `Monta per scene` solo nella fase V2, con pulsanti retry/pause/resume, senza aprire/creare automaticamente una master per clip non verificati.

## Resilienza e sicurezza: piano → applicazione → verifica

- Nessuna scrittura in Resolve durante catalogazione/dry-run. Nelle operazioni esplicite: verificare `project_id`, media IDs, fingerprint, bin originale; salvare progetto Resolve; applicare modifiche per elemento; readback dopo ogni mossa/creazione; scrivere journal atomico. Non ripetere ciecamente operazioni ambigue.
- Salvare e ripristinare folder selezionato e timeline iniziale; non alterare timeline, audio mappings o proprietà sorgenti esistenti.
- Ripresa deterministica dopo crash: manifest + operazioni confermate distinguono `planned` da `applied`. Non creare duplicati su retry. Mai cancellare bin utente.
- Una clip senza ASR o una scena con errore diventa `failed/review`; le altre proseguono. Errori globali come progetto Resolve cambiato, perdita identità o incompatibilità schema bloccano invece **tutte** le scritture.
- Su v2 ogni scena ha un job isolato, uno snapshot degli input, piano e timeline versionata. Se S02 fallisce, S03 si elabora; `MASTER PREMONTATO` si costruisce in un secondo passaggio con sole scene valide e un report esplicito delle mancanti. Non inventare intervalli/scene vuote né creare silent filler.

## Prestazioni / scheduling

- Inventario e text-matching prima di scansioni video; YuNet/ASD solo sulle scene in montaggio.
- ASR Resolve progressivo per clip e riuso trascrizioni; stato GPU/comunicazioni con Resolve visibile, non eseguire più job Resolve in parallelo senza validazione. ComfyUI sulla 4090 può contendere GPU.
- Encoder semantico condiviso/cache testuale (coordinare con PR #20), batching per token e clip, nessun corpus di tutte le immagini in memoria.
- Evitare rianalisi dopo correzione di singola scene o nuova clip. Mostrare tempi per inventario, ASR, matching, pubblicazione bin e montaggio.
- Limiti configurabili per numero di clip/job, durata e RAM; pausa e ripresa tramite journal, non lavoro nascosto da un agente remoto.

## Casi di accettazione

1. 30 clip non ordinate / 8 scene → catalogo riproducibile con ordine del copione, senza nuove timeline all'analisi.
2. Un MP4 contiene scene 1 e 3 → **due membership** con range originali, nessun MoveClips della sorgente.
3. Tre take della stessa scena in un MP4 → tre intervalli senza sovrascrivere o rinumerare parole.
4. "Ciao", "azione", rumore, silenzi e B-roll → non forzare scena sulla base di testo debole.
5. Stessa battuta in due scene → ambiguità o risoluzione basata su contesto+evidenza, mai certezza fittizia.
6. ASR di una clip fallisce → altre clip continuano, ripresa dopo riapertura senza ritrascrivere quelle valide.
7. Una clip cambia percorso/durata/fps/fingerprint → invalidazione mirata e nessuna scrittura sul media sostituito.
8. Uno stesso `media_id` già catalogato → nessuna duplicazione di bin/subclip/timeline al secondo apply.
9. Conflitto fra metadato slate e parlato → quarantena per revisione, non sovrascrivere metadati.
10. Test capability subclip restituisce fine inclusiva → mapping source-relative preservato e risultato verificato, con fallback se differisce.
11. Scrittura Resolve fallisce dopo due bin → journal permette resume senza duplicati; progetto e timeline sorgenti invariati.
12. Montaggio futura scena 2 fallisce → scena 3 si completa; master non finge che scena 2 esista.
13. Modifica di una sola scena del copione → invalidare membership dipendenti, non ricalcolare tutto il corpus.
14. Nessuna credenziale esterna, percorso/nome girato o testo privato nei report di supporto per default.

## Milestone e non-obiettivi

**V1a:** inventory + ASR progressivo + catalogo per intervalli + review in Premontato, nessuna mutazione Media Pool.  
**V1b:** publishing Resolve dry-run/readback, bin scena e SELECTS/subclip con capability probe; mobilità degli originali esclusivamente opt-in.  
**V2:** job di montaggio per scena, timeout/retry/skip/checkpoint e master finale che concatena scene riuscite nell'ordine copione, senza perdere le funzionalità editoriali v0.11.11.  
**Non-obiettivi iniziali:** edit multicam completo, riconoscimento emozioni, sincronizzazione di camere senza timecode/ciak valido, inventare testo per scene mute, automazione UI con click a coordinate, trascinare ogni frame in timeline globale.

**Da verificare sul PC reale:** versione Studio/Workflow SDK, effettivo supporto bounded-subclips e semantica endFrame, bin move con readback, folder IDs, campioni audio senza parola, tempo ASR con GPU libera, rendering e convenzioni di timecode.
