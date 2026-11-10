$ErrorActionPreference = 'Stop'
function Get-Sha256([string] $path) {
    $hash = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($path)
    try { return [BitConverter]::ToString($hash.ComputeHash($stream)).Replace('-', '') }
    finally { $stream.Dispose(); $hash.Dispose() }
}
try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $package = Join-Path $PSScriptRoot 'KURA_paper_title_v9_STANDALONE_FIXED.drfx'
    if (-not (Test-Path -LiteralPath $package -PathType Leaf)) { throw 'Preset DRFX non trovato accanto a questo installer.' }
    if (-not $env:APPDATA) { throw 'Cartella APPDATA non disponibile.' }
    $root = Join-Path $env:APPDATA 'Blackmagic Design\DaVinci Resolve\Support\Fusion\Templates'
    $fullRoot = [IO.Path]::GetFullPath($root).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    $targetPackage = Join-Path $root 'KURA_paper_title_v9_STANDALONE_FIXED.drfx'
    if ((Test-Path -LiteralPath $targetPackage) -and ((Get-Sha256 $targetPackage) -ne (Get-Sha256 $package))) {
        throw 'Un preset diverso ha lo stesso nome. Non e stato sovrascritto.'
    }
    $existingTitle = Join-Path $root 'Edit\Titles\KURA_paper_title_v9\KURA_paper_title_v9.setting'
    if ((Test-Path -LiteralPath $targetPackage -PathType Leaf) -and (Test-Path -LiteralPath $existingTitle -PathType Leaf)) {
        Write-Host 'Preset KURA gia presente. Nessun file modificato.'
        Write-Host 'Per lo stile corretto e necessario il font Montserrat.'
        exit 0
    }
    $zip = [IO.Compression.ZipFile]::OpenRead($package)
    try {
        $items = @()
        foreach ($entry in $zip.Entries) {
            if (-not $entry.Name) { continue }
            $relative = $entry.FullName.Replace('/', [IO.Path]::DirectorySeparatorChar)
            $dest = [IO.Path]::GetFullPath((Join-Path $root $relative))
            if (-not $dest.StartsWith($fullRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Percorso non valido nel preset.' }
            if (Test-Path -LiteralPath $dest -PathType Leaf) {
                $hash = [Security.Cryptography.SHA256]::Create()
                $stream = $entry.Open()
                try { $expected = [BitConverter]::ToString($hash.ComputeHash($stream)).Replace('-', '') } finally { $stream.Dispose(); $hash.Dispose() }
                if ((Get-Sha256 $dest) -ne $expected) { throw "Esiste gia una versione diversa: $dest. Non e stata sovrascritta." }
            }
            $items += @{Entry=$entry; Destination=$dest}
        }
        New-Item -ItemType Directory -Force -Path $root | Out-Null
        if (-not (Test-Path -LiteralPath $targetPackage)) { Copy-Item -LiteralPath $package -Destination $targetPackage }
        $created = 0
        foreach ($item in $items) {
            if (-not (Test-Path -LiteralPath $item.Destination)) {
                New-Item -ItemType Directory -Force -Path (Split-Path -Parent $item.Destination) | Out-Null
                [IO.Compression.ZipFileExtensions]::ExtractToFile($item.Entry, $item.Destination)
                $created++
            }
        }
        if ($created -eq 0) { Write-Host 'Preset KURA gia presente e verificato.' }
        else { Write-Host 'Preset KURA installato. Riavvia Resolve per visualizzarlo nella libreria.' }
        Write-Host 'Per lo stile corretto e necessario il font Montserrat.'
    } finally { $zip.Dispose() }
} catch { Write-Error $_; exit 1 }
