@echo off
setlocal
title RMBL B ROLL - Installazione
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL_FROM_ARCHIVE.ps1"
if errorlevel 1 (
  echo.
  echo Installazione non riuscita. Leggi il messaggio sopra e riprova.
  pause
  exit /b 1
)
exit /b 0
