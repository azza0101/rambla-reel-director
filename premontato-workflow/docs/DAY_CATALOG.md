# Catalogazione giornata — V1 di prova (0.12.0)

## Uso dal pannello

1. Importa le riprese in un bin Resolve, ad esempio Riprese. Le sottocartelle sono incluse; non occorre selezionare le singole clip.
2. Apri Premontato e scegli **Catalogazione giornata · prova**. Carica il PDF con **Scegli copione**.
3. Premi **Leggi cartelle Resolve**, scegli la radice e premi **Cataloga giornata / Riprendi**.
4. Segui stato, cache ed errori clip per clip. Le scene compaiono progressivamente; restano PROVVISORIE finché ci sono sorgenti pendenti/fallite. **Pausa** termina dopo la chiamata Resolve corrente, che non può essere interrotta dal bridge.
5. Apri le scene da verificare: leggi le evidenze e correggi scena e intervallo sorgente [In,Out). Conferma o escludi l’intervallo. Il punteggio è una somiglianza, non una probabilità.
6. Premi **Anteprima organizzazione Media Pool**; poi **Conferma e organizza Media Pool**. Pubblica solo auto_ready/confirmed, anche se il catalogo è provvisorio (dichiarato nell’anteprima).

Risultato: **Premontato - Catalogo Giornata / Giornata_<id> / <ordinale>_<scena> / SELECTS_v0.12.0_<id>**. Sono raccolte di intervalli video/audio delle sorgenti, non il montaggio finale. Una clip può contribuire a più scene. Originali, mapping audio e timeline esistenti non vengono spostati o modificati. Le scene mute/non riconosciute restano senza assegnazione: V1 non inventa copertura.

I checkpoint sono locali in **%APPDATA%/RAMBLA/Premontato/day-catalog/**, separati dai progetti di montaggio. Riapri lo stesso progetto Resolve, lo stesso bin e il copione, quindi Riprendi. Le clip completate non vengono ritrascritte; **Riprova clip fallite** ritenta solo quelle. Modifiche a media/copione invalidano gli input interessati. Se una sorgente è stata rimossa/spostata/ricollegata dopo l’analisi, la pubblicazione viene bloccata.

## Funzionamento

Inventario SDK read-only; GetTranscription e, solo se serve, TranscribeAudio seriale; parser PDF esistente; finestre con tempi delle parole; ancore lessicali e encoder semantico condiviso già distribuito. Contesto/ordine e ripartenze sono evidenze; frasi generiche non bastano. Nessun video decoding, ASD o Groq per catalogare. La regia narrativa e gli inserti V3 della 0.11.11 restano nel flusso Analizza scena.

L’applicazione richiede preview e conferma, SaveProject, verifica ID/fingerprint, journal progressivo, readback cartelle e range video/audio. Un errore di scena non blocca le successive. Al retry si verifica il prefisso esistente prima di completare una SELECTS; una timeline modificata dall’utente non viene sovrascritta. Una correzione che cambia i range crea una nuova SELECTS identificata, preservando la precedente.

## Limiti della prima versione

- Collaudata nativamente su Studio **21.1.0.17**. Altre build/fps/codecs non sono certificati; il readback deve passare prima di dichiarare applicata una scena.
- Fallback SELECTS: bounded-subclip testate soltanto su MP4 sintetico 25 fps, non abilitate in produzione V1. MoveClips provata solo su subclip sintetica e non usata per gli originali.
- Molte assegnazioni del girato reale restano DA VERIFICARE; non è certificata una precisione universale. Nessun gold umano completo disponibile.
- Il pannello è implementato e i comandi sono testati, ma non è stato collaudato visivamente in Electron dopo OFF. Nessuna automazione mouse.
- Se il progetto non aveva una timeline aperta, Resolve può lasciare attiva la nuova SELECTS: non esiste un ripristino affidabile dello stato «nessuna timeline» via API. Con una timeline iniziale, cartella e timeline sono ripristinate e verificate.
- Nessun montaggio globale film, nessun riconoscimento di scene mute, nessuna nuova dipendenza globale. FFmpeg resta il prerequisito preesistente delle analisi audio/video del premontaggio, non della catalogazione.

## Build di prova

Usare l’installer EXE della prerelease dedicata; chiudere il pannello Premontato prima di installare. La build non viene proposta al canale stabile: il tag di prova ha un suffisso escluso dal selettore attuale. I vecchi updater non conoscono i nuovi moduli, quindi questa prima prova si installa con EXE. L’installer preserva i dati utente e copia WorkflowIntegration.node esclusivamente dall’SDK locale; nessuna credenziale di pubblicazione nel pacchetto.

## Test riproducibili

- JavaScript: node --test tests/unit/*.test.cjs
- Python incluso: python tools/run_python_tests.py (unittest più i nove contratti packaging senza pytest).
- Native: tools/create_catalog_smoke_fixtures.ps1 crea soltanto media sintetici in una NUOVA cartella sotto review. Imposta PREMONTATO_PYTHON al runtime incluso e PREMONTATO_SDK_PYTHON al Python che accede all’SDK locale, quindi node tools/day_catalog_native_smoke.cjs <cartella-fixture>. Il test crea un progetto isolato, lo conserva come prova e ripristina quello iniziale. PREMONTATO_PLUGIN_ROOT consente di testare una copia installata isolata.

Dettagli misure e collaudo: performance/2026-10-26-day-catalog-validation.md.

Resolve può quantizzare i tempi con un anticipo di un frame o parole puntuali (start=end). Il catalogatore conserva i dati grezzi, limita il range al media fisicamente disponibile e mantiene il testo; i timing incerti richiedono revisione. Non vengono inventate durate per le parole.
