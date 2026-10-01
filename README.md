# RMBL B ROLL

RMBL B ROLL prepara trascrizione, visual beat, ricerche B-roll, sottotitoli e parole evidenziate, quindi consegna un pacchetto verificabile al bridge di DaVinci Resolve.

## Installazione Windows

1. Copia sul nuovo PC il solo file `RMBL-B-ROLL-Setup-vXXXX.exe`.
2. Avvialo con un doppio clic.
3. Apri l'app dal collegamento **RMBL B ROLL** sul desktop.
4. In Resolve apri **Workspace → Scripts → RAMBLA_B_ROLL**.

L'EXE contiene l'intero ZIP, crea un ambiente Python 3.12 isolato, installa l'app, registra il bridge Resolve e crea il launcher dell'app. Se Python 3.12 manca, usa `winget` per installarlo. Nessun progetto, media, token o profilo browser viene incluso nel pacchetto.

Se trova RMBL B ROLL gia installato, mostra la versione presente e quella nuova e chiede se aggiornarla. L'aggiornamento conserva `rambla-data`, progetti, selezioni, backup, profili browser, autorizzazioni e file di configurazione locali; crea anche un registro di sicurezza in `%LOCALAPPDATA%\RMBL B ROLL\install-backups`.

Lo ZIP `RMBL-B-ROLL-Windows-vXXXX.zip` rimane disponibile come alternativa manuale: estrailo e avvia `INSTALL_RMBL_B_ROLL.cmd`.

## Launcher senza bridge

`RMBL_B_ROLL_APP.vbs` avvia solo l'app e riutilizza una singola istanza. Non avvia né modifica Resolve.

## Creare il pacchetto

Da PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\BUILD_WINDOWS_INSTALLER.ps1
```

L'EXE monofile e lo ZIP vengono scritti in `dist`. Includono solo codice, asset di branding e installer; escludono cache, media, progetti, log e credenziali.

## Sviluppo e passaggio di consegne

La versione visibile è in `RAMBLA_VERSION`. Il riepilogo tecnico aggiornato è in [docs/HANDOFF.md](docs/HANDOFF.md).
