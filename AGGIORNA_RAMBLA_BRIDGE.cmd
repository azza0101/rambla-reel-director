@echo off
setlocal
set "SOURCE=%~dp0tools\resolve_bridge\RAMBLA_B_ROLL.py"
set "TARGET=%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\RAMBLA_B_ROLL.py"
if not exist "%SOURCE%" (
  echo ERRORE: file bridge RAMBLA non trovato.
  pause
  exit /b 1
)
if not exist "%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility" mkdir "%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility"
copy /Y "%SOURCE%" "%TARGET%" >nul
if errorlevel 1 (
  echo ERRORE: chiudi la finestra del bridge e riprova.
  pause
  exit /b 1
)
echo Bridge RAMBLA aggiornato. Chiudi e riapri RAMBLA - B-ROLL dal menu Scripts di Resolve.
pause
