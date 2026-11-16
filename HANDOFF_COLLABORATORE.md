# RAMBLA video tools — guida per collaboratori e agenti

**Fotografia del 16 novembre 2026.** Questa guida è un punto di partenza per una persona o un agente che debba studiare, installare o sviluppare gli strumenti RAMBLA. Il repository è privato: chi lo usa deve avere accesso autorizzato, comprese le release. Non contiene i video dei clienti, le sessioni browser o le chiavi API.

> **Prima di tutto:** non prendere `main` come versione completa del prodotto. I prodotti sono su rami e tag distinti. Non fare merge, aggiornamenti incrociati o modifiche alle timeline di lavoro senza accordo esplicito. Una funzione proposta dall'AI va sempre revisionata: esistenza del codice o un test passato non garantiscono la qualità del montaggio.

## Indice

1. [Mappa delle versioni](#mappa-delle-versioni)
2. [Architettura e flussi](#architettura-e-flussi)
3. [RMBL B ROLL](#rmbl-b-roll)
4. [Auto-Cut per Resolve](#auto-cut-per-resolve)
5. [Omni-Cut](#omni-cut)
6. [Stile KURA e Editing Brain](#stile-kura-e-editing-brain)
7. [Installazione e aggiornamenti](#installazione-e-aggiornamenti)
8. [Diagnosi e test](#diagnosi-e-test)
9. [Questioni aperte e prossimi passi](#questioni-aperte-e-prossimi-passi)
10. [Regole per un agente](#regole-per-un-agente)

## Mappa delle versioni

| Prodotto | Release pubblicata verificata | Codice da studiare | Stato |
|---|---|---|---|
| RMBL B ROLL + bridge | [v0165](https://github.com/azza0101/rambla-reel-director/releases/tag/v0165), 12 novembre | [sorgente v0165](https://github.com/azza0101/rambla-reel-director/tree/v0165), commit `3d8555c5a0ef1fcd8482e67e5ee2c230ec82fe03` | Release non prerelease. ZIP di aggiornamento; l'EXE più recente verificato è nella [v0161](https://github.com/azza0101/rambla-reel-director/releases/tag/v0161). |
| Auto-Cut workflow | [autocut-v0.1.11](https://github.com/azza0101/rambla-reel-director/releases/tag/autocut-v0.1.11) | [sorgente Auto-Cut](https://github.com/azza0101/rambla-reel-director/tree/autocut-v0.1.11), commit `3e949278c3f1a92b906ed2c34eeb3f3e8f123fd5` | Prerelease; ZIP di aggiornamento, non un EXE in questa release. |
| Omni-Cut test | [omnicut-test-v0.2.30](https://github.com/azza0101/rambla-reel-director/releases/tag/omnicut-test-v0.2.30) | [sorgente Omni-Cut](https://github.com/azza0101/rambla-reel-director/tree/omnicut-test-v0.2.30/premontato-workflow), commit `6779f912542f3f57d7fbaca14f28bf4298b8edf7` | Prerelease sperimentale; questa release contiene ZIP e manifest, non EXE. |

I tag e gli hash identificano ciò che è stato pubblicato, non la versione effettivamente installata su ogni computer. Leggere la versione nella finestra e verificare la release. Il ramo `main`, al commit `cff30a4cdce3b03e50a821122b51e66ea33e0561` al momento della rilevazione, contiene soprattutto la documentazione iniziale; è divergente dal ramo della release RMBL. **Non sostituire una release con main e non presumere che un merge sia già stato fatto.**

I canali di aggiornamento rimangono separati: `vNNNN` per RMBL, `autocut-v…` e `omnicut-test-v…`. Il canale storico `premontato-v…` non è un prodotto di riferimento per il lavoro corrente e non deve diventare la release latest dell'intero repository. L'updater di un prodotto non deve installare un pacchetto di un altro.

## Architettura e flussi

```text
Video/file o timeline Resolve
          |
          +--> RMBL B ROLL: trascrizione -> CUT opzionale -> piano -> ricerca
          |       -> selezione -> ZIP/DRA sperimentale oppure pacchetto bridge
          |                                                     |
          |                                          APPLICA esplicito in Resolve
          |
          +--> Auto-Cut workflow: revisione testuale e pause -> applicazione esplicita
          |
          +--> Omni-Cut: copione + girato + analisi -> proposta
                  -> revisione -> creazione timeline / organizzazione Media Pool
```

- **RMBL** è un'app Python con backend locale e interfaccia web; il **bridge** è il componente Resolve separato che riceve un pacchetto e opera solo dopo conferma. Il prodotto non richiede Codex o un server MCP per funzionare.
- **Auto-Cut** e **Omni-Cut test** sono integrazioni Workflow di Resolve; non sono filtri OFX/DFRX generici. Hanno installazioni e canali di aggiornamento indipendenti.
- Elaborazione locale non significa sempre gratuita o offline: RMBL può inviare audio/testo e query ai servizi configurati; le funzioni visive cloud eventualmente abilitate inviano immagini o fotogrammi. I servizi impongono quote e condizioni proprie. L'uso di Codex per lo sviluppo è distinto dal costo del prodotto in esecuzione.
- Le operazioni di Resolve dipendono dall'API ufficiale disponibile nella specifica installazione. I test storici citano Resolve Studio 21.1. Non assumere che ogni funzione funzioni su Free o macOS: verificare versione, edizione, sistema, scripting e un progetto di prova. Nessuna modifica a un progetto cliente durante un collaudo.

## RMBL B ROLL

### Percorso utente

1. **Source:** scegliere il video originale o usare la sorgente/timeline dal bridge. Il video originale deve rimanere distinguibile dall'anteprima tagliata.
2. **Analysis:** trascrizione con tempi e dati necessari. Verificare lingua, parole e tempi prima di fidarsi dell'output.
3. **Auto-Cut:** propone ripartenze, take alternative ed errori di regia; il testo permette esclusione/ripristino, scelta alternativa, undo/redo e revisione. Le pause sono un'operazione opzionale con preset; controllare i confini delle parole. L'anteprima e il file CUT non sostituiscono la sorgente.
4. **Transcript review / piano editoriale:** revisione della trascrizione, selezione delle frasi da coprire e delle locuzioni complete da evidenziare, mantenendo i riferimenti temporali.
5. **Find media / Visual beats:** ricerche e scelta di più alternative per frase, visualizzazione fonti e ricerca personalizzata. Fonti previste comprendono Pexels, Envato, YouTube/Shorts, TikTok, Instagram e immagini, a seconda di accessi e disponibilità. Anteprima non equivale a un file finale scaricabile né a una licenza.
6. **Coperture generiche e luogo:** ricerche aggiuntive e selezioni da usare come materiale di supporto. Il contesto del luogo deve restare coerente; verificare sempre pertinenza e diritti.
7. **Export timeline:** selezionare solo i componenti necessari: CUT nativo oppure originale con audio, sottotitoli, parole evidenziate, B-roll/immagini, clip social e generiche. Controllare i conteggi dopo aver modificato le scelte.

**MAGICO** orchestra la preparazione con budget e avanzamento: CUT, piano, ricerca, selezione e pacchetto; conserva checkpoint e permette di riprendere. La selezione è una proposta, non una certificazione della qualità: controllare ripetizioni, regia, coperture, località, crop, testi e media assenti. Le operazioni incrementali cercano di aggiornare le parti modificate, ma vanno controllate quando cambia il CUT. L'applicazione in Resolve rimane una scelta esplicita.

### Consegna e qualità media

- Il bridge può ricevere un pacchetto per timeline attiva o nuova, con componenti selezionati. I titoli evidenziati vanno tenuti come clip individuali modificabili; coperture alternative possono richiedere più tracce video. Verificare sempre risultato, allineamento e collegamenti nel progetto effettivo.
- Lo ZIP senza bridge può raccogliere media e metadati; il percorso **DRA offline** è sperimentale e genera struttura/progetto senza Resolve usando codice vendorizzato. Non confondere questo con un archivio esportato dall'API ufficiale di Resolve. Testare import, relink, sottotitoli, Text+, effetto, audio e tracce sulla versione Resolve del destinatario. Se un formato non è supportato il percorso deve dichiararlo, non riferire un successo vuoto.
- Il controllo finale video richiede almeno **720 pixel sul lato corto**. Una clip non verificabile o troppo piccola deve produrre un avviso e una scelta esplicita: riprovare, annullare oppure continuare senza le clip indicate. Non usare un'anteprima a bassa qualità come media finale e non spacciare un upscaling per HD.
- La selezione Envato privilegia 1080 quando disponibile. I download nuovi superiori al limite possono essere convertiti in H.264 fino a 1080; se rientrano già nel limite la funzione di normalizzazione può mantenere la sorgente e il codec. **Questo non garantisce che ogni codec sia supportato dal DRA offline**: controllare il messaggio di compatibilità e il risultato su Resolve.
- La conversione leggera usa `-fps_mode passthrough` e verifica FPS, numero e tempi dei fotogrammi; la sorgente non viene eliminata dalla funzione di conversione. Un FPS variabile o non verificabile può impedire alcuni export CUT/DRA: non forzare un frame rate diverso per aggirare il controllo. Il fatto che una timeline abbia FPS propri non autorizza a modificare i FPS dei file sorgenti.
- Su ricerca/download possono intervenire login, CAPTCHA, licenze, limiti del provider o cambi del sito. Anche un risultato selezionato può non essere effettivamente scaricabile. Leggere gli errori e verificare i file reali, non solo le miniature.

### Dove leggere il codice

Link fissati alla release: [README e installazione](https://github.com/azza0101/rambla-reel-director/blob/v0165/README.md), [storico handoff](https://github.com/azza0101/rambla-reel-director/blob/v0165/docs/HANDOFF.md), [backend/app](https://github.com/azza0101/rambla-reel-director/tree/v0165/backend/app), [bridge](https://github.com/azza0101/rambla-reel-director/tree/v0165/tools/resolve_bridge), [test](https://github.com/azza0101/rambla-reel-director/tree/v0165/tests/unit).

Moduli utili: `curation_server.py`, `curation_ui_v2.py`, `cut_pass*.py`, `magic_*.py`, `media_pack_export.py`, `offline_resolve_archive.py`, `media_export_quality.py`, `envato_light_media.py`, `resolve_handoff*.py`, `resolve_bridge.py`, `omnicut_handoff.py`. Ricontrollare nomi e contratti sul tag scelto prima di intervenire.

## Auto-Cut per Resolve

Workflow separato dal bridge RMBL: prende la sorgente dalla timeline supportata, usa trascrizione temporizzata e analisi take, mostra testo e scarti, permette revisioni e rimozione opzionale delle pause, quindi propone l'applicazione in una timeline nuova o attuale. Nelle iterazioni sono stati trattati IN/OUT, applicazione successiva, sottotitoli e backup: verificare l'effettivo comportamento della versione installata prima di lavorare su un progetto reale.

La preferenza dell'utente è preservare sorgenti modificabili e non accumulare timeline di backup. Spostamento non distruttivo di tracce complesse e Fusion **non va dato per universalmente garantito**: le possibilità dell'API Resolve sono limitate. Evitare automazione di mouse/tastiera senza consenso e non affermare che un compound conservi clip separatamente modificabili.

L'analisi di take/note di regia e la stima dei tempi sono euristiche, anche quando usa Groq. Volume più basso può essere un indizio, non la prova di una nota di regia. Revisionare l'ultima take completa, parole tronche e timestamp anomali. Il pulsante di aggiornamento ha un canale proprio. Riferimenti: [moduli backend](https://github.com/azza0101/rambla-reel-director/tree/autocut-v0.1.11/backend/app), [integrazione Resolve](https://github.com/azza0101/rambla-reel-director/tree/autocut-v0.1.11/tools/autocut_integration), [test Auto-Cut](https://github.com/azza0101/rambla-reel-director/tree/autocut-v0.1.11/tests/unit).

## Omni-Cut

**Omni-Cut test è il prodotto di riferimento per il premontaggio:** parte da copione, girato e trascrizioni, propone take, inquadrature e reazioni, e prepara una timeline da revisionare. Può catalogare clip intere per scena o come dettagli/B-roll, usando trascrizioni e, se configurato, confronto visivo locale Qwen; lo spostamento nel Media Pool richiede un'azione esplicita. Catalogare clip intere e montare intervalli in timeline sono operazioni diverse.

Il motore comprende analisi locali di volti, inquadrature e parlante; l'identità e le decisioni incerte vanno revisionate. Per il piano può usare provider configurati come Groq oppure Gemma locale opzionale: controllare le impostazioni e l'eventuale invio dei dati. Alcuni modelli e ambienti opzionali non sono inclusi nel pacchetto e vanno predisposti separatamente. La destinazione documentata è Windows x64 / Resolve Studio; non presentare macOS o multicamera come pienamente supportati senza test mirato.

**Limiti noti:** la v0.2.30 non monta ancora automaticamente le scene mute catalogate e non riconosce in modo generale lo stato degli oggetti. La prova documentata di questa versione non comprende una nuova timeline nativa; occorre verificare su Resolve con una scena di prova prima dell'uso produttivo. L'integrazione RMBL/Omni-Cut comprende preparazione di metadati; non presumere che sia già un montaggio completo senza verificare il contratto di entrambe le versioni.

**Nota sul codice storico:** Omni-Cut deriva dal progetto Premontato e il suo sorgente è tuttora nella cartella `premontato-workflow`. I vecchi tag e installer restano come storico, non come prodotto da installare per il flusso corrente. La discendenza dei commit non dimostra da sola che tutte le funzioni precedenti siano rimaste identiche: eventuale migrazione di lavori esistenti va testata, perché progetti e autosave sono separati.

Leggere: [Omni-Cut: installazione e limiti](https://github.com/azza0101/rambla-reel-director/blob/omnicut-test-v0.2.30/premontato-workflow/docs/OMNICUT_TEST.md), [catalogazione visiva](https://github.com/azza0101/rambla-reel-director/blob/omnicut-test-v0.2.30/premontato-workflow/docs/OMNICUT_VISUAL_CATALOG.md), [montaggio automatico](https://github.com/azza0101/rambla-reel-director/blob/omnicut-test-v0.2.30/premontato-workflow/docs/AUTOMATIC_EDIT_FLOW.md), [release 0.2.30](https://github.com/azza0101/rambla-reel-director/releases/tag/omnicut-test-v0.2.30).

## Stile KURA e Editing Brain

Il **Brain** è una memoria di lavoro separata per cliente, attualmente locale e non automaticamente distribuita. I materiali di riferimento e i dati cliente non vanno pubblicati senza un'azione autorizzata. Il profilo KURA è iniziale e deriva da una reference, non da una regola universale.

Preferenze già espresse: coperture pertinenti al significato e a luoghi riconoscibili; ritmo legato alla voce; soggetto sempre leggibile e continuità dei punti di attenzione nei cambi rapidi; provare a ricentrare una buona clip prima di scartarla; alternative editabili; locuzioni complete evidenziate, eventualmente su due righe. Mantenere la persona in camera quando utile alla narrazione. Effetti sonori e musica richiedono ascolto e verifica: una classificazione automatica è solo un indizio.

Il preset KURA v9 e l'effetto ottimizzato sono percorsi distinti. L'effetto ottimizzato applicato a Text+ non imposta necessariamente il font del testo: impostare font e impaginazione nel Text+ e verificare che preset e font siano installati sul computer destinatario. Controllare resa e prestazioni in Resolve, soprattutto nei pacchetti offline.

## Installazione e aggiornamenti

### RMBL su Windows

1. Con accesso al repository privato, scaricare l'EXE dalla [release v0161](https://github.com/azza0101/rambla-reel-director/releases/tag/v0161), oppure lo ZIP e l'installer manuale dalla [v0165](https://github.com/azza0101/rambla-reel-director/releases/tag/v0165). La v0165 non contiene un EXE separato.
2. Seguire il [README v0165](https://github.com/azza0101/rambla-reel-director/blob/v0165/README.md): l'EXE crea un ambiente Python isolato e può richiedere Python/winget. Lo ZIP prevede `INSTALL_RMBL_B_ROLL.cmd`. Il setup registra anche il bridge; la configurazione può richiedere riaprire Resolve.
3. Configurare **localmente** soltanto le credenziali necessarie, senza inserirle nel codice o nella chat. Il README indica `cloud.env.example` / `.env.local`, Groq e Pexels e, se usati, Gemini e Google. I profili/autenticazioni dei provider vanno configurati sul nuovo PC. I pacchetti pubblici della release non devono contenere token o dati personali.
4. Aprire RMBL e in Resolve un progetto **e una timeline**, poi il bridge da `Workspace → Scripts → RAMBLA_B_ROLL` secondo l'installazione. L'accesso e le impostazioni scripting dipendono dalla versione/edizione di Resolve.
5. Per un'installazione v0161, cercare l'aggiornamento RMBL a v0165 con **Search Update**, verificando versione e conferma. Su repository privato anche il downloader deve avere un accesso autorizzato. Non assumere che l'updater funzioni su un PC mai collaudato: controllare il risultato e mantenere un rollback.

L'aggiornamento è progettato per conservare progetti, cache, configurazioni e profili locali; fare comunque un backup prima delle prove su una macchina nuova. I dati locali non viaggiano con il codice Git. Le release e le installazioni effettive possono evolvere dopo la data di questa guida.

### Pannelli Workflow

- **Auto-Cut:** installatori e sorgente nel [tag dedicato](https://github.com/azza0101/rambla-reel-director/tree/autocut-v0.1.11), inclusi script Windows/macOS; il pacchetto della release v0.1.11 è un update ZIP. Il supporto macOS va verificato su un Mac reale.
- **Omni-Cut test:** [release v0.2.30](https://github.com/azza0101/rambla-reel-director/releases/tag/omnicut-test-v0.2.30) contiene ZIP e manifest; la documentazione descrive anche la costruzione di un EXE, ma non dichiararlo presente in questa release. Verificare il procedimento di prima installazione sul computer target prima di promettere un setup a un clic. Il `WorkflowIntegration.node` ufficiale deve provenire dalla propria installazione/SDK Resolve.

## Diagnosi e test

### Bridge

`bridge connected` può indicare soltanto che il processo bridge ha fatto heartbeat: non prova che Resolve sia raggiungibile o che una timeline sia aperta. Nel debug leggere anche progetto, timeline, ID, pacchetto, stato e build. Un pacchetto `pending` con `bridge_received_at` nullo non è stato ricevuto. Se il programma e il bridge usano server/porte diversi, non si incontrano. Se ci sono più processi Resolve, l'API può collegarsi a un'istanza senza timeline: controllare i processi e non chiuderli alla cieca.

```powershell
foreach ($p in 8810..8819) {
    try {
        $base = "http://127.0.0.1:$p"
        $h = Invoke-RestMethod "$base/health" -TimeoutSec 2
        $b = Invoke-RestMethod "$base/api/curation/resolve-bridge/session" -TimeoutSec 2
        [PSCustomObject]@{ Porta=$p; Build=$h.build_token; PIDServer=$h.server_pid; Bridge=$b.connected }
    } catch { }
}
Get-Process Resolve -ErrorAction SilentlyContinue | Select-Object Id,StartTime,MainWindowTitle
```

Le risposte degli endpoint possono cambiare tra versioni: confrontare con l'implementazione installata. Non pubblicare log grezzi contenenti percorsi, trascrizioni, dati personali o credenziali. Se è disponibile l'assistenza diagnostica, controllare l'anteprima e il consenso prima dell'invio.

### Test mirati

Da una copia del tag RMBL con dipendenze di sviluppo installate, ad esempio:

```powershell
python -m pytest tests/unit/test_original_fps_export.py tests/unit/test_final_media_quality.py tests/unit/test_export_quality_popup.py tests/unit/test_offline_resolve_archive.py tests/unit/test_offline_pack_selection.py -q
```

I test unitari non sostituiscono un vero import Resolve. Su Windows scegliere una directory temporanea scrivibile se `pytest` non riesce a creare `tmp_path`; non cancellare cache o progetti dell'utente per farlo. Per cambi a testi, tracce o ponte servono anche test mirati e una timeline dedicata. Per Omni-Cut consultare i test e i documenti del **tag** specifico; i conteggi di test storici in handoff precedenti non certificano la suite attuale.

**Verifica della presente guida, 16 novembre 2026:** sul codice locale corrispondente ai file chiave della release v0165, gli 11 test di `test_original_fps_export.py` sono passati, inclusi 25, 30000/1001 e 60000/1001 fps, rifiuto VFR e controllo della cadenza. Il primo avvio della suite più ampia ha incontrato un errore di creazione della directory temporanea del sandbox; riprovata con temporanei nel workspace, l'esecuzione complessiva è stata interrotta e non viene dichiarata superata. Nessun test live in Resolve è stato eseguito per questo handoff.

## Questioni aperte e prossimi passi

1. **Installazione pulita:** collaudare ogni prodotto separatamente sul PC del collaboratore, con versione Resolve, SDK, accessi, aggiornamento, rollback e media reali. Nessuna affermazione di compatibilità universale Windows/macOS/Free.
2. **Qualità e FPS:** confrontare sorgenti e media nel pacchetto finale con `ffprobe`, inclusi orientamento, dimensioni, codec, `r_frame_rate`, `avg_frame_rate`, numero e tempi fotogrammi. Provare sia CFR sia VFR. Rendere espliciti gli errori; non riconvertire FPS.
3. **DRA offline:** verificare su più sistemi importazione e relink, audio, nomi coincidenti, immagini, tracce multiple e Text+/effetto installabile. È sperimentale, non una garanzia di compatibilità con ogni codec o versione Resolve.
4. **Qualità editoriale:** testare su video diversi ripartenze, tagli di regia, timestamp, pause e rilevanza visiva; verificare manualmente crop e distribuzione. Gli esempi corretti precedenti non dimostrano accuratezza universale.
5. **RMBL ↔ Omni-Cut:** definire e collaudare contratto versionato di metadati, percorsi portabili, tempi sorgente e timeline, licenze, alternative e correzioni manuali. Non confondere metadati già preparati con un'integrazione di montaggio completa.
6. **Stile/audio KURA:** raccogliere altre reference e ascoltare gli effetti sonori; conservare differenze tra osservazione, preferenza dichiarata e ipotesi. Non pubblicare i materiali dei clienti nel repository.
7. **Rami e release:** decidere con il proprietario una strategia di integrazione; confrontare history e prodotti prima di qualsiasi merge. Non sovrascrivere rami o canali di rilascio.

## Regole per un agente

- Leggere `AGENTS.md` e le istruzioni specifiche della cartella e del ramo, poi il codice e i test della versione effettiva. Le istruzioni esplicite dell'utente prevalgono sui piani storici obsoleti.
- In questo ambiente, **OFF interrompe subito l'automazione del computer**: chiudere/rilasciare la sessione e non inviare altri input finché l'utente non autorizza esplicitamente la ripresa. Il lavoro su file senza controllo UI può continuare se non sospeso.
- Non caricare token, `.env`, sessioni browser, video, cache, modelli o log privati. Non stampare credenziali. Non inviare audio, testo, immagini o query a servizi esterni senza rispettare le autorizzazioni e la configurazione dell'utente.
- Prima di modificare Resolve: lavorare su progetto/timeline di prova, identificare progetto e timeline, salvare e assicurarsi che le operazioni siano autorizzate; non applicare automaticamente un pacchetto. Non interrompere Resolve o cancellare dati per risolvere un problema senza verifiche.
- Distinguere osservato, test automatico, test live, ipotesi e non verificato. Registrare versione, commit, input, esito e limiti. I conteggi di test non sono una valutazione di gusto o qualità editoriale.
- Per il repository privato su Windows controllare prima `gh auth status` e i permessi del repository; il fatto che un connettore non esponga le release non implica che GitHub CLI non sia autenticata. Non creare o incorporare token privilegiati nell'installer. Non fare merge senza approvazione.
