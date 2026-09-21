[CmdletBinding()]
param(
    [string]$RunDir = '',
    [switch]$Activate,
    [switch]$NoReuse
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$runtime = 'Z:\APP REEL TEST\qwen-embedding-smoke\editorial-intelligence-worktree\.venv\Scripts\python.exe'
$projectRoot = 'Z:\APP REEL TEST\qwen-embedding-smoke\kura-finto-etico-smoke\curation-projects'

if (-not (Test-Path -LiteralPath $runtime -PathType Leaf)) {
    throw "Scoped Python runtime not found: $runtime"
}

if (-not $RunDir) {
    if (-not (Test-Path -LiteralPath $projectRoot -PathType Container)) {
        throw "Curation project root not found: $projectRoot"
    }
    $latest = Get-ChildItem -LiteralPath $projectRoot -Directory -ErrorAction Stop |
        Where-Object {
            Test-Path -LiteralPath (Join-Path $_.FullName 'run\transcript-raw.json') -PathType Leaf
        } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $latest) {
        throw 'No analyzed curation project with transcript artifacts was found.'
    }
    $RunDir = Join-Path $latest.FullName 'run'
}

$RunDir = (Resolve-Path -LiteralPath $RunDir).Path
foreach ($required in @('transcript-raw.json','semantic-chunks.json','analysis-signature.json')) {
    $path = Join-Path $RunDir $required
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing V5 input artifact: $path"
    }
}

$envFile = Join-Path $repoRoot '.env.local'
$hasKey = [bool]$env:GEMINI_API_KEY
if (-not $hasKey -and (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    $hasKey = [bool](Select-String -LiteralPath $envFile -Pattern '^\s*GEMINI_API_KEY\s*=\s*\S+' -Quiet)
}
if (-not $hasKey) {
    throw "GEMINI_API_KEY is not configured. Add GEMINI_API_KEY=... to $envFile (do not paste the key into chat)."
}

$oldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = $repoRoot
try {
    Write-Output "Running focused V5 offline tests before any API call..."
    & $runtime -m pytest -q (Join-Path $repoRoot 'tests\unit\test_api_first_director.py')
    if ($LASTEXITCODE -ne 0) {
        throw "V5 offline tests failed with code $LASTEXITCODE. Gemini was not called."
    }
    Write-Output "Offline tests passed."
    Write-Output ""

    $argsList = @(
        '-m', 'backend.app.api_first_director_cli',
        '--run-dir', $RunDir,
        '--review'
    )
    if ($Activate) { $argsList += '--activate' }
    if ($NoReuse) { $argsList += '--no-reuse' }

    Write-Output "APP REEL V5 API-first probe"
    Write-Output "Run: $RunDir"
    Write-Output "Source video sent to AI: NO"
    Write-Output "Launching Director..."
    & $runtime @argsList
    if ($LASTEXITCODE -ne 0) {
        throw "V5 Director exited with code $LASTEXITCODE"
    }
} finally {
    $env:PYTHONPATH = $oldPythonPath
}

$review = Join-Path $RunDir 'api-first\ab-review.html'
$candidate = Join-Path $RunDir 'api-first\visual-plan.json'
$audit = Join-Path $RunDir 'api-first\director-run.json'
Write-Output ""
Write-Output "V5 candidate: $candidate"
Write-Output "Audit:        $audit"
if (Test-Path -LiteralPath $review -PathType Leaf) {
    Write-Output "A/B review:   $review"
    try { Start-Process $review | Out-Null } catch {
        Write-Warning "Could not open A/B review automatically: $($_.Exception.Message)"
    }
} else {
    Write-Warning 'A/B HTML was not generated. The V4 baseline visual-plan.json may be missing.'
}

if (-not $Activate) {
    Write-Output "SAFE MODE: the active V4 visual-plan.json was NOT replaced."
} else {
    Write-Warning "ACTIVATED: V5 plan is now the active visual-plan.json for this run."
}
