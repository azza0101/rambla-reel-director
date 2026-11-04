<#
Prune ONLY old, positively identified RMBL install-backups after a successful
installation. Keep the just-created backup of the version being replaced.

Never touch rambla-data, projects, media, API keys, the live installation,
unrecognized/manual backup folders or reparse points.
#>
param(
    [Parameter(Mandatory=$true)][string]$InstallRoot,
    [Parameter(Mandatory=$true)][string]$KeepBackup
)
$ErrorActionPreference = 'Stop'

$installedRoot = [IO.Path]::GetFullPath($InstallRoot).TrimEnd('\', '/')
$productRoot = Split-Path -Parent $installedRoot
$backups = Join-Path $productRoot 'install-backups'
if (-not (Test-Path -LiteralPath $backups -PathType Container)) { return }
$backups = [IO.Path]::GetFullPath($backups).TrimEnd('\', '/')
$keep = [IO.Path]::GetFullPath($KeepBackup).TrimEnd('\', '/')
$folderPattern = '^\d{8}-\d{6}-v\d{4}$'
if (-not [string]::Equals((Split-Path -Parent $keep), $backups, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Backup da conservare fuori dalla cartella ufficiale: pulizia annullata'
}
if ((Split-Path -Leaf $keep) -notmatch $folderPattern) {
    throw 'Nome backup da conservare non valido: pulizia annullata'
}
if (-not (Test-Path -LiteralPath $keep -PathType Container)) {
    throw 'Backup della versione precedente non presente: pulizia annullata'
}
$rootItem = Get-Item -LiteralPath $backups -Force
$keepItem = Get-Item -LiteralPath $keep -Force
if (($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    ($keepItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw 'Cartella backup non sicura: pulizia annullata'
}
$installedVersionPath = Join-Path $installedRoot 'RAMBLA_VERSION'
if (-not (Test-Path -LiteralPath $installedVersionPath -PathType Leaf)) { throw 'Versione installata mancante' }
$current = (Get-Content -LiteralPath $installedVersionPath -Raw).Trim()
if ($current -notmatch '^v\d{4}$') { throw 'Versione installata non valida' }

function Test-RMBLManagedBackup([IO.DirectoryInfo]$Folder) {
    if ($Folder.Name -notmatch $folderPattern -or
        ($Folder.Attributes -band [IO.FileAttributes]::ReparsePoint)) { return $false }
    $versionFile = Join-Path $Folder.FullName 'code\RAMBLA_VERSION'
    $receipt = Join-Path $Folder.FullName 'update.json'
    if (-not (Test-Path -LiteralPath $versionFile -PathType Leaf) -or
        -not (Test-Path -LiteralPath $receipt -PathType Leaf) -or
        -not (Test-Path -LiteralPath (Join-Path $Folder.FullName 'ROLLBACK_RMBL.ps1') -PathType Leaf)) {
        return $false
    }
    try {
        $record = Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json
        $previous = (Get-Content -LiteralPath $versionFile -Raw).Trim()
        if ($previous -notmatch '^v\d{4}$' -or
            $previous -ne $record.previous_version -or
            $Folder.Name -notmatch ('-' + [regex]::Escape($previous) + '$') -or
            [string]$record.incoming_version -notmatch '^v\d{4}$') {
            return $false
        }
        # Windows junctions and symlinks must never be traversed by cleanup.
        $links = @(Get-ChildItem -LiteralPath $Folder.FullName -Force -Recurse -ErrorAction Stop |
            Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint } |
            Select-Object -First 1)
        return $links.Count -eq 0
    } catch {
        return $false
    }
}

if (-not (Test-RMBLManagedBackup $keepItem)) {
    throw 'Il nuovo backup non e verificabile: nessuna vecchia versione eliminata'
}
$keepReceipt = Get-Content -LiteralPath (Join-Path $keep 'update.json') -Raw | ConvertFrom-Json
if ($keepReceipt.incoming_version -ne $current) {
    throw 'La nuova installazione non e confermata: nessun backup eliminato'
}

$removed = 0
foreach ($candidate in @(Get-ChildItem -LiteralPath $backups -Directory -Force)) {
    if ([string]::Equals($candidate.FullName, $keep, [StringComparison]::OrdinalIgnoreCase)) { continue }
    if (-not (Test-RMBLManagedBackup $candidate)) {
        Write-Host "Backup sconosciuto o non sicuro conservato: $($candidate.Name)"
        continue
    }
    try {
        Remove-Item -LiteralPath $candidate.FullName -Recurse -Force -ErrorAction Stop
        $removed++
    } catch {
        Write-Warning "Impossibile eliminare il vecchio backup $($candidate.Name): $($_.Exception.Message)"
    }
}
Write-Host "Pulizia RMBL: conservato un backup della versione precedente; rimossi $removed backup locali vecchi."
