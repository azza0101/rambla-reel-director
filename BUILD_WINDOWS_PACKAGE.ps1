param([string]$OutputDirectory = (Join-Path $PSScriptRoot 'dist'), [string]$ProvisionFile)
$ErrorActionPreference = 'Stop'
$version = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'RAMBLA_VERSION') -Raw).Trim()
$stage = Join-Path ([IO.Path]::GetTempPath()) ('rmbl-package-' + [guid]::NewGuid().ToString('N'))
$payload = Join-Path $stage 'payload'
New-Item -ItemType Directory -Path $payload -Force | Out-Null
try {
    foreach ($directory in @('backend','tools')) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $directory) -Destination $payload -Recurse -Force
    }
    foreach ($file in @('launch_local_v5.py','pyproject.toml','RAMBLA_VERSION','RMBL_B_ROLL_APP.vbs','RMBL_BRIDGE.vbs','RAMBLA_REEL_DIRECTOR.vbs','INSTALL_RMBL_B_ROLL.cmd','INSTALL_RMBL_B_ROLL.ps1','INSTALL_RESOLVE_BRIDGE.ps1','SEARCH_UPDATE.ps1','ROLLBACK_RMBL.ps1','cloud.env.example','README.md')) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination $payload -Force
    }
    $wheels = Join-Path $PSScriptRoot '.runtime-temp\release-wheels'
    if (-not (Test-Path -LiteralPath $wheels)) { throw 'Prepara prima le wheel con python -m pip wheel . setuptools wheel --wheel-dir .runtime-temp\release-wheels' }
    Copy-Item -LiteralPath $wheels -Destination (Join-Path $payload 'wheels') -Recurse
    $bin = Join-Path $payload 'runtime\bin'
    New-Item -ItemType Directory -Path $bin -Force | Out-Null
    $ffmpeg = (Get-Command ffmpeg.exe -ErrorAction Stop).Source
    $ffroot = Split-Path -Parent $ffmpeg
    foreach ($name in @('ffmpeg.exe','ffprobe.exe')) { Copy-Item -LiteralPath (Join-Path $ffroot $name) -Destination $bin }
    Get-ChildItem -LiteralPath $ffroot -File -Filter '*.dll' | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $bin }
    Copy-Item -LiteralPath (Get-Command gh.exe -ErrorAction Stop).Source -Destination $bin
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'docs\WINDOWS_INSTALL_UPDATE.md') -Destination $payload
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'docs\THIRD_PARTY_RUNTIME.txt') -Destination $payload
    Get-ChildItem -LiteralPath $payload -Directory -Recurse -Filter '__pycache__' | Remove-Item -Recurse -Force
    Get-ChildItem -LiteralPath $payload -File -Recurse -Filter '*.pyc' | Remove-Item -Force
    if ($ProvisionFile) {
        Copy-Item -LiteralPath $ProvisionFile -Destination (Join-Path $payload 'personal-provision.json')
    }
    $forbidden = Get-ChildItem -LiteralPath $payload -File -Recurse | Where-Object { $_.Name -match '^\.env(\.|$)|^gateway\.db$|^gateway-token|^encryption-key|^admin\.json$' }
    if ($forbidden) { throw 'File privato rilevato nello staging. Build interrotta.' }
    New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
    $archiveName = "RMBL-B-ROLL-Windows-$version.zip"
    $archive = Join-Path $OutputDirectory $archiveName
    if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive -Force }
    Compress-Archive -Path (Join-Path $payload '*') -DestinationPath $archive -CompressionLevel Optimal
    @{ version=$version; archive=$archiveName; sha256=(Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputDirectory 'update.json') -Encoding UTF8
    Write-Host "Pacchetto verificabile creato: $archive"
} finally {
    $target = [IO.Path]::GetFullPath($stage)
    $temp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if ($target.StartsWith($temp,[StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $target)) { Remove-Item -LiteralPath $target -Recurse -Force }
}
