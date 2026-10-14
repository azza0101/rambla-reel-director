# Native CUT and Selective Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inviare da 7 le sole componenti selezionate, creando il CUT nativo in Resolve dal video lungo originale, e scaricare l'MP4 CUT sotto il player.

**Architecture:** Un contratto esplicito delle componenti viene applicato prima della preparazione/download. Il pacchetto congelato include sorgente originale, FPS/formato e mappa CUT; una funzione dedicata crea e verifica la base nativa, poi le componenti opzionali usano i tempi già montati. Il download MP4 riusa il render completo della revisione.

**Tech Stack:** Python/FastAPI, JSON persistente, JavaScript UI esistente, FFmpeg, Resolve scripting API 21.1, pytest e test Node.

**Spec:** ../specs/2026-10-14-native-cut-selective-export.md

## Global Constraints
- Video lungo originale come fonte di ogni clip nativa; non clean.mp4/preview.mp4.
- Full HD: 1920×1080 landscape, 1080×1920 portrait, 1080×1080 square; altri rapporti con lato corto1080 e dimensioni pari.
- FPS reali della sorgente, inclusi 30000/1001; nessuna conversione implicita a30.
- IN/OUT piano esclusivi; video/audio stessi frame sorgente e destinazione.
- Nuova timeline CUT; non modificare altre timeline o marker.
- Pacchetto applicato solo tramite APPLICA e sessione bridge corrente.
- Scelte/timing dal piano congelato del progetto derivato, senza prendere revisioni nuove del padre.
- Nessuna chiamata AI per export, download o costruzione timeline.
- Esecuzione nativa nella chat corrente, come già scelto dall'utente; nessuna delegazione proattiva.

## Review Focus
- File originale spostato/sostituito: preflight deve segnalare indisponibilità o identità cambiata prima delle mutazioni (Task2).
- Source con rotazione o FPS frazionario: formato visualizzato e frame devono corrispondere, non ai valori arrotondati (Task3).
- Progetto CUT derivato più vecchio del padre: export del piano congelato corretto (Task2).
- Zero componenti / titolo assente / ricerca non fatta: zero componenti bloccato; video-only non dipende da titolo o ricerca (Task1 e4).
- Errore parziale e retry: nessuna duplicazione delle clip nella timeline generata (Task3 e5).

## Files e responsabilità
- `backend/app/export_components.py` (nuovo): selezioni/availability e filtro per provider.
- `backend/app/native_cut_export.py` (nuovo): piano/file sorgente congelati, formato, contratto e validazione native_cut.
- `backend/app/resolve_native_cut.py` (nuovo): creazione/verifica base nativa via adapter Resolve.
- `backend/app/curation_server.py`: richieste selettive e preflight CUT al posto del blocco globale.
- `backend/app/resolve_textplus_timeline.py`: integrazione base CUT ed overlay; estensione controllata ai FPS frazionari per nuovo flusso.
- `backend/app/resolve_handoff.py`, `resolve_handoff_jobs.py`: riepilogo CUT, destino new e retry coerenti.
- `tools/resolve_bridge/standalone_bridge.py`: versione compatibile, riepilogo/destino per pacchetto CUT.
- `backend/app/timeline_export_ui.py`: tendina componenti, conteggi e singolo invio.
- `backend/app/cut_pass_routes.py`, `cut_pass_ui.py`: MP4 completo sotto player.

## Task 1: Contratto componenti e preparazione selettiva
**Files:** Create export_components.py; modify curation_server.py, timeline_export_ui.py; test tests/unit/test_export_components.py e test_resolve_prepare_jobs.py.
**Interfaces:** `ExportComponents` con bool video/subtitles/highlights/broll/social/generic; `normalize_components(value, *, has_native_cut: bool) -> dict[str,bool]`; `filter_selected_media(rows, components) -> list[dict]`.
- [ ] Scrivere test fallente: tutte false rifiutate; video-only accettato; stock/immagini separati da youtube_shorts/tiktok; richiesta legacy mantiene default precedente.
- [ ] Eseguire `.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_export_components.py -q`, verificare fail.
- [ ] Implementare funzioni e campi persistenti `export-options.json` per progetto; GET/PUT `/projects/{pid}/export-options` con conteggi/availability. POST resolve-preparation accetta componenti opzionali.
- [ ] Collegare filtro prima di prepare_selected_media e prepare_generic_media: componenti escluse non scaricano né generano SRT/template. Selezioni UI salvate e pulsante unico con riepilogo.
- [ ] Test video-only senza visual-plan, subs o template; selezioni zero e bridge audio-only video disattivato con motivo. Verificare test esistenti e nuovi, commit dei soli file di task.

## Task 2: Pacchetto CUT congelato
**Files:** Create native_cut_export.py; modify cut_pass_routes.py, curation_server.py; test tests/unit/test_native_cut_export.py.
**Interfaces:** `load_native_cut(project_root: Path, projects_root: Path) -> dict`; `validate_native_cut(cut: dict) -> None`; `native_cut_format(width:int,height:int,rotation:int=0) -> tuple[int,int]`.
- [ ] Test fallente: progetto derivato usa cut-origin.plan anche se padre modificato; sorgente non è clean.mp4; intervalli destinazione contigui e uguali a sorgente; file mancante genera errore preflight.
- [ ] Eseguire test e verificarne il fallimento.
- [ ] Implementare source_path, source_identity, fps razionale, width/height di display, revision, segments, alternatives e duration_frames. Salvare identità originale nel provenance nuovo; gestire esplicitamente il provenance legacy con verifica metadati, senza accettare un proxy al posto dell'originale.
- [ ] Video-only costruisce payload vuoto di overlay e include native_cut senza dipendenze dal piano editoriale. Progetto CUT con overlay senza video richiede base CUT corrispondente verificata.
- [ ] Sostituire middleware globale con preflight della combinazione supportata, lasciando errore chiaro per CUT su guida audio multitraccia non ancora supportato.
- [ ] Verificare test e regressioni CUT; commit.

## Task 3: Costruzione della timeline nativa e verifica
**Files:** Create resolve_native_cut.py; modify resolve_textplus_timeline.py; test tests/unit/test_resolve_native_cut.py e test_resolve_timing_regression.py.
**Interfaces:** `create_native_cut_base(resolve, project, payload: dict, *, progress=None) -> dict` restituisce timeline, fps, base_frame, video_count, audio_count, source_item_id; `verify_native_cut_base(timeline, cut:dict, base_frame:int) -> dict`.
- [ ] Consultare MCP get_whats_new e stubs MediaPool/Timeline prima delle chiamate, per stabilire convenzioni IN/OUT e API impostazioni per timeline locale.
- [ ] Scrivere fake-adapter test: `[10,40)` importato per30frame, video/audio entrambi a base+edited_in; clip successiva contigua; frame0 e ultima parola; sorgente è originale lungo; impostazioni altre timeline immutate.
- [ ] Eseguire test fallenti.
- [ ] Implementare import originale/idempotente, timeline numerata nuova, impostazioni locali1080/rotazione/FPS reali e AppendToTimeline nativo video/audio; verificare convenzione endFrame dalla API e usare OUT esclusivo del piano convertito una volta.
- [ ] Aggiungere take alternative su traccia superiore disabilitata senza audio attivo; verificare frame e durata reali dopo inserimento.
- [ ] Test Fraction30000/1001,24,25,30; portrait/landscape/square; retry su timeline parziale rimuove solo risorse generate identificabili e non duplica clip.
- [ ] Verificare e commit. Non riutilizzare il ramo integer-only del creatore attuale senza adattare e testare il nuovo flusso.

## Task 4: Overlay e componenti sulla base CUT
**Files:** Modify resolve_textplus_timeline.py, curation_server.py; test tests/unit/test_native_cut_components.py e regression title/subtitle/media esistenti.
**Interfaces:** Task2 native_cut + Task3 base_frame; componenti già filtrate da Task1. Tempi overlay relativi al montaggio pulito, sommati una volta a base_frame.
- [ ] Test fallente: titoli/subs/B-roll/social seguono edited frames; generiche dopo duration_frames+gap2s. Un pacchetto video-only non accede a KURA_title o sottotitoli.
- [ ] Eseguire test fallenti.
- [ ] Integrare la base CUT nel creatore, applicando titoli separati sopra tutti i video (Yellow), coverage(Purple), generiche(Beige) e SRT nativo solo se richiesto. Verificare timecode a FPS frazionario, non assumere30.
- [ ] Test tempi vicini a fine video e overlay su revisioni sbagliate rifiutati; verificare conteggi, durata e nessuna modifica alla base durante inserimento.
- [ ] Verificare suite interessate e commit.

## Task 5: Bridge e riepilogo coerenti
**Files:** Modify resolve_handoff.py, resolve_handoff_jobs.py, standalone_bridge.py; tests test_resolve_handoff.py, test_resolve_handoff_jobs.py, test_standalone_resolve_bridge.py.
**Interfaces:** Pacchetto dei task1/2, runner del task3/4. `native_cut` impone destination_mode=new; nessuna mutazione al ricevimento.
- [ ] Test fallente: riepilogo include numero tagli/fps/formato e componenti scelte; APPLICA per VideoCUT crea nuova timeline; sessione/versione errata rifiutata prima di Apply; retry senza doppia append.
- [ ] Eseguire test fallenti.
- [ ] Implementare riconoscimento capability native_cut, compatibilità versione, selettore destinazione bloccato a nuova per VideoCUT e spiegazione leggibile. Overlay-only richiede timeline CUT id/revisione corrispondente.
- [ ] Salvare ricevuta con timeline_id/revision/source_identity e snapshot verificato, usabile per invii successivi.
- [ ] Test caricamento automatico bridge aggiornato e regressioni heartbeat; verificare e commit.

## Task 6: Download MP4 completo sotto anteprima
**Files:** Modify cut_pass_routes.py, cut_pass_ui.py; test tests/unit/test_cut_download.py e test_cut_preview_player.py.
**Interfaces:** POST `/projects/{pid}/cut/download` lancia job kind=download; GET `/projects/{pid}/cut/download/{revision}` restituisce FileResponse attachment completo. Stessi render_cut/source/piano congelato già disponibili.
- [ ] Test fallente: riusa clean-{revision}.mp4 se esiste; non scarica preview proxy; revision obsoleta409; CUT confermato scarica il proprio file clean verificato.
- [ ] Eseguire test fallenti.
- [ ] Implementare download osservabile e bottone SCARICA MP4 CUT sotto il player, senza import Resolve e senza nuove chiamate AI. Mantenere anteprima e conferma funzionanti.
- [ ] Verificare e commit.

## Task 7: Verifica integrata e consegna
**Files:** RAMBLA_VERSION, docs/HANDOFF.md, test integrazione nativo dedicato.
- [ ] Eseguire suite di task e regressioni export/bridge/CUT senza iniziare ricerche media o cloud.
- [ ] Provare UI: sole componenti selezionate, zero componenti, video-only, download, progresso/errore. Provare bundle completo con file già locali.
- [ ] Verificare in Resolve su timeline di test nuova con sorgente originale: FPS/formato, sorgente delle clip, video/audio IN/OUT/posizioni esatti e durata conforme. Non modificare timeline utente esistenti; ripristinare contesto aperto e scartare solo test creati da questa verifica.
- [ ] Fare revisione finale tramite tool di code review, correggere difetti verificati, ripetere solo test interessati.
- [ ] Incrementare versione unica app/bridge, aggiornare HANDOFF con evidenze e limitazioni effettive, aggiornare runtime/bridge. Mostrare sezione7 e download appena implementati.

## Autoverifica del piano
Copertura: tutti i sei componenti, VideoCUT nativo e MP4 separato coperti. Review Focus mappato ai task1–5. Signatures native_cut e component keys condivise fra i task. L'export di CUT su una guida multitraccia Resolve resta esplicitamente fuori dalla prima implementazione, senza bypass del preflight.
