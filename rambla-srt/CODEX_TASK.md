# Task Codex — implementare la Workflow Integration RAMBLA SRT

Base di riferimento: `autocut-standalone` al commit `a1c73bee994a3c5825df2686238ca8b03b12b3c3`. Leggi obbligatoriamente `tools/autocut_integration/{main.js,preload.js,source_adapter.js,manifest.xml,package.json}`, `tools/install_autocut_integration.py`, `backend/app/autocut_update.py`, `docs/AUTOCUT_INTEGRATION.md` e i relativi test. Implementa in cartella SEPARATA `rambla-srt`, senza modificare AutoCut.

1. Recupera e archivia nella nuova cartella il sorgente reale `RAMBLA_SRT_Range.lua` V3.1 da `RAMBLA_SRT_V3_1_WINDOWS_MAC.zip` prima di migrare. Se il sorgente non è recuperabile, segnala il blocco; usa README come specifica, ma non affermare preservazione bit-per-bit.
2. Scrivi test di regressione sui file SRT emessi dalla V3.1 (o fixture reali): single + original, single + zero, multi ordinato/overlap/dedup, tempo iniziale timeline non-zero, missing IN/OUT, context ON/OFF, unicode, caption a cavallo dei limiti, framerate 23.976/25/30, drop-frame dove pertinente.
3. Costruisci Workflow Integration `com.rambla.srt` standalone, GUI RAMBLA responsive e scroll verticale: switch SINGLE/MULTI con SINGLE di default; differenzia visivamente solo il gruppo multi. Scelta file/folder, optional filename, checkbox timecode, checkbox context in fondo, export, apri cartella, AGGIORNA; stato e messaggi di errore leggibili. Evitare taglio lato destro anche a 620px o zoom 125%.
4. Integra lettura read-only di timeline, tutte le tracce sottotitoli, IN/OUT e timecode; blocca cambi di timeline tra cattura degli intervalli ed esportazione. NON applicare restrizione AutoCut `una clip video integrale`.
5. Installer/updater separati e sicuri, backup e rollback, release `srt-*`; non toccare runtime o file AutoCut. Evitare di introdurre dipendenze Python non indispensabili.
6. QA reale in Resolve Studio 21 Mac+Windows, inclusa importazione SRT con commenti # e test di aggiornamento del solo plugin. Qualsiasi limite host/API va riportato, non mascherato.

**Gate:** finché la verifica live e regressiva non passa, lascia installata e utilizzabile la V3.1 script; nuova Workflow Integration affiancata con nome/ID diverso. PR draft verso base concordata; niente merge o installazione automatica nel Resolve dell'utente senza collaudo.
