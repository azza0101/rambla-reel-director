param([string]$PluginRoot='', [string]$SdkPath='', [switch]$Quiet)
$ErrorActionPreference='Stop'
$id='com.rambla.premontato'
$sourceRoot=Split-Path -Parent $PSScriptRoot
$support=Join-Path $env:PROGRAMDATA 'Blackmagic Design\DaVinci Resolve\Support'
if(!$PluginRoot){$PluginRoot=Join-Path $support 'Workflow Integration Plugins'}
if(!$SdkPath){$SdkPath=Join-Path $support 'Developer\Workflow Integrations\Examples\SamplePlugin\WorkflowIntegration.node'}
if(!(Test-Path -LiteralPath $SdkPath -PathType Leaf)){Add-Type -AssemblyName System.Windows.Forms;$pick=New-Object System.Windows.Forms.OpenFileDialog;$pick.Title='Seleziona WorkflowIntegration.node dalla tua installazione Resolve';$pick.Filter='WorkflowIntegration.node|WorkflowIntegration.node';if($pick.ShowDialog() -ne [Windows.Forms.DialogResult]::OK){throw 'Selezione SDK annullata'};$SdkPath=$pick.FileName}
$PluginRoot=[IO.Path]::GetFullPath($PluginRoot);$target=Join-Path $PluginRoot $id;$stage=Join-Path $PluginRoot ('.premontato-stage-'+[guid]::NewGuid().ToString('N'));$backupRoot=Join-Path (Split-Path $PluginRoot) 'RAMBLA Premontato Install Backups';$backup=Join-Path $backupRoot ([DateTime]::Now.ToString('yyyyMMdd-HHmmss'))
$allowed=@('main.js','preload.js','resolve_adapter.js','session.js','ipc_security.js','index.html','style.css','renderer.js','updater.js','update.ps1','package.json','manifest.xml','worker\protocol.py','worker\script_parser.py','worker\transcript_align.py','worker\edit_selector.py','worker\pdf_script.py','worker\shot_analyzer.py','worker\cache.py','worker\requirements.txt')
function Assert-NoLink([string]$p){$c=[IO.Path]::GetFullPath($p);while($c){if(Test-Path -LiteralPath $c){if((Get-Item -Force -LiteralPath $c).Attributes -band [IO.FileAttributes]::ReparsePoint){throw ('Collegamento non consentito: '+$c)}};$parent=[IO.Path]::GetDirectoryName($c);if(!$parent -or $parent -eq $c){break};$c=$parent}}
try{
 Assert-NoLink $sourceRoot;Assert-NoLink $PluginRoot;Assert-NoLink $SdkPath
 $manifest=Get-Content -Raw -LiteralPath (Join-Path $sourceRoot 'plugin\package.json')|ConvertFrom-Json;if($manifest.name -ne 'rambla-premontato'){throw 'Pacchetto sorgente non valido'}
 if(!(Test-Path -LiteralPath $SdkPath -PathType Leaf) -or (Split-Path -Leaf $SdkPath) -ne 'WorkflowIntegration.node'){throw 'SDK Resolve non valido'}
 foreach($n in $allowed){$rel=if($n.StartsWith('worker\')){$n}else{'plugin\'+$n};$f=Join-Path $sourceRoot $rel;Assert-NoLink $f;if(!(Test-Path -LiteralPath $f -PathType Leaf)){throw ('File mancante: '+$n)}}
 $runtime=Join-Path $sourceRoot 'runtime';if(!(Test-Path (Join-Path $runtime 'python.exe')) -or !(Test-Path (Join-Path $runtime 'site-packages\cv2\__init__.py')) -or !(Test-Path (Join-Path $runtime 'THIRD_PARTY_NOTICES.txt'))){throw 'Runtime locale o licenze non completi'}
 Assert-NoLink $target;if(Test-Path -LiteralPath $target){$old=Get-Content -Raw -LiteralPath (Join-Path $target 'package.json')|ConvertFrom-Json;if($old.name -ne 'rambla-premontato'){throw 'Destinazione occupata da un altro plugin'}}
 New-Item -ItemType Directory -Force -Path $PluginRoot|Out-Null;New-Item -ItemType Directory -Path $stage|Out-Null
 foreach($n in $allowed){$rel=if($n.StartsWith('worker\')){$n}else{'plugin\'+$n};$src=Join-Path $sourceRoot $rel;$dest=Join-Path $stage $n;New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest)|Out-Null;Copy-Item -LiteralPath $src -Destination $dest}
 Copy-Item -LiteralPath $runtime -Destination (Join-Path $stage 'runtime') -Recurse
 Copy-Item -LiteralPath $SdkPath -Destination (Join-Path $stage 'WorkflowIntegration.node')
 if(Test-Path -LiteralPath $target){New-Item -ItemType Directory -Force -Path $backupRoot|Out-Null;Move-Item -LiteralPath $target -Destination $backup}
 try{Move-Item -LiteralPath $stage -Destination $target}catch{if(Test-Path -LiteralPath $backup){Move-Item -LiteralPath $backup -Destination $target};throw}
 $message='RAMBLA Premontato '+$manifest.version+' installato. Apri Workspace > Workflow Integrations > RAMBLA Premontato.';if(!(Get-Command ffmpeg -ErrorAction SilentlyContinue) -and !(Test-Path -LiteralPath 'C:\Program Files\FFmpeg\ffmpeg.exe')){$message+=' Analisi silenzi: installa FFmpeg nel PATH per abilitarla; fino ad allora le pause vengono conservate.'};Write-Output $message
 if(!$Quiet){Add-Type -AssemblyName System.Windows.Forms;[Windows.Forms.MessageBox]::Show($message,'RAMBLA Premontato')|Out-Null}
}catch{Write-Error -ErrorAction Continue $_;if(!$Quiet){Add-Type -AssemblyName System.Windows.Forms;[Windows.Forms.MessageBox]::Show($_.Exception.Message,'RAMBLA Premontato')|Out-Null};exit 1}
finally{if((Test-Path -LiteralPath $stage) -and [IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($stage)) -eq $PluginRoot -and [IO.Path]::GetFileName($stage).StartsWith('.premontato-stage-')){Assert-NoLink $stage;Remove-Item -LiteralPath $stage -Recurse -Force}}
