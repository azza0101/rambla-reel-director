<#
Run from any PowerShell window:

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "Z:\APP REEL TEST\qwen-embedding-smoke\api-first-v5-cloud\SETUP_REVISIONE_ONLINE.ps1"

Google requires the account owner to approve and deploy the Web App. This
script automates every local step and guides those unavoidable browser clicks.
#>
param(
    [string]$WebAppUrl = "",
    [switch]$Force,
    [switch]$SkipBrowser,
    [switch]$SkipRestart
)

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot
$envFile = Join-Path $repoRoot ".env.local"
$codeFile = Join-Path $repoRoot "tools\google_apps_script_review_bridge\Code.gs"
$appsScriptNew = "https://script.google.com/home/projects/create"

function Get-LocalSetting([string]$Name) {
    if (-not (Test-Path -LiteralPath $envFile)) { return "" }
    $line = Get-Content -LiteralPath $envFile | Where-Object { $_ -match ("^\s*" + [regex]::Escape($Name) + "\s*=") } | Select-Object -Last 1
    if (-not $line) { return "" }
    return ($line -replace "^[^=]*=", "").Trim().Trim('"').Trim("'")
}

function Set-LocalSetting([string]$Name, [string]$Value) {
    $lines = @()
    if (Test-Path -LiteralPath $envFile) {
        $lines = @(Get-Content -LiteralPath $envFile | Where-Object { $_ -notmatch ("^\s*" + [regex]::Escape($Name) + "\s*=") })
    }
    $lines += "$Name=$Value"
    [IO.File]::WriteAllLines($envFile, $lines, [Text.UTF8Encoding]::new($false))
}

function New-OwnerSecret {
    $bytes = New-Object byte[] 32
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function Assert-WebAppUrl([string]$Value) {
    $candidate = $Value.Trim()
    if ($candidate -notmatch '^https://script\.google\.com/macros/s/[^/]+/exec(?:\?.*)?$') {
        throw "URL non valido. Copia l'URL distribuito che termina con /exec, non quello di test /dev."
    }
    return $candidate
}

function Restart-And-Verify {
    if ($SkipRestart) {
        Write-Host "Configurazione salvata. Riavvia RAMBLA quando vuoi." -ForegroundColor Yellow
        return
    }
    $python = Join-Path (Split-Path -Parent $repoRoot) "editorial-intelligence-worktree\.venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) { throw "Runtime RAMBLA non trovato: $python" }
    Write-Host ""
    Write-Host "Riavvio RAMBLA e verifico il collegamento..." -ForegroundColor Cyan
    $launchOutput = (& $python (Join-Path $repoRoot "launch_local_v5.py") restart 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw "Riavvio RAMBLA fallito: $launchOutput" }
    $match = [regex]::Match($launchOutput, 'http://127\.0\.0\.1:\d+/curation[^\s]*')
    if (-not $match.Success) { throw "RAMBLA avviato ma URL locale non trovato: $launchOutput" }
    $ramblaUrl = $match.Value
    $page = Invoke-WebRequest -UseBasicParsing -Uri $ramblaUrl -TimeoutSec 15
    if ($page.StatusCode -ne 200 -or $page.Content -notmatch 'publishReviewV19') {
        throw "RAMBLA risponde, ma il modulo Revisione online non risulta disponibile."
    }
    Write-Host ""
    Write-Host "CONFIGURAZIONE COMPLETATA" -ForegroundColor Green
    Write-Host "RAMBLA: $ramblaUrl"
    Write-Host "Apri un progetto analizzato e premi CREA LINK REVISIONE."
}

if (-not (Test-Path -LiteralPath $codeFile)) { throw "File Apps Script mancante: $codeFile" }

$ownerSecret = Get-LocalSetting "RAMBLA_REVIEW_OWNER_SECRET"
if ([string]::IsNullOrWhiteSpace($ownerSecret)) {
    $ownerSecret = New-OwnerSecret
    Set-LocalSetting "RAMBLA_REVIEW_OWNER_SECRET" $ownerSecret
}

$savedUrl = Get-LocalSetting "RAMBLA_REVIEW_WEBAPP_URL"
if (-not $Force -and [string]::IsNullOrWhiteSpace($WebAppUrl) -and -not [string]::IsNullOrWhiteSpace($savedUrl)) {
    $null = Assert-WebAppUrl $savedUrl
    Write-Host "Il ponte di revisione e gia configurato in .env.local." -ForegroundColor Green
    Restart-And-Verify
    exit 0
}

if ([string]::IsNullOrWhiteSpace($WebAppUrl)) {
    $code = Get-Content -LiteralPath $codeFile -Raw -Encoding UTF8
    Set-Clipboard -Value $code
    Write-Host ""
    Write-Host "RAMBLA - CONFIGURAZIONE REVISIONE ONLINE" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "PASSO 1 DI 3" -ForegroundColor Yellow
    Write-Host "Ho copiato negli appunti tutto Code.gs."
    Write-Host "Nel progetto Google appena aperto: seleziona il codice presente, incolla e salva."
    if (-not $SkipBrowser) { Start-Process $appsScriptNew }
    else { Write-Host "Apri: $appsScriptNew" }
    $null = Read-Host "Dopo avere incollato e salvato il codice, premi INVIO qui"

    Set-Clipboard -Value $ownerSecret
    Write-Host ""
    Write-Host "PASSO 2 DI 3" -ForegroundColor Yellow
    Write-Host "Ho copiato il segreto negli appunti senza mostrarlo."
    Write-Host "In Impostazioni progetto > Proprieta script aggiungi:"
    Write-Host "  Nome:  RAMBLA_OWNER_SECRET"
    Write-Host "  Valore: incolla dagli appunti"
    Write-Host "Salva la proprieta."
    $null = Read-Host "Dopo avere salvato la proprieta, premi INVIO qui"

    Write-Host ""
    Write-Host "PASSO 3 DI 3" -ForegroundColor Yellow
    Write-Host "In Google premi Distribuisci > Nuova distribuzione > Applicazione web."
    Write-Host "Esegui come: te stesso. Accesso: chiunque debba usare il link."
    Write-Host "Autorizza, completa la distribuzione e COPIA l'URL che termina con /exec."
    $null = Read-Host "Quando l'URL /exec e negli appunti, premi INVIO qui"
    $clipboardUrl = (Get-Clipboard -Raw).Trim()
    if ($clipboardUrl -match 'https://script\.google\.com/macros/s/[^\s]+/exec(?:\?[^\s]*)?') {
        $WebAppUrl = $Matches[0]
    } else {
        $WebAppUrl = Read-Host "Incolla qui l'URL /exec"
    }
}

$WebAppUrl = Assert-WebAppUrl $WebAppUrl
Set-LocalSetting "RAMBLA_REVIEW_WEBAPP_URL" $WebAppUrl
Set-LocalSetting "RAMBLA_REVIEW_OWNER_SECRET" $ownerSecret

Write-Host ""
Write-Host "URL e segreto salvati localmente in .env.local." -ForegroundColor Green
Write-Host "Il segreto non e stato stampato e non viene inserito in Git."
Restart-And-Verify
