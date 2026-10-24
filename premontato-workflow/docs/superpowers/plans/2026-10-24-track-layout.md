# Track layout and mono buses

User clarified: change timeline audio track format Stereo -> Mono, without editing media pool clip attributes, source audio mapping or files. Create at most three video tracks and three corresponding audio tracks: V/A1 master-wide blue, V/A2 medium green, V/A3 close/detail orange. Unknown framing stays on V/A1 with Tan warning color, explicitly unclassified. Keep every paced source range at the same record position for paired audio/video; link the pair. No channel splitting, custom downmix or source mutation.

- [x] Write failing native adapter tests for 3-track placement, mono track reset, source timecodes, colors, links, rollback and no source mutation.
- [x] Replace unpositioned append with explicit video/audio appends and recordFrame; configure only the newly created empty timeline. Verify actual tracks/items/colors/positions/mono and restore original timeline on success/failure.
- [x] Add panel legend and returned layout stats. Verify unit suites and controlled SDK tests; native Resolve scripting became available; full JavaScript adapter verified on a disposable timeline with 9 synchronized AV ranges and source mappings unchanged.
- [ ] Package and publish isolated Premontato release without merge/latest promotion.

## VIDEO COLICHE — estensione richiesta dall’autore

Memoria editoriale in docs/styles/VIDEO_COLICHE.md. Pannello Regia con note opzionali .txt/.md e marcatori per battuta: tensione, risoluzione, libero. Solo i marcatori vengono interpretati dal selettore locale: preferisce close finché la tensione non termina, wide sulla risoluzione, senza forzare candidati meno affidabili o persone confermate assenti. Conserva pause in tensione salvo override manuale. Segnala la copertura mancante. Non crea inserti di reazione da note testuali. Progetti e autosave conservano profilo, note, marcatori e bozze. Verifiche: selezione worker, pausa, roundtrip progetto, test browser con worker reale.
