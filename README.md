# RMBL B ROLL

RMBL B ROLL prepara trascrizione, visual beat, ricerche B-roll, sottotitoli e parole evidenziate, quindi consegna un pacchetto verificabile al bridge di DaVinci Resolve.

## Installazione Windows

1. Estrai `RMBL-B-ROLL-Windows-vXXXX.zip` in una cartella locale.
2. Avvia `INSTALL_RMBL_B_ROLL.cmd`.
3. Apri l'app dal collegamento **RMBL B ROLL** sul desktop.
4. In Resolve apri **Workspace → Scripts → RAMBLA_B_ROLL**.

L'installer crea un ambiente Python 3.12 isolato, installa l'app, registra il bridge Resolve e crea il launcher dell'app. Se Python 3.12 manca, usa `winget` per installarlo. Nessun progetto, media, token o profilo browser viene incluso nel pacchetto.

## Launcher senza bridge

`RMBL_B_ROLL_APP.vbs` avvia solo l'app e riutilizza una singola istanza. Non avvia né modifica Resolve.

## Creare il pacchetto

Da PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\BUILD_WINDOWS_PACKAGE.ps1
```

Il file ZIP viene scritto in `dist`. Include solo codice, asset di branding e installer; esclude cache, media, progetti, log e credenziali.

## Sviluppo e passaggio di consegne

La versione visibile è in `RAMBLA_VERSION`. Il riepilogo tecnico aggiornato è in [docs/HANDOFF.md](docs/HANDOFF.md).
