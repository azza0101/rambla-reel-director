# KURA paper title v8 — audit statico, 2 ottobre 2026

## Fonte e limiti
- Pacchetto letto: backend/assets/resolve_titles/KURA_paper_title_v8.drfx, dal commit 67a037d7f48fd2d5a53fa51baca915def42419f4.
- Blob Git: 9f3d5dffdf5fb1ebdf1ceab4f3126deb6e5b1a49. Dimensione: 4.623.692 byte.
- SHA256 dei byte: cb56bfd056ddd9f4332eade6da712a9456cfcd0fa63a6abfa86896e14e0ac0d1.
- Archivio ZIP valido: controllo CRC di tutti i file superato. File setting: Edit/Titles/KURA_paper_title_v8/KURA_paper_title_v8.setting, 1.618 righe.
- Analisi delle connessioni, dei valori salvati e delle immagini del pacchetto. Nessun render di DaVinci Resolve eseguito e nessuna misura degli FPS della macchina dell'utente.
- Il branch operativo e il pacchetto originale non sono stati modificati. Questo documento appartiene soltanto al branch di analisi.

## Inventario verificato
- 65 operatori/modificatori interni, esclusi il contenitore principale e il sottogruppo Paper_Text_1_1. Non equivale a 65 operatori renderizzati per frame.
- 5 Loader, 2 TextPlus, 10 Merge, 5 Background, 7 Transform Fusion, 3 TimeStretcher, 3 Dissolve, 3 BrightnessContrast, 2 ColorCorrector, 2 ErodeDilate, 1 Displace, 1 FastNoise, 1 UltraKeyer.
- 4 operatori OFX: Color_Back (ColorGeneratorPlugin), Transform2 (ResolveFX Transform), DropShadow2 e DropShadow1_1_1 (ResolveFX DropShadow).
- Altri operatori/modificatori: 2 PipeRouter, 1 RectangleMask, 1 EllipseMask, 3 LUTLookup, 3 LUTBezier, 1 Offset, 2 Calculation, 3 PerturbNumber.
- 34 PNG nelle quattro sequenze: Center e Center mask, 9 frame ciascuna; Rect e Rect mask, 8 frame ciascuna. Center: 1920x1920; Rect: 1920x1080. paper.jpg: 1920x1280. Presente inoltre una thumbnail 426x240.
- La thumbnail e i commenti/controlli LLmotion sono coerenti con un effetto generico di paper unfolding adattato successivamente a un titolo.

## Connessioni e valori rilevanti (righe del setting originale)
- Output principale: DropShadow2.Output (266–269).
- Template è il TextPlus del testo visibile, con Montserrat / Black, testo bianco RGBA 1, Size 0.1401, CharacterSpacing 0.975, LineSpacing 0.828, UseFrameFormatSettings=1 (393–415).
- ErodeDilateGSFix_1_1 usa XAmount=-0.001; ErodeDilate2_1_1 usa XAmount=0.01555. Sono concatenati a partire dal ramo del testo (741–773).
- Displace2_1_1 riceve mgPapText_1_1 e FastNoise2_1_1; usa il ramo del testo come maschera invertita, Offset=-0.5, RefractionStrength=0.2 (1057–1077).
- FastNoise2_1_1 ha Detail=10, XScale=5.67, Seethe=1.123 senza animazione salvata, Discontinuous=1 e Inverted=1; usa UseFrameFormatSettings=1 (1078–1092). Il suo costo continuativo va misurato: non è corretto descriverlo come noise animato a ogni frame.
- bgResFix_1_1 e Instance_bgResFix_1_1 impostano sia Width sia Height a max(bgTimeline_1_1.Width,bgTimeline_1_1.Height), quindi producono canvas quadrati (1093–1109 e 1180–1224). A 1080x1920 il canvas quadrato teorico è 1920x1920: 1.778 volte i pixel, NON una misura di rallentamento.
- Color_Back è un ColorGenerator OFX, mascherato dal ramo carta; Merge_Color combina con Multiply. Colore salvato RGB=(0.156862745098,0.4,0.047058823529), corrispondente a #28660c (807–833,1126–1142).
- Catena finale: mgPaperBorder_1_1 → xfShakeIN_1_1 → xfShake_1_1 → xfGLOBAL_1_1 → Transform2 → DropShadow2. Transform2 ha solo posY=0.025 non neutro fra i controlli geometrici principali; zoom/scale=1, rotate/pitch/yaw/crop=0, motionBlur=0 (1225–1460).
- DropShadow2 è realmente sull'output: shadowStrength=0.5, shadowAngle=80, ShadowDistance=0.0142, shadowBlur=0.354 (1363–1390).
- DropShadow1_1_1 e Text1_1_1 non sono referenziati dal percorso finale, nemmeno tramite le espressioni degli altri operatori. Il sottogruppo Paper_Text_1_1 contiene invece nodi usati: non va eliminato come se fosse vuoto.
- Instance_paper_CC_1_1 eredita parametri da paper_CC_1_1 ma sovrascrive Input con desat_1_1. Una SourceOp di istanza non implica che l'immagine dell'operatore master sia necessariamente renderizzata (681–726).

## Temporizzazione e doppio movimento
- LL_1_1.SourceTime = LL_1_1.UnfoldAmount; UnfoldAmount=4. Nel preset salvato il ramo unfolding campiona un tempo fisso, non un'apertura completa (868–897).
- LL_R_1_1.Anim ha espressione costante 1; AnimFF risulta quindi 0. ACmaxR_1_1 usa una curva con valore 1 a entrambi gli estremi e Scale=20 (898–1010).
- Rrandom usa MaxR - 2*random()*MaxR con seed variabile per step temporale, ed entra in xfShakeIN_1_1.Angle tramite Calculation2_1_1 (898–1010,1225–1275). Questo è distinto dal wiggle esposto.
- I controlli esposti Wiggle X/Y/Angle agiscono sui tre PerturbNumber che alimentano xfShake_1_1, non sulla rotazione precedente di xfShakeIN_1_1 (149–238,1305–1362).
- Wiggle Posterize=3 campiona i controlli del secondo sistema ogni 3 frame. Non è di per sé uno switch OFF né una garanzia di render a un terzo del costo.
- Nessun motion blur attivo è esplicitamente salvato nel grafo; Transform2 lo dichiara spento. Le impostazioni effettive della composizione installata restano da verificare.

## Priorità proposte, non benchmark
1. Misurare separatamente DropShadow2, Transform2, Displace2_1_1 e i due ErodeDilate, con stessa frase, risoluzione e cache controllata.
2. Conservare il TextPlus Template e i suoi controlli. Eliminare dal percorso testo il supporto generico a media/green-screen non richiesto, dopo confronto visivo.
3. Sostituire Transform2 con una trasformazione Fusion equivalente; confrontare campionamento, alpha e posizionamento. Non assumere una corrispondenza diretta dei valori numerici tra OFX e Fusion.
4. Precalcolare le uscite realmente statiche delle maschere unfolding e, se utile, la mappa FastNoise. Non sostituire la carta con un rettangolo generico.
5. Limitare l'area elaborata da bordo/ombra e preferire lavorazioni sull'alpha dove equivalenti. Verificare il Domain of Definition reale, non solo Width/Height.
6. Unificare i controlli del movimento o separare chiaramente movimento originale e wiggle aggiuntivo. Spostare l'ombra prima della rotazione cambia la direzione relativa: non è un'ottimizzazione visivamente neutra.
7. Nessun guadagno FPS dichiarato prima di prove reali; nodi disconnessi, cache e concatenazione delle trasformazioni impediscono di dedurre le prestazioni dal solo conteggio.
