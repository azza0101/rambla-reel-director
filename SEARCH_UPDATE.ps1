param([string]$AppRoot = $PSScriptRoot, [string]$LocalReleaseDirectory, [switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$mutex = New-Object Threading.Mutex($false, 'Local\RMBLSoftwareUpdate')
if (-not $mutex.WaitOne(0)) { Write-Host 'Un aggiornamento e gia aperto.'; exit 0 }
try {
    $current = (Get-Content -LiteralPath (Join-Path $AppRoot 'RAMBLA_VERSION') -Raw).Trim()
    $stage = Join-Path ([IO.Path]::GetTempPath()) ('rmbl-update-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stage | Out-Null
    if ($LocalReleaseDirectory) {
        Copy-Item -LiteralPath (Join-Path $LocalReleaseDirectory 'update.json') -Destination $stage
    } else {
        $gh = Join-Path $AppRoot 'runtime\bin\gh.exe'
        if (-not (Test-Path -LiteralPath $gh)) { $gh = (Get-Command gh.exe -ErrorAction Stop).Source }
        & $gh auth status --hostname github.com
        if ($LASTEXITCODE -ne 0) {
            if ($CheckOnly) { throw 'Accesso GitHub necessario.' }
            Write-Host 'Accedi a GitHub con un account autorizzato al repository privato RMBL.'
            & $gh auth login --hostname github.com --web --git-protocol https
            if ($LASTEXITCODE -ne 0) { throw 'Accesso GitHub non completato.' }
        }
        Write-Host 'Controllo ultima release RMBL B ROLL...'
        # Repository hosts Omni-Cut and Premontato too: never select their
        # latest release when checking B ROLL updates.
        $tags = @(& $gh release list --repo azza0101/rambla-reel-director --limit 300 --json tagName --jq '.[].tagName')
        if ($LASTEXITCODE -ne 0) { throw 'Impossibile leggere le release GitHub.' }
        $latestTag = $tags |
            Where-Object { $_ -match '^v[0-9]{4} = Get-Content -LiteralPath (Join-Path $stage 'update.json') -Raw | ConvertFrom-Json
    if ($manifest.archive -notmatch '^RMBL-B-ROLL-Windows-v\d{4}\.zip$' -or $manifest.version -notmatch '^v\d{4}$') { throw 'Manifest non valido.' }
    if ($LocalReleaseDirectory) {
        Copy-Item -LiteralPath (Join-Path $LocalReleaseDirectory $manifest.archive) -Destination $stage
    } else {
        & $gh release download $manifest.version --repo azza0101/rambla-reel-director --pattern $manifest.archive --dir $stage
        if ($LASTEXITCODE -ne 0) { throw 'Download non completato.' }
    }
    $python = Join-Path $AppRoot '.venv\Scripts\python.exe'
    & $python (Join-Path $AppRoot 'tools\verify_update_archive.py') (Join-Path $stage $manifest.archive) (Join-Path $stage 'update.json')
    if ($LASTEXITCODE -ne 0) { throw 'Verifica pacchetto fallita. Nessun aggiornamento applicato.' }
    if ($CheckOnly) { Write-Host "CHECK OK: $current -> $($manifest.version)"; return }
    if ($manifest.version -le $current) { Write-Host "RMBL $current e aggiornato."; return }
    Add-Type -AssemblyName PresentationFramework
    $choice = [Windows.MessageBox]::Show("Aggiornare RMBL da $current a $($manifest.version)?`n`nAttendi la fine delle elaborazioni. RMBL verra riavviato; Resolve resta aperto. Progetti e impostazioni sono conservati.", 'RMBL - SEARCH UPDATE', 'YesNo', 'Question')
    if ($choice -ne 'Yes') { return }
    $payload = Join-Path $stage 'payload'
    Expand-Archive -LiteralPath (Join-Path $stage $manifest.archive) -DestinationPath $payload
    $record = Join-Path (Split-Path -Parent $AppRoot) 'rambla-data\desktop-runtime.json'
    if (Test-Path -LiteralPath $record) {
        $runtime = Get-Content -LiteralPath $record -Raw | ConvertFrom-Json
        $base = ([Uri]$runtime.url).GetLeftPart([UriPartial]::Authority)
        $busy = $null
        try { $busy = Invoke-RestMethod -Uri "$base/api/curation/software-update/status" -TimeoutSec 4 } catch { }
        if ($busy.busy) { throw 'Elaborazione attiva: riprova quando termina.' }
    }
    & $python (Join-Path $AppRoot 'launch_local_v5.py') stop
    if ($LASTEXITCODE -ne 0) { throw 'Impossibile arrestare RMBL in sicurezza.' }
    try {
        & (Join-Path $payload 'INSTALL_RMBL_B_ROLL.ps1') -InstallRoot $AppRoot -ForceUpdate
    } finally {
        & $python (Join-Path $AppRoot 'launch_local_v5.py') start
    }
    Write-Host 'Aggiornamento completato. Il bridge carica la nuova versione quando libero.'
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host 'Progetti conservati. Backup del codice in install-backups.'
    if ($CheckOnly) { exit 1 }
} finally {
    $mutex.ReleaseMutex(); $mutex.Dispose()
    if (-not $CheckOnly) { Read-Host 'Premi INVIO per chiudere' }
}
 } |
            Sort-Object { [int]($_.Substring(1)) } -Descending | Select-Object -First 1
        if (-not $latestTag) { throw 'Nessuna release RMBL B ROLL trovata.' }
        & $gh release download $latestTag --repo azza0101/rambla-reel-director --pattern update.json --dir $stage
        if ($LASTEXITCODE -ne 0) { throw 'Release B ROLL non disponibile o account senza accesso.' }
    }
    $manifest = Get-Content -LiteralPath (Join-Path $stage 'update.json') -Raw | ConvertFrom-Json
    if ($manifest.archive -notmatch '^RMBL-B-ROLL-Windows-v\d{4}\.zip$' -or $manifest.version -notmatch '^v\d{4}$') { throw 'Manifest non valido.' }
    if ($LocalReleaseDirectory) {
        Copy-Item -LiteralPath (Join-Path $LocalReleaseDirectory $manifest.archive) -Destination $stage
    } else {
        & $gh release download $manifest.version --repo azza0101/rambla-reel-director --pattern $manifest.archive --dir $stage
        if ($LASTEXITCODE -ne 0) { throw 'Download non completato.' }
    }
    $python = Join-Path $AppRoot '.venv\Scripts\python.exe'
    & $python (Join-Path $AppRoot 'tools\verify_update_archive.py') (Join-Path $stage $manifest.archive) (Join-Path $stage 'update.json')
    if ($LASTEXITCODE -ne 0) { throw 'Verifica pacchetto fallita. Nessun aggiornamento applicato.' }
    if ($CheckOnly) { Write-Host "CHECK OK: $current -> $($manifest.version)"; return }
    if ($manifest.version -le $current) { Write-Host "RMBL $current e aggiornato."; return }
    Add-Type -AssemblyName PresentationFramework
    $choice = [Windows.MessageBox]::Show("Aggiornare RMBL da $current a $($manifest.version)?`n`nAttendi la fine delle elaborazioni. RMBL verra riavviato; Resolve resta aperto. Progetti e impostazioni sono conservati.", 'RMBL - SEARCH UPDATE', 'YesNo', 'Question')
    if ($choice -ne 'Yes') { return }
    $payload = Join-Path $stage 'payload'
    Expand-Archive -LiteralPath (Join-Path $stage $manifest.archive) -DestinationPath $payload
    $record = Join-Path (Split-Path -Parent $AppRoot) 'rambla-data\desktop-runtime.json'
    if (Test-Path -LiteralPath $record) {
        $runtime = Get-Content -LiteralPath $record -Raw | ConvertFrom-Json
        $base = ([Uri]$runtime.url).GetLeftPart([UriPartial]::Authority)
        $busy = $null
        try { $busy = Invoke-RestMethod -Uri "$base/api/curation/software-update/status" -TimeoutSec 4 } catch { }
        if ($busy.busy) { throw 'Elaborazione attiva: riprova quando termina.' }
    }
    & $python (Join-Path $AppRoot 'launch_local_v5.py') stop
    if ($LASTEXITCODE -ne 0) { throw 'Impossibile arrestare RMBL in sicurezza.' }
    try {
        & (Join-Path $payload 'INSTALL_RMBL_B_ROLL.ps1') -InstallRoot $AppRoot -ForceUpdate
    } finally {
        & $python (Join-Path $AppRoot 'launch_local_v5.py') start
    }
    Write-Host 'Aggiornamento completato. Il bridge carica la nuova versione quando libero.'
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host 'Progetti conservati. Backup del codice in install-backups.'
    if ($CheckOnly) { exit 1 }
} finally {
    $mutex.ReleaseMutex(); $mutex.Dispose()
    if (-not $CheckOnly) { Read-Host 'Premi INVIO per chiudere' }
}
 } |
            Sort-Object { [int]($_.Substring(1)) } -Descending |
            Select-Object -First 1
        if (-not $latestTag) { throw 'Nessuna release B ROLL disponibile.' }
        & $gh release download $latestTag --repo azza0101/rambla-reel-director --pattern update.json --dir $stage
        if ($LASTEXITCODE -ne 0) { throw 'Manifest aggiornamento B ROLL non disponibile.' }
    }
    $manifest = Get-Content -LiteralPath (Join-Path $stage 'update.json') -Raw | ConvertFrom-Json
    if ($manifest.archive -notmatch '^RMBL-B-ROLL-Windows-v\d{4}\.zip$' -or $manifest.version -notmatch '^v\d{4}$') { throw 'Manifest non valido.' }
    if ($LocalReleaseDirectory) {
        Copy-Item -LiteralPath (Join-Path $LocalReleaseDirectory $manifest.archive) -Destination $stage
    } else {
        & $gh release download $manifest.version --repo azza0101/rambla-reel-director --pattern $manifest.archive --dir $stage
        if ($LASTEXITCODE -ne 0) { throw 'Download non completato.' }
    }
    $python = Join-Path $AppRoot '.venv\Scripts\python.exe'
    & $python (Join-Path $AppRoot 'tools\verify_update_archive.py') (Join-Path $stage $manifest.archive) (Join-Path $stage 'update.json')
    if ($LASTEXITCODE -ne 0) { throw 'Verifica pacchetto fallita. Nessun aggiornamento applicato.' }
    if ($CheckOnly) { Write-Host "CHECK OK: $current -> $($manifest.version)"; return }
    if ($manifest.version -le $current) { Write-Host "RMBL $current e aggiornato."; return }
    Add-Type -AssemblyName PresentationFramework
    $choice = [Windows.MessageBox]::Show("Aggiornare RMBL da $current a $($manifest.version)?`n`nAttendi la fine delle elaborazioni. RMBL verra riavviato; Resolve resta aperto. Progetti e impostazioni sono conservati.", 'RMBL - SEARCH UPDATE', 'YesNo', 'Question')
    if ($choice -ne 'Yes') { return }
    $payload = Join-Path $stage 'payload'
    Expand-Archive -LiteralPath (Join-Path $stage $manifest.archive) -DestinationPath $payload
    $record = Join-Path (Split-Path -Parent $AppRoot) 'rambla-data\desktop-runtime.json'
    if (Test-Path -LiteralPath $record) {
        $runtime = Get-Content -LiteralPath $record -Raw | ConvertFrom-Json
        $base = ([Uri]$runtime.url).GetLeftPart([UriPartial]::Authority)
        $busy = $null
        try { $busy = Invoke-RestMethod -Uri "$base/api/curation/software-update/status" -TimeoutSec 4 } catch { }
        if ($busy.busy) { throw 'Elaborazione attiva: riprova quando termina.' }
    }
    & $python (Join-Path $AppRoot 'launch_local_v5.py') stop
    if ($LASTEXITCODE -ne 0) { throw 'Impossibile arrestare RMBL in sicurezza.' }
    try {
        & (Join-Path $payload 'INSTALL_RMBL_B_ROLL.ps1') -InstallRoot $AppRoot -ForceUpdate
    } finally {
        & $python (Join-Path $AppRoot 'launch_local_v5.py') start
    }
    Write-Host 'Aggiornamento completato. Il bridge carica la nuova versione quando libero.'
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host 'Progetti conservati. Backup del codice in install-backups.'
    if ($CheckOnly) { exit 1 }
} finally {
    $mutex.ReleaseMutex(); $mutex.Dispose()
    if (-not $CheckOnly) { Read-Host 'Premi INVIO per chiudere' }
}
 } |
            Sort-Object { [int]($_.Substring(1)) } -Descending | Select-Object -First 1
        if (-not $latestTag) { throw 'Nessuna release RMBL B ROLL trovata.' }
        & $gh release download $latestTag --repo azza0101/rambla-reel-director --pattern update.json --dir $stage
        if ($LASTEXITCODE -ne 0) { throw 'Release B ROLL non disponibile o account senza accesso.' }
    }
    $manifest = Get-Content -LiteralPath (Join-Path $stage 'update.json') -Raw | ConvertFrom-Json
    if ($manifest.archive -notmatch '^RMBL-B-ROLL-Windows-v\d{4}\.zip$' -or $manifest.version -notmatch '^v\d{4}$') { throw 'Manifest non valido.' }
    if ($LocalReleaseDirectory) {
        Copy-Item -LiteralPath (Join-Path $LocalReleaseDirectory $manifest.archive) -Destination $stage
    } else {
        & $gh release download $manifest.version --repo azza0101/rambla-reel-director --pattern $manifest.archive --dir $stage
        if ($LASTEXITCODE -ne 0) { throw 'Download non completato.' }
    }
    $python = Join-Path $AppRoot '.venv\Scripts\python.exe'
    & $python (Join-Path $AppRoot 'tools\verify_update_archive.py') (Join-Path $stage $manifest.archive) (Join-Path $stage 'update.json')
    if ($LASTEXITCODE -ne 0) { throw 'Verifica pacchetto fallita. Nessun aggiornamento applicato.' }
    if ($CheckOnly) { Write-Host "CHECK OK: $current -> $($manifest.version)"; return }
    if ($manifest.version -le $current) { Write-Host "RMBL $current e aggiornato."; return }
    Add-Type -AssemblyName PresentationFramework
    $choice = [Windows.MessageBox]::Show("Aggiornare RMBL da $current a $($manifest.version)?`n`nAttendi la fine delle elaborazioni. RMBL verra riavviato; Resolve resta aperto. Progetti e impostazioni sono conservati.", 'RMBL - SEARCH UPDATE', 'YesNo', 'Question')
    if ($choice -ne 'Yes') { return }
    $payload = Join-Path $stage 'payload'
    Expand-Archive -LiteralPath (Join-Path $stage $manifest.archive) -DestinationPath $payload
    $record = Join-Path (Split-Path -Parent $AppRoot) 'rambla-data\desktop-runtime.json'
    if (Test-Path -LiteralPath $record) {
        $runtime = Get-Content -LiteralPath $record -Raw | ConvertFrom-Json
        $base = ([Uri]$runtime.url).GetLeftPart([UriPartial]::Authority)
        $busy = $null
        try { $busy = Invoke-RestMethod -Uri "$base/api/curation/software-update/status" -TimeoutSec 4 } catch { }
        if ($busy.busy) { throw 'Elaborazione attiva: riprova quando termina.' }
    }
    & $python (Join-Path $AppRoot 'launch_local_v5.py') stop
    if ($LASTEXITCODE -ne 0) { throw 'Impossibile arrestare RMBL in sicurezza.' }
    try {
        & (Join-Path $payload 'INSTALL_RMBL_B_ROLL.ps1') -InstallRoot $AppRoot -ForceUpdate
    } finally {
        & $python (Join-Path $AppRoot 'launch_local_v5.py') start
    }
    Write-Host 'Aggiornamento completato. Il bridge carica la nuova versione quando libero.'
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host 'Progetti conservati. Backup del codice in install-backups.'
    if ($CheckOnly) { exit 1 }
} finally {
    $mutex.ReleaseMutex(); $mutex.Dispose()
    if (-not $CheckOnly) { Read-Host 'Premi INVIO per chiudere' }
}
