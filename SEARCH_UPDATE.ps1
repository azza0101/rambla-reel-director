param([string]$AppRoot = $PSScriptRoot, [string]$LocalReleaseDirectory, [switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
function Confirm-RMBLSoftwareUpdate {
    param([string]$CurrentVersion, [string]$TargetVersion)
    # An unowned MessageBox can hide behind PowerShell or DaVinci Resolve.
    # Use an explicit topmost modal with its own taskbar entry.
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $form = New-Object System.Windows.Forms.Form
    $form.Text = 'RMBL - SEARCH UPDATE'
    $form.Size = [System.Drawing.Size]::new(540, 245)
    $form.StartPosition = 'CenterScreen'
    $form.FormBorderStyle = 'FixedDialog'
    $form.MinimizeBox = $false
    $form.MaximizeBox = $false
    $form.ShowInTaskbar = $true
    $form.TopMost = $true
    $label = New-Object System.Windows.Forms.Label
    $label.Location = [System.Drawing.Point]::new(22, 20)
    $label.Size = [System.Drawing.Size]::new(485, 118)
    $label.Font = [System.Drawing.Font]::new('Segoe UI', 10)
    $label.Text = "RMBL B ROLL $CurrentVersion -> $TargetVersion" + [Environment]::NewLine +
        [Environment]::NewLine + 'Aggiornamento scaricato e verificato.' +
        [Environment]::NewLine + 'RMBL verra riavviato; Resolve rimane aperto.' +
        [Environment]::NewLine + 'Progetti, impostazioni e backup conservati.'
    $yes = New-Object System.Windows.Forms.Button
    $yes.Text = 'INSTALLA AGGIORNAMENTO'
    $yes.Location = [System.Drawing.Point]::new(240, 154)
    $yes.Size = [System.Drawing.Size]::new(262, 33)
    $yes.DialogResult = [System.Windows.Forms.DialogResult]::Yes
    $no = New-Object System.Windows.Forms.Button
    $no.Text = 'ANNULLA'
    $no.Location = [System.Drawing.Point]::new(22, 154)
    $no.Size = [System.Drawing.Size]::new(122, 33)
    $no.DialogResult = [System.Windows.Forms.DialogResult]::No
    $form.Controls.Add($label)
    $form.Controls.Add($yes)
    $form.Controls.Add($no)
    $form.AcceptButton = $yes
    $form.CancelButton = $no
    $form.Add_Shown({
        $form.BringToFront()
        $form.Activate()
    })
    try {
        return $form.ShowDialog()
    } finally {
        $form.Dispose()
    }
}

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
            Where-Object { $_ -match '^v[0-9]{4}$' } |
            Sort-Object { [int]($_.Substring(1)) } -Descending |
            Select-Object -First 1
        if (-not $latestTag) { throw 'Nessuna release B ROLL disponibile.' }
        & $gh release download $latestTag --repo azza0101/rambla-reel-director --pattern update.json --dir $stage
        if ($LASTEXITCODE -ne 0) { throw 'Manifest aggiornamento B ROLL non disponibile.' }
    }
    $manifest = Get-Content -LiteralPath (Join-Path $stage 'update.json') -Raw | ConvertFrom-Json
    if ($manifest.archive -notmatch '^RMBL-B-ROLL-Windows-v\d{4}\.zip$' -or $manifest.version -notmatch '^v\d{4}$') { throw 'Manifest non valido.' }
    if (-not $CheckOnly -and $manifest.version -le $current) {
        Write-Host "RMBL $current e gia aggiornato. Nessun download necessario."
        return
    }
    Write-Host "Versione installata: $current. Release disponibile: $($manifest.version)."
    Write-Host 'Scarico e verifico il pacchetto Windows (circa 150 MB)...'
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
    Write-Host 'PACCHETTO VERIFICATO. Apro la conferma in primo piano.'
    Write-Host 'Se non la vedi, usa ALT+TAB e cerca RMBL - SEARCH UPDATE.'
    $choice = Confirm-RMBLSoftwareUpdate -CurrentVersion $current -TargetVersion $manifest.version
    if ($choice -ne [System.Windows.Forms.DialogResult]::Yes) {
        Write-Host 'Aggiornamento annullato. Nessun dato modificato.'
        return
    }
    Write-Host 'Installazione confermata. Estraggo il pacchetto e avvio l installer...'
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
