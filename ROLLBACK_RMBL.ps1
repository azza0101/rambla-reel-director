param([string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'RMBL B ROLL\app'))
$ErrorActionPreference = 'Stop'
$code = Join-Path $PSScriptRoot 'code'
if (-not (Test-Path -LiteralPath (Join-Path $code 'RAMBLA_VERSION'))) { throw 'Backup codice non valido.' }
$python = Join-Path $InstallRoot '.venv\Scripts\python.exe'
& $python (Join-Path $InstallRoot 'launch_local_v5.py') stop
Get-ChildItem -LiteralPath $code | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $InstallRoot -Recurse -Force }
& $python (Join-Path $InstallRoot 'launch_local_v5.py') start
Write-Host 'Codice ripristinato. Dati e progetti non sono stati modificati.'
