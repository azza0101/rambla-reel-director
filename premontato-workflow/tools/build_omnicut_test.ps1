param(
 [Parameter(Mandatory=$true)][string]$RuntimePath,
 [string]$OutputDirectory=(Join-Path $PSScriptRoot '..\dist-omnicut-test'),
 [string]$Version='0.1.0',
 [string]$NodePath='C:\Program Files\nodejs\node.exe'
)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot));$out=[IO.Path]::GetFullPath($OutputDirectory);$runtime=[IO.Path]::GetFullPath($RuntimePath)
if($Version -notmatch '^\d+\.\d+\.\d+$'){throw 'Versione Omni-Cut test non valida'}
if(!(Test-Path -LiteralPath (Join-Path $runtime 'python.exe'))){throw 'Runtime locale mancante'}
$stage=[IO.Path]::GetFullPath((Join-Path $root ('.omnicut-test-build-'+[guid]::NewGuid().ToString('N'))))
if(!$stage.StartsWith($root+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Directory di build non valida'}
try{
 & $NodePath (Join-Path $PSScriptRoot 'omnicut_test_product.cjs') $root $stage $Version
 if($LASTEXITCODE -ne 0){throw 'Preparazione prodotto fallita'}
 New-Item -ItemType Directory -Path (Join-Path $stage 'runtime')|Out-Null
 foreach($name in @('premontato','models','THIRD_PARTY_NOTICES.txt')){Copy-Item -LiteralPath (Join-Path $root ('runtime\'+$name)) -Destination (Join-Path $stage 'runtime') -Recurse -Force}
 & (Join-Path $stage 'tools\build_installer.ps1') -RuntimePath $runtime -OutputPath (Join-Path $out 'Install-OmniCut-Test.exe')
 if($LASTEXITCODE -ne 0){throw 'Build installer Omni-Cut test fallita'}
 & (Join-Path $stage 'tools\build_update.ps1') -RuntimePath $runtime -OutputDirectory $out
 if($LASTEXITCODE -ne 0){throw 'Build aggiornamento Omni-Cut test fallita'}
 Write-Output ('Omni-Cut test '+$Version+' pronto in '+$out)
}finally{
 # Delete only the unique generated staging tree checked above.
 if($stage.StartsWith($root+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -and (Split-Path -Leaf $stage) -match '^\.omnicut-test-build-[a-f0-9]{32}$' -and (Test-Path -LiteralPath $stage)){Remove-Item -LiteralPath $stage -Recurse -Force}
}
