param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'RMBL B ROLL\app'),
    [switch]$SkipDependencyInstall,
    [switch]$ForceUpdate
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
    @{
        previous_version = $installedVersion
        incoming_version = $incomingVersion
        data_root = $dataRoot
        created_at = (Get-Date).ToString('o')
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $backup 'update.json') -Encoding UTF8
}

if ((Resolve-Path -LiteralPath $SourceRoot).Path -ne [IO.Path]::GetFullPath($InstallRoot)) {
    New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
    foreach ($directory in @('backend', 'tools')) {
        Copy-Item -LiteralPath (Join-Path $SourceRoot $directory) -Destination $InstallRoot -Recurse -Force
    }
    foreach ($file in @('launch_local_v5.py','pyproject.toml','RAMBLA_VERSION','RMBL_B_ROLL_APP.vbs','RAMBLA_REEL_DIRECTOR.vbs','INSTALL_RESOLVE_BRIDGE.ps1','cloud.env.example')) {
        Copy-Item -LiteralPath (Join-Path $SourceRoot $file) -Destination $InstallRoot -Force
    }
}

$python = $null
$probeErrorAction = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
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
    if (-not $py) { throw 'Python 3.12 installato ma non ancora visibile. Riavvia Windows e rilancia.' }
    $python = @($py.Source, '-3.12')
}

$venvPython = Join-Path $InstallRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    if ($python.Count -eq 2) { & $python[0] $python[1] -m venv (Join-Path $InstallRoot '.venv') }
    else { & $python[0] -m venv (Join-Path $InstallRoot '.venv') }
}
if (-not $SkipDependencyInstall) {
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -e $InstallRoot
}

& (Join-Path $InstallRoot 'INSTALL_RESOLVE_BRIDGE.ps1') -AppRoot $InstallRoot
$previousVersion = $installedVersion
@{
    app_root = $InstallRoot
    data_root = $dataRoot
    version = $incomingVersion
    previous_version = $previousVersion
    installed_at = (Get-Date).ToString('o')
} | ConvertTo-Json | Set-Content -LiteralPath $manifestPath -Encoding UTF8
$desktop = [Environment]::GetFolderPath('Desktop')
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path $desktop 'RMBL B ROLL.lnk'))
$shortcut.TargetPath = Join-Path $env:WINDIR 'System32\wscript.exe'
$shortcut.Arguments = '"' + (Join-Path $InstallRoot 'RMBL_B_ROLL_APP.vbs') + '"'
$shortcut.WorkingDirectory = $InstallRoot
$shortcut.Description = 'RMBL B ROLL'
$shortcut.IconLocation = Join-Path $env:WINDIR 'System32\shell32.dll,14'
$shortcut.Save()
Write-Host "Installazione completata: $InstallRoot"
Write-Host 'Launcher app creato sul desktop. Bridge installato nel menu Scripts di Resolve.'
