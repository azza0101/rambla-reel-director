[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$branch = 'feat/curation-ui-v1'
$repo = 'azza0101/rambla-reel-director'
$scriptRoot = Split-Path -Parent $PSScriptRoot
$runtime = 'Z:\APP REEL TEST\qwen-embedding-smoke\editorial-intelligence-worktree\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runtime -PathType Leaf)) { throw "Scoped Python runtime not found: $runtime" }

$workRoot = $scriptRoot
if (Test-Path -LiteralPath (Join-Path $scriptRoot '.git')) {
    $actualBranch = (git -C $scriptRoot branch --show-current).Trim()
    if ($actualBranch -ne $branch) { throw "Wrong branch: $actualBranch (expected $branch)" }
    $dirty = @(git -C $scriptRoot status --porcelain)
    if ($dirty.Count) { throw "Dirty worktree; aborting. Changed files:`n$($dirty -join "`n")" }
    git -C $scriptRoot fetch origin $branch
    if ($LASTEXITCODE) { throw 'git fetch failed' }
    git -C $scriptRoot merge --ff-only "origin/$branch"
    if ($LASTEXITCODE) { throw 'fast-forward-only update failed' }
    $fullSha = (git -C $scriptRoot rev-parse HEAD).Trim()
} else {
    # Codex's documented API-transport workspace has no .git metadata. Build an
    # isolated runtime from exact remote blobs; never trust or overwrite the mirror.
    $fullSha = (gh api "repos/$repo/git/ref/heads/$branch" --jq .object.sha).Trim()
    $commit = gh api "repos/$repo/git/commits/$fullSha" | ConvertFrom-Json
    $remoteFiles = (gh api "repos/$repo/git/trees/$($commit.tree.sha)?recursive=1" | ConvertFrom-Json).tree | Where-Object type -eq 'blob'
    $workRoot = Join-Path $scriptRoot ".acceptance-builds\$fullSha"
    $complete = Join-Path $workRoot '.complete'
    if (-not (Test-Path -LiteralPath $complete)) {
        New-Item -ItemType Directory -Force -Path $workRoot | Out-Null
        $runtimeFiles = $remoteFiles | Where-Object { $_.path -like 'backend/*' -or $_.path -eq 'pyproject.toml' -or $_.path -eq 'debug-runner-command.json' }
        foreach ($entry in $runtimeFiles) {
            $target = Join-Path $workRoot $entry.path
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
            $encoded = (gh api "repos/$repo/git/blobs/$($entry.sha)" --jq .content) -replace '\s',''
            [IO.File]::WriteAllBytes($target, [Convert]::FromBase64String($encoded))
        }
        Set-Content -LiteralPath $complete -Value $fullSha -Encoding ascii
    }
    $actualBranch = $branch
}

$shortSha = $fullSha.Substring(0, 7)
$marker = "CURATION V1 · build $shortSha"
$port = $null
foreach ($candidate in 8765..8799) {
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $candidate)
    try { $listener.Start(); $port = $candidate; break } catch {} finally { $listener.Stop() }
}
if (-not $port) { throw 'No free acceptance port in range 8765..8799' }

$previousToken = $env:RAMBLA_BUILD_TOKEN
$env:RAMBLA_BUILD_TOKEN = $shortSha
try {
    $process = Start-Process -FilePath $runtime -ArgumentList '-m','uvicorn','backend.app.debug_server:app','--host','127.0.0.1','--port',"$port" -WorkingDirectory $workRoot -WindowStyle Hidden -PassThru
} finally { $env:RAMBLA_BUILD_TOKEN = $previousToken }
$health = "http://127.0.0.1:$port/health"
$stamp = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$url = "http://127.0.0.1:$port/curation?build=$shortSha&ts=$stamp"
$ready = $false
foreach ($attempt in 1..40) {
    Start-Sleep -Milliseconds 250
    try { if ((Invoke-RestMethod -Uri $health -TimeoutSec 2).status -eq 'ok') { $ready = $true; break } } catch {}
}
if (-not $ready) { Stop-Process -Id $process.Id -ErrorAction SilentlyContinue; throw "Acceptance server failed health check: $health" }
$response = Invoke-WebRequest -Uri $url -UseBasicParsing -Headers @{'Cache-Control'='no-cache'}
if (-not $response.Content.Contains($marker)) { Stop-Process -Id $process.Id -ErrorAction SilentlyContinue; throw "Build marker verification failed. Expected: $marker" }
$record = @{pid=$process.Id;port=$port;url=$url;branch=$actualBranch;sha=$fullSha;short_sha=$shortSha;build_marker=$marker;started_at=(Get-Date).ToString('o')}
$record | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $scriptRoot '.curation-acceptance-server.json') -Encoding utf8
Start-Process $url
$record | Format-List
