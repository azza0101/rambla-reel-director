$ErrorActionPreference = 'Stop'

$archive = Get-ChildItem -LiteralPath $PSScriptRoot -File -Filter 'RMBL-B-ROLL-Windows-v*.zip' |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1
if (-not $archive) {
    throw 'Archivio RMBL B ROLL non trovato nel pacchetto di installazione.'
}

$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
$stage = Join-Path $tempRoot ('rmbl-install-' + [guid]::NewGuid().ToString('N'))
$resolvedStage = [IO.Path]::GetFullPath($stage)
if (-not $resolvedStage.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Cartella temporanea non valida: $resolvedStage"
}

try {
    New-Item -ItemType Directory -Force -Path $resolvedStage | Out-Null
    Write-Host 'Estrazione di RMBL B ROLL...'
    Expand-Archive -LiteralPath $archive.FullName -DestinationPath $resolvedStage -Force
    $installer = Join-Path $resolvedStage 'INSTALL_RMBL_B_ROLL.ps1'
    if (-not (Test-Path -LiteralPath $installer)) {
        throw 'Installer interno non trovato: INSTALL_RMBL_B_ROLL.ps1'
    }
    $installRoot = Join-Path $env:LOCALAPPDATA 'RMBL B ROLL\app'
    & $installer -InstallRoot $installRoot
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "Installer interno terminato con codice $LASTEXITCODE."
    }
    Write-Host ''
    Write-Host 'RMBL B ROLL installato correttamente.' -ForegroundColor Green
    Write-Host 'Trovi RMBL B ROLL sul Desktop e il bridge nel menu Workspace > Scripts di DaVinci Resolve.'
}
finally {
    if (Test-Path -LiteralPath $resolvedStage) {
        Remove-Item -LiteralPath $resolvedStage -Recurse -Force
    }
}
