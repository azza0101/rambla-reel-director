param([string]$OutputDirectory = (Join-Path $PSScriptRoot 'dist'))
$ErrorActionPreference = 'Stop'
$version = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'RAMBLA_VERSION') -Raw).Trim()
$stage = Join-Path $env:TEMP ("rmbl-package-" + [guid]::NewGuid().ToString('N'))
$payload = Join-Path $stage 'RMBL-B-ROLL'
New-Item -ItemType Directory -Force -Path $payload | Out-Null
foreach ($directory in @('backend', 'tools')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $directory) -Destination $payload -Recurse -Force
}
foreach ($file in @('launch_local_v5.py','pyproject.toml','RAMBLA_VERSION','RMBL_B_ROLL_APP.vbs','RAMBLA_REEL_DIRECTOR.vbs','INSTALL_RMBL_B_ROLL.cmd','INSTALL_RMBL_B_ROLL.ps1','INSTALL_RESOLVE_BRIDGE.ps1','cloud.env.example','README.md')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination $payload -Force
}
$resolvedStage = [IO.Path]::GetFullPath($stage)
$resolvedTemp = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
if (-not $resolvedStage.StartsWith($resolvedTemp, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Cartella di staging non valida: $resolvedStage"
}
Get-ChildItem -LiteralPath $payload -Directory -Recurse -Filter '__pycache__' | Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $payload -File -Recurse -Filter '*.pyc' | Remove-Item -Force
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$archive = Join-Path $OutputDirectory ("RMBL-B-ROLL-Windows-$version.zip")
if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive -Force }
Compress-Archive -Path (Join-Path $payload '*') -DestinationPath $archive -CompressionLevel Optimal
Remove-Item -LiteralPath $resolvedStage -Recurse -Force
Write-Host "Pacchetto creato: $archive"
