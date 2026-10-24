param(
    [Parameter(Mandatory=$true)][string]$PluginRoot,
    [Parameter(Mandatory=$true)][string]$ArchivePath,
    [Parameter(Mandatory=$true)][string]$ExpectedSha256,
    [Parameter(Mandatory=$true)][string]$Version,
    [string]$ProgressPipe = '',
    [switch]$ValidateOnly
)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'

$script:progressClient=$null;$script:progressWriter=$null
if($ProgressPipe -and $ProgressPipe -notmatch '^premontato-update-[a-f0-9]{32}$'){throw 'Canale avanzamento non valido'}
function Send-UpdateProgress([string]$Phase,[int]$Current,[int]$Total){
 if(!$ProgressPipe){return}
 try{
  if(!$script:progressWriter){$script:progressClient=[IO.Pipes.NamedPipeClientStream]::new('.',$ProgressPipe,[IO.Pipes.PipeDirection]::Out);$script:progressClient.Connect(500);$script:progressWriter=[IO.StreamWriter]::new($script:progressClient,[Text.UTF8Encoding]::new($false));$script:progressWriter.AutoFlush=$true}
  $script:progressWriter.WriteLine((@{phase=$Phase;current=$Current;total=$Total}|ConvertTo-Json -Compress))
 }catch{if($script:progressClient){$script:progressClient.Dispose()};$script:progressWriter=$null;$script:progressClient=$null}
}
function Quote-Argument([string]$Value) { '"' + $Value.Replace('"','\"') + '"' }
function Get-TargetRelativePath([string]$Name) {
    $parts=$Name.Split('/')
    if($parts.Count -lt 2 -or $parts | Where-Object { $_ -in @('', '.', '..') -or $_ -match ':' }) { throw 'Percorso non consentito nel pacchetto' }
    $prefix=$parts[0];$leaf=($parts[1..($parts.Count-1)] -join '\')
    $pluginFiles=@('main.js','preload.js','resolve_adapter.js','session.js','ipc_security.js','index.html','style.css','renderer.js','updater.js','update.ps1','manifest.xml','package.json')
    $workerFiles=@('protocol.py','script_parser.py','transcript_align.py','edit_selector.py','pdf_script.py','shot_analyzer.py','cache.py','requirements.txt')
    if($prefix -eq 'plugin' -and $parts.Count -eq 2 -and $pluginFiles -contains $parts[1]) { return $leaf }
    if($prefix -eq 'worker' -and $parts.Count -eq 2 -and $workerFiles -contains $parts[1]) { return ('worker\'+$leaf) }
    if($prefix -eq 'runtime' -and $parts.Count -ge 2) { return ('runtime\'+$leaf) }
    throw 'File non consentito nel pacchetto aggiornamento'
}

$PluginRoot=[IO.Path]::GetFullPath($PluginRoot);$ArchivePath=[IO.Path]::GetFullPath($ArchivePath)
if((Split-Path -Leaf $PluginRoot) -ne 'com.rambla.premontato' -or !(Test-Path -LiteralPath (Join-Path $PluginRoot 'WorkflowIntegration.node') -PathType Leaf)) { throw 'Cartella Premontato o bridge Resolve non validi' }
if(!(Test-Path -LiteralPath $ArchivePath -PathType Leaf) -or $ExpectedSha256 -notmatch '^[a-f0-9]{64}$' -or $Version -notmatch '^\d+\.\d+\.\d+$') { throw 'Parametri aggiornamento non validi' }
if((Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedSha256.ToLowerInvariant()) { throw 'SHA-256 pacchetto non valido' }

Send-UpdateProgress 'validate' 0 1
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip=[IO.Compression.ZipFile]::OpenRead($ArchivePath)
$entries=@();$names=@{};$total=0L
try {
    foreach($entry in $zip.Entries) {
        if(!$entry.Name) { continue }
        $name=$entry.FullName.Replace('\','/')
        if($names.ContainsKey($name)) { throw 'File duplicato nel pacchetto aggiornamento' };$names[$name]=$true
        $relative=Get-TargetRelativePath $name
        $mode=($entry.ExternalAttributes -shr 16) -band 0xF000
        if($mode -eq 0xA000) { throw 'Collegamento simbolico non consentito nel pacchetto' }
        $total += $entry.Length
        if($total -gt 600MB) { throw 'Pacchetto aggiornamento troppo grande' }
        $entries += [pscustomobject]@{ArchiveName=$entry.FullName;Name=$name;Relative=$relative}
    }
    foreach($required in @('plugin/main.js','plugin/updater.js','plugin/update.ps1','plugin/package.json','worker/protocol.py','runtime/python.exe','runtime/THIRD_PARTY_NOTICES.txt')) {
        if(!$names.ContainsKey($required)) { throw ('File richiesto mancante: '+$required) }
    }
    if($ValidateOnly) { Write-Output ('Pacchetto valido: '+$Version+' · '+$entries.Count+' file');exit 0 }
} finally { $zip.Dispose() }

$identity=[Security.Principal.WindowsIdentity]::GetCurrent();$principal=[Security.Principal.WindowsPrincipal]::new($identity)
if(!$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $exe=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $argsList=@('-NoLogo','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$PSCommandPath,'-PluginRoot',$PluginRoot,'-ArchivePath',$ArchivePath,'-ExpectedSha256',$ExpectedSha256,'-Version',$Version)
    if($ProgressPipe){$argsList+=@('-ProgressPipe',$ProgressPipe)}
    $argLine=($argsList | ForEach-Object { Quote-Argument $_ }) -join ' '
    try { $process=Start-Process -FilePath $exe -ArgumentList $argLine -Verb RunAs -WindowStyle Hidden -PassThru -Wait;exit $process.ExitCode }
    catch { throw 'Richiesta di autorizzazione amministrativa annullata o non riuscita' }
}

$stage=Join-Path $PluginRoot ('.premontato-update-stage-'+[guid]::NewGuid().ToString('N'))
$backupRoot=Join-Path (Split-Path -Parent $PluginRoot) 'RAMBLA Premontato Update Backups'
$backup=Join-Path $backupRoot ([DateTime]::Now.ToString('yyyyMMdd-HHmmss-fff'))
$changed=New-Object 'System.Collections.Generic.List[object]'
try {
    New-Item -ItemType Directory -Path $stage | Out-Null
    $zip=[IO.Compression.ZipFile]::OpenRead($ArchivePath)
    try {
        $processed=0
        foreach($entry in $entries) {
            $archiveEntry=$zip.GetEntry($entry.ArchiveName)
            if(!$archiveEntry) { throw ('File non più presente nel pacchetto: '+$entry.Name) }
            $target=Join-Path $stage $entry.Relative
            $resolved=[IO.Path]::GetFullPath($target)
            if(!$resolved.StartsWith($stage+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Percorso estrazione fuori dalla cartella temporanea' }
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
            $input=$archiveEntry.Open();$output=[IO.File]::Open($target,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
            try { $input.CopyTo($output) } finally { $output.Dispose();$input.Dispose() }
            $processed++;if($processed % [Math]::Max(1,[Math]::Floor($entries.Count/100)) -eq 0 -or $processed -eq $entries.Count){Send-UpdateProgress 'extract' $processed $entries.Count}
        }
    } finally { $zip.Dispose() }
    $processed=0
    foreach($entry in $entries) {
        $source=Join-Path $stage $entry.Relative;$target=Join-Path $PluginRoot $entry.Relative
        $targetFull=[IO.Path]::GetFullPath($target)
        if(!$targetFull.StartsWith($PluginRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Destinazione fuori dal plugin' }
        $cursor=$targetFull
        while($cursor -and $cursor.StartsWith($PluginRoot,[StringComparison]::OrdinalIgnoreCase)) {
            if(Test-Path -LiteralPath $cursor) { if((Get-Item -Force -LiteralPath $cursor).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Collegamento nella cartella del plugin non consentito' } }
            $cursor=[IO.Path]::GetDirectoryName($cursor)
        }
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        $old=Test-Path -LiteralPath $target -PathType Leaf;$backupFile=$null
        if($old) { $backupFile=Join-Path $backup $entry.Relative;New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backupFile) | Out-Null }
        $changed.Add([pscustomobject]@{Target=$target;Backup=$backupFile;Existed=$old})
        $temporary=$target+'.premontato-update'
        Copy-Item -LiteralPath $source -Destination $temporary -Force
        if($old) { [IO.File]::Replace($temporary,$target,$backupFile) } else { [IO.File]::Move($temporary,$target) }
        $processed++;if($processed % [Math]::Max(1,[Math]::Floor($entries.Count/100)) -eq 0 -or $processed -eq $entries.Count){Send-UpdateProgress 'install' $processed $entries.Count}
    }
    Write-Output ('Premontato aggiornato a '+$Version+'. Chiudi e riapri il pannello per caricare la nuova versione.')
} catch {
    Send-UpdateProgress 'rollback' 0 1
    for($i=$changed.Count-1;$i -ge 0;$i--) {
        $item=$changed[$i]
        try { if($item.Existed -and (Test-Path -LiteralPath $item.Backup)) { $restore=$item.Target+'.premontato-restore';Copy-Item -LiteralPath $item.Backup -Destination $restore -Force;if(Test-Path -LiteralPath $item.Target){$rollbackBackup=$item.Target+'.premontato-rollback-'+[guid]::NewGuid().ToString('N');[IO.File]::Replace($restore,$item.Target,$rollbackBackup);Remove-Item -LiteralPath $rollbackBackup -Force}else{[IO.File]::Move($restore,$item.Target)} } elseif(!$item.Existed -and (Test-Path -LiteralPath $item.Target)){Remove-Item -LiteralPath $item.Target -Force} } catch {}
    }
    throw
} finally {
    if($script:progressWriter){$script:progressWriter.Dispose()};if($script:progressClient){$script:progressClient.Dispose()}
    if(Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
}
