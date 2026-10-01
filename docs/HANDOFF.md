# RMBL B ROLL — handoff tecnico

Aggiornato: 2026-10-01  
Versione: `v0032`  
Branch di consegna: `feat/curation-ui-v1`

## Avvio rapido

- App: `RMBL_B_ROLL_APP.vbs` oppure `python launch_local_v5.py start`.
- Bridge Resolve: `Workspace → Scripts → RAMBLA_B_ROLL`.
- Backend: `backend/app/curation_server.py`.
- UI prodotto: `backend/app/curation_ui_v2.py`, con moduli UI separati per trascrizione, visual beat ed export.
- Bridge nativo: `tools/resolve_bridge/standalone_bridge.py`.
- Versione unica app/bridge: `RAMBLA_VERSION`.

## Flusso Resolve

1. Il bridge mantiene un heartbeat con il backend locale e rileva la timeline focalizzata.
2. **USA AUDIO IN RMBL B ROLL** invia audio e intervalli video esistenti; l'audio può essere riutilizzato solo se la firma della timeline coincide.
3. L'app prepara un handoff senza modificare Resolve.
4. Il bridge riceve il pacchetto nella stessa sessione, si espande e abilita **APPLICA**.
5. L'utente sceglie nuova timeline o timeline attiva con backup TEMP e conferma.

Il bridge espone anche **RICALCOLA AUDIO · IN → OUT**: invia `force_recalculate=true`, impedisce il riuso della guida precedente e renderizza il range IN/OUT letto dalla timeline focalizzata in quel momento. Resolve 21 restituisce i mark relativi all'inizio timeline e può omettere `in` quando coincide con l'inizio: `timeline_range()` normalizza entrambi i casi in frame assoluti. Il ricalcolo forzato rifiuta di partire se non vede almeno un range esplicito, evitando il fallback silenzioso all'intera timeline. Il riepilogo mostra `mark_in`, `mark_out` e `range_source` realmente acquisiti.

La timeline sorgente resta protetta. Le mutazioni Resolve passano dai job di `resolve_handoff_jobs.py`; i calcoli temporali usano FPS e frame iniziale della timeline acquisita.

## Branding

- `backend/assets/branding/rmbl_wordmark_white.png`: marchio orizzontale originale fornito dall'utente.
- `backend/assets/branding/rmbl_mark_white.png`: simbolo originale usato come icona app/finestra.
- `backend/assets/branding/rmbl_bridge_mark.svg`: variante del simbolo RMBL con un ponte sovrapposto; è usata esclusivamente dal bridge.

## Distribuzione

- `INSTALL_RMBL_B_ROLL.cmd` è l'ingresso a un clic.
- `INSTALL_RMBL_B_ROLL.ps1` installa app, dipendenze, shortcut e bridge.
- `INSTALL_RESOLVE_BRIDGE.ps1` può aggiornare soltanto il bridge.
- `BUILD_WINDOWS_PACKAGE.ps1` genera lo ZIP trasferibile senza dati privati.
- `BUILD_WINDOWS_INSTALLER.ps1` avvolge ZIP e bootstrap in un solo `RMBL-B-ROLL-Setup-vXXXX.exe` tramite IExpress.
- Gli aggiornamenti rilevano la versione installata, chiedono conferma e mantengono `rambla-data`, profili browser, progetti e configurazioni locali. Il registro di sicurezza e in `%LOCALAPPDATA%\RMBL B ROLL\install-backups`.
- `RMBL_B_ROLL_APP.vbs` è il launcher app senza bridge.

## Browser e accessi esterni

- I pulsanti di accesso TikTok, Instagram ed Envato aprono una nuova finestra nella sessione e nel profilo Google Chrome attualmente usati dall'utente.
- **SCARICA DA ENVATO** apre allo stesso modo la pagina dell'asset in Chrome e continua a monitorare il download ufficiale.
- Il comando Chrome usa `--profile-directory=<ultimo profilo>` e `--new-window`, senza creare un profilo RMBL separato e senza passare da Edge.

## Navigazione guidata

- Le sezioni numerate 1–7 partono chiuse.
- L'app apre automaticamente una sola sezione: il primo passaggio ancora da completare.
- Ogni intestazione resta cliccabile per aprire o richiudere manualmente la sezione.
- In modifica trascrizione, **ANNULLA MODIFICHE** e **SALVA MODIFICHE TESTO** sono affiancati sotto il box, allineati a destra; **MODIFICA TESTO** resta disponibile sotto la trascrizione in modalità normale.

## Tema grafico

- Il canvas predefinito di `v0028` è verde acqua scuro e solido, senza il precedente gradiente marcato.
- Il pannello finale **⚙ IMPOSTAZIONI GRAFICHE** controlla live canvas e sezioni 1–7, ciascuno in modalità solida o gradiente.
- `GET/PUT /api/curation/theme-preferences` valida soltanto colori esadecimali e persiste in `rambla-data/theme-preferences.json`.
- Il file resta fuori dai progetti e viene conservato dall'installer durante ogni aggiornamento.

## Dati locali esclusi dal repository

Non pubblicare `.env.local`, `rambla-data`, profili browser, progetti cliente, media scaricati, cache, log, render, pacchetti DRA/XML di prova o cartelle `.test-*`. Le chiavi provider rimangono locali.

## Verifica

Prima di dichiarare una modifica pronta:

```powershell
$env:TEMP=(Resolve-Path '..\rambla-data').Path
$env:TMP=$env:TEMP
& '..\editorial-intelligence-worktree\.venv\Scripts\python.exe' -m pytest -q -p no:cacheprovider
```

Il vincolo di sviluppo resta `resolve_calls=0`: i test non devono modificare una timeline reale. Per prove reali su EGITTO serve l'azione esplicita dell'utente nel bridge.

### Stato suite al passaggio v0032

I test focalizzati sulla disposizione dei comandi di modifica testo, UI, tema e versione passano (`47 passed`). La batteria precedente su ricalcolo audio IN/OUT, normalizzazione dei mark Resolve 21, cache, bridge standalone e distribuzione Windows passa (`71 passed`). Il JavaScript completo renderizzato passa inoltre `node --check`.


