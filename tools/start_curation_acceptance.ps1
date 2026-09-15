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
    $rootTree = (gh api "repos/$repo/git/trees/$($commit.tree.sha)" | ConvertFrom-Json).tree
    $backendSha = ($rootTree | Where-Object path -eq 'backend').sha
    if (-not $backendSha) { throw 'Remote backend tree not found' }
    $remoteFiles = @((gh api "repos/$repo/git/trees/$backendSha`?recursive=1" | ConvertFrom-Json).tree | Where-Object type -eq 'blob' | ForEach-Object { [pscustomobject]@{path="backend/$($_.path)";sha=$_.sha} })
    $remoteFiles += @($rootTree | Where-Object { $_.type -eq 'blob' -and $_.path -in @('pyproject.toml','debug-runner-command.json') })
    $workRoot = Join-Path $scriptRoot ".acceptance-builds\$fullSha-runtime"
    $complete = Join-Path $workRoot '.complete'
    if (-not (Test-Path -LiteralPath $complete)) {
        New-Item -ItemType Directory -Force -Path $workRoot | Out-Null
        foreach ($entry in $remoteFiles) {
            $target = Join-Path $workRoot $entry.path
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
            $encoded = $null
            foreach ($attempt in 1..3) {
                $blobText = & gh api "repos/$repo/git/blobs/$($entry.sha)" --jq .content
                if ($LASTEXITCODE -eq 0 -and $blobText) { $encoded = $blobText -replace '\s',''; break }
                Start-Sleep -Milliseconds (500 * $attempt)
            }
            if (-not $encoded) { throw "Remote blob download failed after 3 attempts: $($entry.path)" }
            [IO.File]::WriteAllBytes($target, [Convert]::FromBase64String($encoded))
            $actualBlob = (git hash-object --no-filters -- $target).Trim()
            if ($actualBlob -ne $entry.sha) { throw "Remote blob verification failed: $($entry.path)" }
        }
        Set-Content -LiteralPath $complete -Value $fullSha -Encoding ascii
    }
    $actualBranch = $branch
}

$shortSha = $fullSha.Substring(0, 7)
$marker = "CURATION-V1-build-$shortSha"

# Keep a stable browser origin so localStorage can reopen the last project across
# launcher restarts. Only stop the process recorded by our previous launcher and
# only when it is the same scoped Python runtime; never kill an unrelated process.
$recordPath = Join-Path $scriptRoot '.curation-acceptance-server.json'
if (Test-Path -LiteralPath $recordPath -PathType Leaf) {
    try {
        $old = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
        if ($old.pid) {
            $oldProcess = Get-Process -Id ([int]$old.pid) -ErrorAction SilentlyContinue
            if ($oldProcess -and $oldProcess.Path -eq $runtime) {
                Stop-Process -Id $oldProcess.Id -Force -ErrorAction Stop
                Wait-Process -Id $oldProcess.Id -Timeout 5 -ErrorAction SilentlyContinue
            }
        }
    } catch {
        Write-Warning "Previous acceptance server cleanup skipped: $($_.Exception.Message)"
    }
}

$port = 8765
$listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $port)
try { $listener.Start() }
catch { throw "Port 8765 is already in use by an unrelated process. Close it, then relaunch RAMBLA." }
finally { $listener.Stop() }

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
$record | ConvertTo-Json | Set-Content -LiteralPath $recordPath -Encoding utf8
$record | Format-List
Write-Output "OPEN MANUALLY: $url"

# Browser startup is convenience only. The verified server and recovery record
# remain authoritative even if a browser executable crashes or cannot start.
$opened = $false
try {
    $browser = Start-Process $url -PassThru -ErrorAction Stop
    Start-Sleep -Milliseconds 750
    if ($browser.HasExited -and $browser.ExitCode -ne 0) { throw "Default browser exited with code $($browser.ExitCode)" }
    $opened = $true
} catch {
    Write-Warning "Default browser failed: $($_.Exception.Message)"
}
if (-not $opened) {
    $edgeCandidates = @(
        (Get-Command msedge.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -Unique
    foreach ($edge in $edgeCandidates) {
        try { Start-Process -FilePath $edge -ArgumentList $url -ErrorAction Stop; $opened = $true; break }
        catch { Write-Warning "Edge fallback failed: $($_.Exception.Message)" }
    }
}
if (-not $opened) { Write-Warning "Browser could not be opened. Use the OPEN MANUALLY URL above." }
exit 0
