param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'RMBL B ROLL\app'),
    [switch]$SkipDependencyInstall,
    [switch]$ForceUpdate,
    [switch]$SkipDesktopIntegration,
    [string]$PythonExecutable
)
$ErrorActionPreference = 'Stop'
$SourceRoot = $PSScriptRoot
$productRoot = Split-Path -Parent $InstallRoot
$dataRoot = Join-Path $productRoot 'rambla-data'
$manifestPath = Join-Path $productRoot 'install.json'
$incomingVersion = (Get-Content -LiteralPath (Join-Path $SourceRoot 'RAMBLA_VERSION') -Raw).Trim()
$installedVersion = ''
if (Test-Path -LiteralPath (Join-Path $InstallRoot 'RAMBLA_VERSION')) {
    $installedVersion = (Get-Content -LiteralPath (Join-Path $InstallRoot 'RAMBLA_VERSION') -Raw).Trim()
}

if ($installedVersion -and -not $ForceUpdate) {
    Add-Type -AssemblyName PresentationFramework
    if ($installedVersion -eq $incomingVersion) {
        $question = "RMBL B ROLL $installedVersion e gia installato.`n`nVuoi riparare l'installazione senza cancellare dati, progetti, accessi o configurazioni?"
        $caption = 'RMBL B ROLL - Riparazione'
    }
    else {
        $question = "RMBL B ROLL $installedVersion e gia installato.`n`nVuoi aggiornarlo a $incomingVersion? Dati, progetti, accessi e configurazioni saranno conservati."
        $caption = 'RMBL B ROLL - Aggiornamento'
    }
    $choice = [System.Windows.MessageBox]::Show(
        $question, $caption,
        [System.Windows.MessageBoxButton]::YesNo,
        [System.Windows.MessageBoxImage]::Question
    )
    if ($choice -ne [System.Windows.MessageBoxResult]::Yes) {
        Write-Host 'Installazione annullata. Nessun file e stato modificato.'
        exit 0
    }
}

$runtimePath = Join-Path $dataRoot 'desktop-runtime.json'
if ($installedVersion -and (Test-Path -LiteralPath $runtimePath)) {
    $runtime = Get-Content -LiteralPath $runtimePath -Raw | ConvertFrom-Json
    $busy = $null
    try {
        $base = ([Uri]$runtime.url).GetLeftPart([UriPartial]::Authority)
        if (([Uri]$base).Host -in @('127.0.0.1','localhost','::1')) {
            $busy = Invoke-RestMethod -Uri "$base/api/curation/software-update/status" -TimeoutSec 4
        }
    } catch { }
    if ($busy.busy) { throw 'Elaborazione RMBL attiva: attendi la fine prima di aggiornare.' }
}
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
$updateMarker = Join-Path $InstallRoot '.update-in-progress'
[IO.File]::WriteAllText($updateMarker, (Get-Date).ToString('o'))
try {
    $existingPython = Join-Path $InstallRoot '.venv\Scripts\python.exe'
    if ($installedVersion -and (Test-Path -LiteralPath $existingPython)) {
        & $existingPython (Join-Path $InstallRoot 'launch_local_v5.py') stop
        if ($LASTEXITCODE -ne 0) { throw 'Arresto RMBL fallito; aggiornamento annullato.' }
    }
New-Item -ItemType Directory -Force -Path $productRoot | Out-Null
New-Item -ItemType Directory -Force -Path $dataRoot | Out-Null
if ($installedVersion) {
    $backupRoot = Join-Path $productRoot 'install-backups'
    $backup = Join-Path $backupRoot ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + $installedVersion)
    New-Item -ItemType Directory -Force -Path $backup | Out-Null
    foreach ($localFile in @('.env.local', 'cloud.env.local', 'settings.json', 'user-settings.json')) {
        $candidate = Join-Path $InstallRoot $localFile
        if (Test-Path -LiteralPath $candidate) {
            Copy-Item -LiteralPath $candidate -Destination $backup -Force
        }
    }
    if (Test-Path -LiteralPath $manifestPath) {
        Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $backup 'install.json') -Force
    }
    $codeBackup = Join-Path $backup 'code'
    New-Item -ItemType Directory -Path $codeBackup | Out-Null
    foreach ($name in @('backend','tools','launch_local_v5.py','RAMBLA_VERSION','pyproject.toml','SEARCH_UPDATE.ps1','INSTALL_RMBL_B_ROLL.ps1','INSTALL_RESOLVE_BRIDGE.ps1','RMBL_B_ROLL_APP.vbs','RMBL_BRIDGE.vbs')) {
        $item = Join-Path $InstallRoot $name
        if (Test-Path -LiteralPath $item) { Copy-Item -LiteralPath $item -Destination $codeBackup -Recurse -Force }
    }
    Copy-Item -LiteralPath (Join-Path $SourceRoot 'ROLLBACK_RMBL.ps1') -Destination $backup -Force
    @{
        previous_version = $installedVersion
        incoming_version = $incomingVersion
        data_root = $dataRoot
        created_at = (Get-Date).ToString('o')
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $backup 'update.json') -Encoding UTF8
}

if ((Resolve-Path -LiteralPath $SourceRoot).Path -ne [IO.Path]::GetFullPath($InstallRoot)) {
    New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
    foreach ($directory in @('backend', 'tools', 'runtime', 'wheels')) {
        Copy-Item -LiteralPath (Join-Path $SourceRoot $directory) -Destination $InstallRoot -Recurse -Force
    }
    foreach ($file in @('launch_local_v5.py','pyproject.toml','RAMBLA_VERSION','RMBL_B_ROLL_APP.vbs','RAMBLA_REEL_DIRECTOR.vbs','INSTALL_RESOLVE_BRIDGE.ps1','cloud.env.example','SEARCH_UPDATE.ps1','INSTALL_RMBL_B_ROLL.ps1','ROLLBACK_RMBL.ps1','RMBL_BRIDGE.vbs')) {
        Copy-Item -LiteralPath (Join-Path $SourceRoot $file) -Destination $InstallRoot -Force
    }
}

$python = $null
if ($PythonExecutable) {
    & $PythonExecutable -c "import sys; assert sys.version_info[:2] == (3,12)"
    if ($LASTEXITCODE -ne 0) { throw 'Runtime di test non compatibile.' }
    $python = @($PythonExecutable)
}
$probeErrorAction = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py -and -not $python) {
        & $py.Source -3.12 -c "import sys; assert sys.version_info[:2] == (3, 12)" 2>$null
        if ($LASTEXITCODE -eq 0) { $python = @($py.Source, '-3.12') }
    }
    if (-not $python) {
        $candidate = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($candidate) {
            & $candidate.Source -c "import sys; assert sys.version_info[:2] == (3, 12)" 2>$null
            if ($LASTEXITCODE -eq 0) { $python = @($candidate.Source) }
        }
    }
}
finally {
    $ErrorActionPreference = $probeErrorAction
}
if (-not $python) {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) { throw 'Serve Python 3.12. Installalo da python.org e rilancia questo file.' }
    & $winget.Source install --id Python.Python.3.12 --exact --silent --accept-package-agreements --accept-source-agreements
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($LASTEXITCODE -ne 0) { throw 'Installazione Python non riuscita.' }
    if (-not $py) {
        $launcher = Join-Path $env:LOCALAPPDATA 'Programs\Python\Launcher\py.exe'
        if (Test-Path -LiteralPath $launcher) { $py = [pscustomobject]@{ Source = $launcher } }
    }
    if (-not $py) { throw 'Python installato ma launcher non visibile: riapri il setup.' }
    $python = @($py.Source, '-3.12')
}

$venvPython = Join-Path $InstallRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    if ($python.Count -eq 2) { & $python[0] $python[1] -m venv (Join-Path $InstallRoot '.venv') }
    else { & $python[0] -m venv (Join-Path $InstallRoot '.venv') }
}
if (-not (Test-Path -LiteralPath $venvPython)) { throw 'Creazione runtime Python fallita.' }
if (-not $SkipDependencyInstall) {
    $wheels = Join-Path $InstallRoot 'wheels'
    & $venvPython -m pip install --no-index --find-links $wheels setuptools wheel
    if ($LASTEXITCODE -ne 0) { throw 'Installazione strumenti Python fallita.' }
    & $venvPython -m pip install --no-index --find-links $wheels --no-build-isolation -e $InstallRoot
    if ($LASTEXITCODE -ne 0) { throw 'Installazione dipendenze fallita. La versione precedente e conservata in install-backups.' }
}
& $venvPython -I -c "import fastapi, uvicorn, httpx, PIL, playwright, yt_dlp, tkinter; from backend.app.curation_server import create_app"
if ($LASTEXITCODE -ne 0) { throw 'Verifica del runtime fallita.' }
$mediaBin = Join-Path $InstallRoot 'runtime\bin'
$null = & (Join-Path $mediaBin 'ffmpeg.exe') -version 2>&1
if ($LASTEXITCODE -ne 0) { throw 'FFmpeg non funzionante.' }
$null = & (Join-Path $mediaBin 'ffprobe.exe') -version 2>&1
if ($LASTEXITCODE -ne 0) { throw 'FFprobe non funzionante.' }
if (-not $SkipDesktopIntegration) {
    & (Join-Path $InstallRoot 'INSTALL_RESOLVE_BRIDGE.ps1') -AppRoot $InstallRoot
    & $venvPython (Join-Path $InstallRoot 'tools\install_platform_assets.py')
    if ($LASTEXITCODE -ne 0) { throw 'Installazione template Fusion fallita.' }
}
$provision = Join-Path $SourceRoot 'personal-provision.json'
$credentials = Join-Path $InstallRoot '.env.local'
if ((Test-Path -LiteralPath $provision) -and -not (Test-Path -LiteralPath $credentials)) {
    $api = Get-Content -LiteralPath $provision -Raw | ConvertFrom-Json
    $lines = foreach ($key in @('PEXELS_API_KEY','GOOGLE_API_KEY','GOOGLE_CSE_ID','GEMINI_API_KEY','GROQ_API_KEY')) {
        $value = [string]$api.$key
        if ($value -and $value -notmatch '[\r\n]') { "$key=$value" }
    }
    [IO.File]::WriteAllLines($credentials, [string[]]$lines, (New-Object Text.UTF8Encoding($false)))
    Write-Host 'API preconfigurate dal pacchetto personale. I valori non vengono mostrati.'
}
if (Test-Path -LiteralPath $provision) {
    & $venvPython (Join-Path $InstallRoot 'tools\provision_github_auth.py') $provision
    if ($LASTEXITCODE -ne 0) { throw 'Preconfigurazione GitHub fallita: serve il token dedicato.' }
}
$previousVersion = $installedVersion
@{
    app_root = $InstallRoot
    data_root = $dataRoot
    version = $incomingVersion
    previous_version = $previousVersion
    installed_at = (Get-Date).ToString('o')
} | ConvertTo-Json | Set-Content -LiteralPath $manifestPath -Encoding UTF8
if (-not $SkipDesktopIntegration) {
    $desktop = [Environment]::GetFolderPath('Desktop')
    $shell = New-Object -ComObject WScript.Shell
    foreach ($entry in @(@('RMBL B ROLL','RMBL_B_ROLL_APP.vbs'), @('RMBL Bridge','RMBL_BRIDGE.vbs'))) {
        $shortcut = $shell.CreateShortcut((Join-Path $desktop ($entry[0] + '.lnk')))
        $shortcut.TargetPath = Join-Path $env:WINDIR 'System32\wscript.exe'
        $shortcut.Arguments = '"' + (Join-Path $InstallRoot $entry[1]) + '"'
        $shortcut.WorkingDirectory = $InstallRoot
        $shortcut.Description = $entry[0]
        $shortcut.IconLocation = Join-Path $InstallRoot 'backend\assets\branding\rmbl_app.ico'
        $shortcut.Save()
    }
}
Write-Host "Installazione completata e verificata: $InstallRoot"
Write-Host 'Progetti e chiavi del tuo PC restano separati dal programma. Configura le chiavi API al primo avvio.'

} catch {
    if ($backup -and (Test-Path -LiteralPath (Join-Path $backup 'code\RAMBLA_VERSION'))) {
        Get-ChildItem -LiteralPath (Join-Path $backup 'code') | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $InstallRoot -Recurse -Force
        }
        Write-Host 'Codice della versione precedente ripristinato.'
    }
    throw
} finally {
    if (Test-Path -LiteralPath $updateMarker) { Remove-Item -LiteralPath $updateMarker -Force }
}
