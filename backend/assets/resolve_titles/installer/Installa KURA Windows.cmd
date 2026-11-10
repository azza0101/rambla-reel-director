@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Installa KURA Windows.ps1"
if errorlevel 1 echo Installazione non completata. Leggi il messaggio sopra.
pause
