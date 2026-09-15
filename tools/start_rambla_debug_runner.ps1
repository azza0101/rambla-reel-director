$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$profile = $env:RAMBLA_DEBUG_COMMAND_FILE
if ([string]::IsNullOrWhiteSpace($profile)) {
    $profile = 'Z:\APP REEL TEST\qwen-embedding-smoke\debug-runner-command.json'
    $env:RAMBLA_DEBUG_COMMAND_FILE = $profile
}

if (-not (Test-Path -LiteralPath $profile)) {
    Write-Host "Profilo comando mancante: $profile" -ForegroundColor Yellow
    Write-Host 'ESEGUI restera non operativo finche il profilo locale non viene creato.' -ForegroundColor Yellow
}

$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "Python del worktree non trovato: $python"
}
$server = Start-Process -FilePath $python -ArgumentList @('-m','backend.app.debug_server') -PassThru -WindowStyle Hidden
try {
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 250
        try {
            $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 1
            if ($health.status -eq 'ok') { $ready = $true; break }
        } catch {}
    }
    if (-not $ready) { throw 'RAMBLA Debug Runner non risponde su http://127.0.0.1:8765' }
    Start-Process 'http://127.0.0.1:8765/debug'
    Write-Host "RAMBLA Debug Runner avviato (PID $($server.Id))." -ForegroundColor Green
} catch {
    if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    throw
}
