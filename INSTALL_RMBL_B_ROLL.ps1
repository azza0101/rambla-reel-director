param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'RMBL B ROLL\app'),
    [switch]$SkipDependencyInstall
)
$ErrorActionPreference = 'Stop'
$SourceRoot = $PSScriptRoot

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
