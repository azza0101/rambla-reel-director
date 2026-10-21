param([string]$PluginRoot='', [string]$SdkPath='', [switch]$Quiet, [switch]$NoElevate, [string]$OwnerSid='')
$ErrorActionPreference='Stop'
$id='com.rambla.srt'
$source=Join-Path (Split-Path $PSScriptRoot) 'plugin'
$support=Join-Path $env:PROGRAMDATA 'Blackmagic Design\DaVinci Resolve\Support'
if (!$PluginRoot) { $PluginRoot=Join-Path $support 'Workflow Integration Plugins' }
if (!$SdkPath) { $SdkPath=Join-Path $support 'Developer\Workflow Integrations\Examples\SamplePlugin\WorkflowIntegration.node' }
$PluginRoot=[IO.Path]::GetFullPath($PluginRoot)
$target=Join-Path $PluginRoot $id
$stage=Join-Path $PluginRoot ('.com.rambla.srt-stage-'+[guid]::NewGuid().ToString('N'))
$backupRoot=Join-Path (Split-Path $PluginRoot) 'RAMBLA SRT Install Backups'
$backup=Join-Path $backupRoot ([DateTime]::Now.ToString('yyyyMMdd-HHmmss')+'-'+[guid]::NewGuid().ToString('N'))
$moved=$false
if(!$OwnerSid){$OwnerSid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value}
if($OwnerSid -notmatch '^S-1-[0-9-]+$'){throw 'Identita utente non valida'}
function File-Hash([string]$file) { $sha=[Security.Cryptography.SHA256]::Create(); $stream=[IO.File]::OpenRead($file); try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','').ToLower() } finally { $stream.Dispose();$sha.Dispose() } }
function Assert-NoLink([string]$path) {
 $cursor=[IO.Path]::GetFullPath($path)
 while($cursor) {
  if(Test-Path -LiteralPath $cursor) { if((Get-Item -Force -LiteralPath $cursor).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Collegamento non consentito: $cursor" } }
  $parent=[IO.Path]::GetDirectoryName($cursor); if($parent -eq $cursor){break}; $cursor=$parent
 }
}
try {
 Assert-NoLink $PluginRoot; Assert-NoLink $source; Assert-NoLink $SdkPath
 if(!(Test-Path -LiteralPath $SdkPath -PathType Leaf)){throw 'SDK di Resolve Studio non trovato. Installa Resolve Studio dalla distribuzione Blackmagic.'}
 $hashes=Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'checksums.json') | ConvertFrom-Json
 $allowed=@('main.js','preload.js','resolve_adapter.js','core.js','session.js','updater.js','index.html','style.css','renderer.js','package.json','manifest.xml')
 if(@($hashes.PSObject.Properties).Count -ne $allowed.Count){throw 'Manifest installer incompleto'}
 foreach($name in $allowed){$file=Join-Path $source $name; Assert-NoLink $file; if(!(Test-Path -LiteralPath $file -PathType Leaf) -or (File-Hash $file) -ne $hashes.$name){throw "File mancante o danneggiato: $name"}}
 $incoming=Get-Content -Raw -LiteralPath (Join-Path $source 'package.json') | ConvertFrom-Json
 if($incoming.name -ne 'rambla-srt'){throw 'Pacchetto di un altro plugin'}
 Assert-NoLink $target
 if(Test-Path -LiteralPath $target){
  foreach($file in Get-ChildItem -LiteralPath $target -Force -Recurse){if($file.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Link trovato nel plugin esistente'}}
  $old=Get-Content -Raw -LiteralPath (Join-Path $target 'package.json') | ConvertFrom-Json
  if($old.name -ne 'rambla-srt'){throw 'Destinazione occupata da un altro programma'}
  if([version]$old.version -gt [version]$incoming.version){throw 'Versione installata più recente: downgrade annullato'}
 }
 try { New-Item -ItemType Directory -Force -Path $PluginRoot | Out-Null; New-Item -ItemType Directory -Path $stage | Out-Null }
 catch [System.UnauthorizedAccessException] {
  if($NoElevate){throw}
  if($PSCommandPath.Contains('"') -or $PluginRoot.Contains('"') -or $SdkPath.Contains('"')){throw 'Percorso non valido'}
  $arguments='-NoProfile -ExecutionPolicy Bypass -File "'+$PSCommandPath+'" -PluginRoot "'+$PluginRoot+'" -SdkPath "'+$SdkPath+'" -OwnerSid "'+$OwnerSid+'" -NoElevate'
  $child=Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -Verb RunAs -WindowStyle Hidden -Wait -PassThru
  exit $child.ExitCode
 }
 foreach($name in $allowed){Copy-Item -LiteralPath (Join-Path $source $name) -Destination (Join-Path $stage $name);if((File-Hash (Join-Path $stage $name)) -ne $hashes.$name){throw 'Verifica copia fallita'}}
 Copy-Item -LiteralPath $SdkPath -Destination (Join-Path $stage 'WorkflowIntegration.node')
 if((File-Hash $SdkPath) -ne (File-Hash (Join-Path $stage 'WorkflowIntegration.node'))){throw 'Verifica SDK fallita'}
 # Grant update access only on this staged plugin, including after UAC elevation.
 $acl=[IO.Directory]::GetAccessControl($stage)
 $rule=New-Object Security.AccessControl.FileSystemAccessRule((New-Object Security.Principal.SecurityIdentifier($OwnerSid)), 'Modify', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
 $acl.AddAccessRule($rule);[IO.Directory]::SetAccessControl($stage,$acl)
 if(Test-Path -LiteralPath $target){Assert-NoLink $backupRoot;New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null;Move-Item -LiteralPath $target -Destination $backup;$moved=$true}
 try { Move-Item -LiteralPath $stage -Destination $target } catch { if($moved){Move-Item -LiteralPath $backup -Destination $target};throw }
 $message="RAMBLA SRT $($incoming.version) installato.`nApri Workspace > Workflow Integrations > RAMBLA SRT.`nLa prima registrazione può richiedere il riavvio di Resolve.`nAutoCut e lo script Utility sono invariati."
 Write-Output $message
 if(!$Quiet){Add-Type -AssemblyName System.Windows.Forms;[Windows.Forms.MessageBox]::Show($message,'RAMBLA SRT') | Out-Null}
 exit 0
} catch {
 Write-Error -ErrorAction Continue $_
 if(!$Quiet){Add-Type -AssemblyName System.Windows.Forms;[Windows.Forms.MessageBox]::Show($_.Exception.Message,'RAMBLA SRT - installazione non completata') | Out-Null}
 exit 1
} finally {
 # Delete only our generated stage, after checking its absolute parent and name.
 if((Test-Path -LiteralPath $stage) -and [IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($stage)) -eq $PluginRoot -and [IO.Path]::GetFileName($stage).StartsWith('.com.rambla.srt-stage-')){Assert-NoLink $stage;Remove-Item -LiteralPath $stage -Recurse -Force}
}
