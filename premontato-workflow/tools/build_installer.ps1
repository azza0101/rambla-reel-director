param([string]$OutputPath = (Join-Path $PSScriptRoot '..\dist\Install-Premontato.exe'), [string]$RuntimePath = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$temp = Join-Path $root ('.premontato-installer-' + [guid]::NewGuid().ToString('N'))
$payload = Join-Path $temp 'payload'; New-Item -ItemType Directory -Path $payload -Force | Out-Null
try {
    if ($RuntimePath) { Copy-Item -LiteralPath $RuntimePath -Destination (Join-Path $payload 'runtime') -Recurse }
    else { & (Join-Path $PSScriptRoot 'build_runtime.ps1') -OutputPath (Join-Path $payload 'runtime') }
    foreach ($dir in @('plugin','worker','install')) { New-Item -ItemType Directory -Path (Join-Path $payload $dir) -Force | Out-Null }
    Get-ChildItem (Join-Path $root 'plugin') -File | Where-Object { $_.Name -ne 'WorkflowIntegration.node' } | Copy-Item -Destination (Join-Path $payload 'plugin')
    Copy-Item (Join-Path $root 'worker\*.py') (Join-Path $payload 'worker')
    Copy-Item (Join-Path $root 'worker\requirements.txt') (Join-Path $payload 'worker')
    Copy-Item (Join-Path $root 'install\Install-Premontato.ps1') (Join-Path $payload 'install')
    Compress-Archive -Path (Join-Path $payload '*') -DestinationPath (Join-Path $temp 'payload.zip') -CompressionLevel Optimal
    $out = [IO.Path]::GetFullPath($OutputPath); New-Item -ItemType Directory -Force -Path (Split-Path $out) | Out-Null
    $launcher = Join-Path $PSScriptRoot 'launcher'
    Copy-Item (Join-Path $temp 'payload.zip') (Join-Path $launcher 'payload.zip')
    try {
        $env:DOTNET_CLI_HOME = Join-Path $temp '.dotnet-home'
        $env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = '1'
        $env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
        $env:DOTNET_NOLOGO = '1'
        $env:NUGET_PACKAGES = Join-Path $temp '.nuget-packages'
        $env:APPDATA = Join-Path $temp 'appdata'
        $nugetConfigDir = Join-Path $env:APPDATA 'NuGet'; New-Item -ItemType Directory -Force -Path $nugetConfigDir | Out-Null
        $nugetConfig = Join-Path $nugetConfigDir 'NuGet.Config'
        @'
<?xml version="1.0" encoding="utf-8"?>
<configuration><packageSources><clear/><add key="nuget.org" value="https://api.nuget.org/v3/index.json" /></packageSources></configuration>
'@ | Set-Content $nugetConfig -Encoding utf8
        & dotnet restore (Join-Path $launcher 'launcher.csproj') -r win-x64 --configfile $nugetConfig
        if ($LASTEXITCODE -ne 0) { throw 'dotnet restore failed' }
        & dotnet publish (Join-Path $launcher 'launcher.csproj') -c Release -r win-x64 --no-restore --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o (Join-Path $temp 'publish')
        if ($LASTEXITCODE -ne 0) { throw 'dotnet publish failed' }
        Copy-Item (Join-Path $temp 'publish\Install-Premontato.exe') $out -Force
    } finally { Remove-Item -LiteralPath (Join-Path $launcher 'payload.zip') -Force -ErrorAction SilentlyContinue }
    $check = Get-Item $out
    if ($check.Length -lt 20MB) { throw 'Installer sospettosamente piccolo: payload runtime mancante' }
    Write-Output "Creato: $out ($($check.Length) byte)"
} finally { if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Recurse -Force } }


