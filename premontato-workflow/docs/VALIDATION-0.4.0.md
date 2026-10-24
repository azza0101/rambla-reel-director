# Premontato 0.4.0 — stato reale

## Integrato
- YuNet 640 CPU, modello ufficiale MIT incluso offline e verificato SHA256. Cache Haar invalidata.
- Voto temporale sui fotogrammi, avanzamento reale per clip, annullamento.
- Allineamento sequenziale di battute complete attraverso segmenti ASR; copertura lessicale visibile e avviso sulle corrispondenze parziali.
- Apertura sul master quando il testo ha copertura comparabile, alternanza fra scale stimate, intervalli riusati esclusi.
- Revisione locale di alternative, In/Out, scala.
- Verifica timeline corretta per timecode assoluti delle camere; richiesta esplicita di timestamp delle parole.

## Verificato
23 test unittest Python nel runtime distribuito; 39 test Node; 9 contratti pacchetto.
Benchmark manuale: 31/31 campioni distinguono master da copertura stretta; non è una misura di accuratezza generale.

## Limiti
Il copione differisce dal recitato, e le trascrizioni Resolve hanno errori. L'allineamento lessicale può trovare una porzione anziché una battuta completa: copertura e parlato trovato servono alla revisione, non certificano un montaggio finito. Nessun riconoscimento identità/attore; nessuna garanzia di raccordo sguardi o sincronismo labiale. Nessun modello semantico o nuova ASR inclusi.
UI Electron completa e revisione manuale interattiva non ancora collaudate nell'host. Multicam e reazioni automatiche non implementati.

## Test reale
Tre file completi: 665 fotogrammi campionati a 2 fps circa, 422 secondi totali di decodifica/analisi. Master wide, due coperture close stimate. Ultimo piano di prova: 10/12 battute, diverse parziali. Timeline tecnica Resolve: 10 video + 10 audio, 1168 frame, tutti gli intervalli esatti; timeline precedente ripristinata. Questo non certifica qualità editoriale né dialoghi completi.
