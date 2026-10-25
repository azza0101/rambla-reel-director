param([string]$OutputPath = (Join-Path $PSScriptRoot '..\dist\Install-Premontato.exe'), [string]$RuntimePath = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
& (Join-Path $PSScriptRoot 'prepare_models.ps1')
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
    Copy-Item -LiteralPath (Join-Path $root 'runtime\premontato') -Destination (Join-Path $payload 'runtime\premontato') -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $root 'runtime\models') -Destination (Join-Path $payload 'runtime\models') -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $root 'runtime\THIRD_PARTY_NOTICES.txt') -Destination (Join-Path $payload 'runtime\THIRD_PARTY_NOTICES.txt') -Force
    Compress-Archive -Path (Join-Path $payload '*') -DestinationPath (Join-Path $temp 'payload.zip') -CompressionLevel Optimal
    $out = [IO.Path]::GetFullPath($OutputPath); New-Item -ItemType Directory -Force -Path (Split-Path $out) | Out-Null
    $launcher = Join-Path $PSScriptRoot 'launcher'
    $compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
    if (!(Test-Path -LiteralPath $compiler)) { throw '.NET Framework C# compiler is not available on this Windows system' }
    $launcherExe = Join-Path $temp 'Install-Premontato.exe'
    $payloadZip = Join-Path $temp 'payload.zip'
    $manifest = Join-Path $launcher 'app.manifest'
    $source = Join-Path $launcher 'Program.cs'
    $compilerArgs = @('/nologo','/target:winexe','/platform:x64',('/out:' + $launcherExe),('/win32manifest:' + $manifest),('/resource:' + $payloadZip + ',Premontato.payload.zip'),'/reference:System.dll','/reference:System.Core.dll','/reference:System.Windows.Forms.dll','/reference:System.IO.Compression.dll','/reference:System.IO.Compression.FileSystem.dll',$source)
    & $compiler @compilerArgs
    if ($LASTEXITCODE -ne 0 -or !(Test-Path -LiteralPath $launcherExe)) { throw 'C# launcher compile failed' }
    Copy-Item -LiteralPath $launcherExe -Destination $out -Force
    $check = Get-Item $out
    if ($check.Length -lt 20MB) { throw 'Installer sospettosamente piccolo: payload runtime mancante' }
    Write-Output "Creato: $out ($($check.Length) byte)"
} finally { if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Recurse -Force } }


