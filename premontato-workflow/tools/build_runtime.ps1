param([string]$OutputPath = (Join-Path $PSScriptRoot '..\plugin\runtime'))
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$lockRoot = Join-Path $root 'runtime'
$tmp = Join-Path ([IO.Path]::GetTempPath()) ('premontato-runtime-' + [guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Path $tmp | Out-Null
    $pythonLock = Get-Content (Join-Path $lockRoot 'python-runtime.lock')
    $pythonUrl, $pythonHash = $pythonLock[-1] -split ' '
    $pythonZip = Join-Path $tmp 'python-embed.zip'
    Invoke-WebRequest -Uri $pythonUrl -OutFile $pythonZip
    if ((Get-FileHash $pythonZip -Algorithm SHA256).Hash -ne $pythonHash) { throw 'Hash runtime Python non valido' }
    Expand-Archive -LiteralPath $pythonZip -DestinationPath $tmp
    $wheelDir = Join-Path $tmp 'wheels'; New-Item -ItemType Directory -Path $wheelDir | Out-Null
    python -m pip download --only-binary=:all: --require-hashes --python-version 3.13 --implementation cp --abi cp313 --platform win_amd64 -r (Join-Path $lockRoot 'requirements.lock') -d $wheelDir
    $site = Join-Path $tmp 'site-packages'; New-Item -ItemType Directory -Path $site | Out-Null
    Get-ChildItem $wheelDir -Filter '*.whl' | ForEach-Object { python -m zipfile -e $_.FullName $site }
    @'
python313.zip
.
site-packages
../worker
import site
'@ | Set-Content (Join-Path $tmp 'python313._pth') -Encoding ascii
    $licenseDir = Join-Path $tmp 'licenses'; New-Item -ItemType Directory -Path $licenseDir | Out-Null
    Copy-Item (Join-Path $lockRoot 'THIRD_PARTY_NOTICES.txt') $tmp
    Copy-Item (Join-Path $lockRoot 'licenses\*') $licenseDir
    Get-ChildItem $site -Directory -Filter '*.dist-info' | ForEach-Object {
        $dest = Join-Path $licenseDir $_.Name; New-Item -ItemType Directory -Path $dest | Out-Null
        Get-ChildItem $_.FullName -Recurse -File | Where-Object { $_.Name -match '^(LICENSE|COPYING|NOTICE|AUTHORS|PATENTS)' -or $_.DirectoryName -match '\\licenses($|\\)' } | ForEach-Object {
            $rel = $_.FullName.Substring($_.FullName.IndexOf($_.Directory.Name, [StringComparison]::OrdinalIgnoreCase))
            $out = Join-Path $dest (Split-Path $_.FullName -Leaf); Copy-Item $_.FullName $out -Force
        }
    }
    # Validate the exact isolated runtime, not the developer's system Python.
    & (Join-Path $tmp 'python.exe') -c 'import cv2,numpy,pypdf; print(cv2.__version__,numpy.__version__,pypdf.__version__)'
    if ($LASTEXITCODE) { throw 'Import runtime Premontato fallito' }
    Remove-Item -LiteralPath $wheelDir -Recurse -Force
    Remove-Item -LiteralPath $pythonZip -Force
    $OutputPath = [IO.Path]::GetFullPath($OutputPath)
    if (Test-Path -LiteralPath $OutputPath) { Remove-Item -LiteralPath $OutputPath -Recurse -Force }
    Move-Item -LiteralPath $tmp -Destination $OutputPath
    $tmp = $null
} finally { if ($tmp -and (Test-Path -LiteralPath $tmp)) { Remove-Item -LiteralPath $tmp -Recurse -Force } }
