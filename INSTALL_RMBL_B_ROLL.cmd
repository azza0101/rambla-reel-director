@echo off
setlocal
title RMBL B ROLL - Installazione
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL_RMBL_B_ROLL.ps1"
if errorlevel 1 (
  echo.
  echo Installazione non riuscita. Leggi il messaggio sopra.
  pause
  exit /b 1
)
echo.
echo RMBL B ROLL installato correttamente.
pause
