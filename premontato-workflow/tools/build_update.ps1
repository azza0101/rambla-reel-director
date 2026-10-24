param([Parameter(Mandatory=$true)][string]$RuntimePath,[string]$OutputDirectory=(Join-Path $PSScriptRoot '..\dist'))
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
& (Join-Path $PSScriptRoot 'prepare_models.ps1')
$runtime=[IO.Path]::GetFullPath($RuntimePath)
$out=[IO.Path]::GetFullPath($OutputDirectory)
$version=(Get-Content -Raw (Join-Path $root 'plugin\package.json')|ConvertFrom-Json).version
if($version -notmatch '^\d+\.\d+\.\d+$'){throw 'Versione Premontato non valida'}
if(!(Test-Path -LiteralPath (Join-Path $runtime 'python.exe')) -or !(Test-Path -LiteralPath (Join-Path $runtime 'THIRD_PARTY_NOTICES.txt'))){throw 'Runtime aggiornamento incompleto'}
$temp=Join-Path $root ('.premontato-update-build-'+[guid]::NewGuid().ToString('N'))
try{
    $stage=Join-Path $temp 'payload';foreach($dir in @('plugin','worker','runtime')){New-Item -ItemType Directory -Force -Path (Join-Path $stage $dir)|Out-Null}
    Get-ChildItem (Join-Path $root 'plugin') -File | Where-Object {$_.Name -ne 'WorkflowIntegration.node'} | Copy-Item -Destination (Join-Path $stage 'plugin')
    Copy-Item (Join-Path $root 'worker\*.py') (Join-Path $stage 'worker')
    Copy-Item (Join-Path $root 'worker\requirements.txt') (Join-Path $stage 'worker')
    Copy-Item (Join-Path $runtime '*') (Join-Path $stage 'runtime') -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $root 'runtime\models') -Destination (Join-Path $stage 'runtime\models') -Recurse -Force
    $archiveName='Premontato-'+$version+'.zip';$archive=Join-Path $out $archiveName
    New-Item -ItemType Directory -Force -Path $out|Out-Null
    if(Test-Path -LiteralPath $archive){Remove-Item -LiteralPath $archive -Force}
    Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $archive -CompressionLevel Optimal
    $digest=(Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    $manifest=[ordered]@{version=$version;archive=$archiveName;sha256=$digest}
    $manifestPath=Join-Path $out 'premontato-update.json'
    [IO.File]::WriteAllText($manifestPath,($manifest|ConvertTo-Json -Depth 4),[Text.UTF8Encoding]::new($false))
    Write-Output "Creato: $archive ($(Get-Item $archive).Length byte)"
    Write-Output "Manifest: $manifestPath · SHA-256 $digest"
}finally{if(Test-Path -LiteralPath $temp){Remove-Item -LiteralPath $temp -Recurse -Force}}
