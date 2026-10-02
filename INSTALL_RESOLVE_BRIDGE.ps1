param([string]$AppRoot = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
$AppRoot = (Resolve-Path -LiteralPath $AppRoot).Path
$source = Join-Path $AppRoot 'tools\resolve_bridge\RAMBLA_B_ROLL.py'
$target = Join-Path $env:APPDATA 'Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\RAMBLA_B_ROLL.py'
New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null
if ((Test-Path -LiteralPath $target) -and ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $target).Hash)) {
    $backupDir = Join-Path $env:LOCALAPPDATA 'RMBL B ROLL\bridge-backups'
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    Copy-Item -LiteralPath $target -Destination (Join-Path $backupDir ((Get-Date -Format 'yyyyMMdd-HHmmss-ffff') + '-RAMBLA_B_ROLL.py'))
}
Copy-Item -LiteralPath $source -Destination $target -Force
if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $target).Hash) {
    throw 'Verifica installazione fallita: il launcher installato non coincide con quello aggiornato.'
}
$configDir = Join-Path $env:LOCALAPPDATA 'RMBL B ROLL'
New-Item -ItemType Directory -Force -Path $configDir | Out-Null
@{ app_root = $AppRoot } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $configDir 'install.json') -Encoding UTF8
$release = (Get-Content -LiteralPath (Join-Path $AppRoot 'RAMBLA_VERSION') -Raw).Trim()
Write-Host "Launcher verificato: RAMBLA - B-ROLL $release. Chiudi il vecchio bridge e riaprilo da Workspace > Scripts > RAMBLA_B_ROLL."
Write-Host 'I prossimi aggiornamenti del bridge verranno caricati dalla cartella RAMBLA automaticamente.'
