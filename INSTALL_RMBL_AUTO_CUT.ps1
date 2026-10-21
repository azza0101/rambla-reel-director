$ErrorActionPreference = 'Stop'
$runtime = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runtime)) { throw 'Installa prima il runtime RMBL B ROLL: questa versione iniziale usa il motore gia presente.' }
& $runtime (Join-Path $PSScriptRoot 'tools\install_autocut_integration.py') --app-root $PSScriptRoot
if ($LASTEXITCODE -ne 0) { throw 'Installazione Auto-Cut non riuscita' }
