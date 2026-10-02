param([string]$OutputDirectory = (Join-Path $PSScriptRoot 'dist'))
$ErrorActionPreference = 'Stop'

& (Join-Path $PSScriptRoot 'BUILD_WINDOWS_PACKAGE.ps1') -OutputDirectory $OutputDirectory
$version = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'RAMBLA_VERSION') -Raw).Trim()
$archiveName = "RMBL-B-ROLL-Windows-$version.zip"
$archive = Join-Path $OutputDirectory $archiveName
if (-not (Test-Path -LiteralPath $archive)) {
    throw "Pacchetto sorgente non trovato: $archive"
}

$iexpress = Join-Path $env:WINDIR 'System32\iexpress.exe'
if (-not (Test-Path -LiteralPath $iexpress)) {
    throw 'iexpress.exe non trovato: serve Windows per generare il setup monofile.'
}

$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
$stage = Join-Path $tempRoot ('rmbl-iexpress-' + [guid]::NewGuid().ToString('N'))
$resolvedStage = [IO.Path]::GetFullPath($stage)
if (-not $resolvedStage.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Cartella temporanea non valida: $resolvedStage"
}

New-Item -ItemType Directory -Force -Path $resolvedStage | Out-Null
try {
    Copy-Item -LiteralPath $archive -Destination (Join-Path $resolvedStage $archiveName) -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'INSTALL_FROM_ARCHIVE.cmd') -Destination $resolvedStage -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'INSTALL_FROM_ARCHIVE.ps1') -Destination $resolvedStage -Force
    New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
    $target = [IO.Path]::GetFullPath((Join-Path $OutputDirectory "RMBL-B-ROLL-Setup-$version.exe"))
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Force }
    $sedPath = Join-Path $resolvedStage 'RMBL-B-ROLL-Setup.sed'
    $sourceDirectory = $resolvedStage.TrimEnd('\') + '\'
    $sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=1
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=
DisplayLicense=
FinishMessage=
TargetName=$target
FriendlyName=RMBL B ROLL $version
AppLaunched=INSTALL_FROM_ARCHIVE.cmd
PostInstallCmd=<None>
AdminQuietInstCmd=INSTALL_FROM_ARCHIVE.cmd
UserQuietInstCmd=INSTALL_FROM_ARCHIVE.cmd
SourceFiles=SourceFiles
[SourceFiles]
SourceFiles0=$sourceDirectory
[SourceFiles0]
%FILE0%=
%FILE1%=
%FILE2%=
[Strings]
FILE0="INSTALL_FROM_ARCHIVE.cmd"
FILE1="INSTALL_FROM_ARCHIVE.ps1"
FILE2="$archiveName"
"@
    [IO.File]::WriteAllText($sedPath, $sed, [Text.Encoding]::ASCII)
    $process = Start-Process -FilePath $iexpress -ArgumentList @('/N', $sedPath) -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "IExpress terminato con codice $($process.ExitCode)."
    }
    if (-not (Test-Path -LiteralPath $target)) {
        throw 'IExpress non ha creato il file di setup.'
    }
    $size = (Get-Item -LiteralPath $target).Length
    if ($size -lt 1MB) {
        throw "Setup incompleto: dimensione inattesa $size byte."
    }
    Write-Host "Installer monofile creato: $target"
}
finally {
    if (Test-Path -LiteralPath $resolvedStage) {
        Remove-Item -LiteralPath $resolvedStage -Recurse -Force
    }
}
