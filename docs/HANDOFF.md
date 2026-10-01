# RMBL B ROLL — handoff tecnico

Aggiornato: 2026-10-01  
Versione: `v0023`  
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
- `RMBL_B_ROLL_APP.vbs` è il launcher app senza bridge.

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

### Stato suite al passaggio v0023

I test focalizzati su branding, bridge, versione, launcher e distribuzione passano (`19 passed`). La suite completa eseguita con accesso temporaneo elevato riporta `844 passed, 7 failed`. I sette errori sono contratti legacy già esterni a questo intervento: due test del vecchio `/curation` debug, il launcher Envato che ora usa intenzionalmente `os.startfile`, un test Node bloccato dall'accesso Windows al file temporaneo, una variante di ricerca stock e due fixture `MemoryPath` incompatibili con il registro Envato. Non sono stati mascherati né rimossi.
