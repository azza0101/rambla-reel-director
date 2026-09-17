[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$branch = 'feat/curation-ui-v1'
$repo = 'azza0101/rambla-reel-director'
$scriptRoot = Split-Path -Parent $PSScriptRoot
$launcherPath = $MyInvocation.MyCommand.Path

# Non-git acceptance copies do not update this launcher when they download a
# fresh backend build. Refresh the launcher itself once, then re-exec so future
# feature wiring (server module, validation, env flags) cannot remain stale.
if ($env:RAMBLA_LAUNCHER_REFRESHED -ne '1' -and -not (Test-Path -LiteralPath (Join-Path $scriptRoot '.git'))) {
    $remoteLauncherPath = "repos/$repo/contents/tools/start_curation_acceptance.ps1?ref=$branch"
    $remoteLauncher = & gh api -H 'Accept: application/vnd.github.raw+json' $remoteLauncherPath 2>$null
    if ($LASTEXITCODE -eq 0 -and $remoteLauncher) {
        if ($remoteLauncher -is [array]) { $remoteLauncher = $remoteLauncher -join "`n" }
        $remoteLauncher = [string]$remoteLauncher
        $localLauncher = Get-Content -LiteralPath $launcherPath -Raw
        $remoteNormalized = $remoteLauncher -replace "`r`n", "`n"
        $localNormalized = $localLauncher -replace "`r`n", "`n"
        if ($remoteNormalized -ne $localNormalized) {
            [IO.File]::WriteAllText($launcherPath, $remoteLauncher, [Text.UTF8Encoding]::new($true))
            $env:RAMBLA_LAUNCHER_REFRESHED = '1'
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $launcherPath
            exit $LASTEXITCODE
        }
    }
}

$runtime = 'Z:\APP REEL TEST\qwen-embedding-smoke\editorial-intelligence-worktree\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runtime -PathType Leaf)) { throw "Scoped Python runtime not found: $runtime" }

# Playwright is intentionally NOT required to start the curation server.
# Social browser automation is loaded lazily only when a social action is used.

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
    } catch { Write-Warning "Previous acceptance server cleanup skipped: $($_.Exception.Message)" }
}

# Never block RAMBLA on one hard-coded local port. Pick the first free port in
# a small deterministic range and leave unrelated listeners completely alone.
$port = $null
foreach ($candidatePort in 8765..8799) {
    $probeListener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $candidatePort)
    try {
        $probeListener.Start()
        $port = $candidatePort
        break
    } catch {
    } finally {
        try { $probeListener.Stop() } catch {}
    }
}
if ($null -eq $port) { throw 'No free RAMBLA port found in 8765..8799' }
Write-Output "RAMBLA using local port $port"

$previousToken = $env:RAMBLA_BUILD_TOKEN
$previousVertical = $env:RAMBLA_ENABLE_VERTICAL_SOCIAL
$previousSocialBrowser = $env:RAMBLA_ENABLE_SOCIAL_BROWSER
$previousWebVideo = $env:RAMBLA_ENABLE_WEB_VIDEO
$previousBrowserProfileRoot = $env:RAMBLA_BROWSER_PROFILE_ROOT
$previousPythonPath = $env:PYTHONPATH
$browserProfileRoot = Join-Path (Split-Path -Parent $scriptRoot) 'browser-profiles'
New-Item -ItemType Directory -Force -Path $browserProfileRoot | Out-Null
$env:RAMBLA_BUILD_TOKEN = $shortSha
$env:RAMBLA_ENABLE_VERTICAL_SOCIAL = '1'
$env:RAMBLA_ENABLE_SOCIAL_BROWSER = '1'
$env:RAMBLA_ENABLE_WEB_VIDEO = '1'
$env:RAMBLA_BROWSER_PROFILE_ROOT = $browserProfileRoot
$env:PYTHONPATH = $workRoot
$importPath = $null
$serverLogDir = Join-Path $scriptRoot '.curation-logs'
New-Item -ItemType Directory -Force -Path $serverLogDir | Out-Null
$serverStdout = Join-Path $serverLogDir "server-$shortSha-$port.stdout.log"
$serverStderr = Join-Path $serverLogDir "server-$shortSha-$port.stderr.log"
Remove-Item -LiteralPath $serverStdout,$serverStderr -Force -ErrorAction SilentlyContinue
try {
    $importPath = (& $runtime -c "import backend.app.curation_server as m; print(m.__file__)").Trim()
    if ($LASTEXITCODE -ne 0 -or -not $importPath) { throw 'Import provenance verification failed: curation_server import failed' }
    $resolvedWorkRoot = (Resolve-Path -LiteralPath $workRoot).Path
    $resolvedImportPath = (Resolve-Path -LiteralPath $importPath).Path
    if (-not $resolvedImportPath.StartsWith($resolvedWorkRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Import provenance verification failed. Imported $resolvedImportPath instead of build under $resolvedWorkRoot"
    }
    $process = Start-Process -FilePath $runtime -ArgumentList '-m','uvicorn','backend.app.curation_server:app','--app-dir',$workRoot,'--host','127.0.0.1','--port',"$port" -WorkingDirectory $workRoot -WindowStyle Hidden -RedirectStandardOutput $serverStdout -RedirectStandardError $serverStderr -PassThru
} finally {
    $env:RAMBLA_BUILD_TOKEN = $previousToken
    $env:RAMBLA_ENABLE_VERTICAL_SOCIAL = $previousVertical
    $env:RAMBLA_ENABLE_SOCIAL_BROWSER = $previousSocialBrowser
    $env:RAMBLA_ENABLE_WEB_VIDEO = $previousWebVideo
    $env:RAMBLA_BROWSER_PROFILE_ROOT = $previousBrowserProfileRoot
    $env:PYTHONPATH = $previousPythonPath
}
$health = "http://127.0.0.1:$port/health"
$stamp = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$projectRoot = 'Z:\APP REEL TEST\qwen-embedding-smoke\kura-finto-etico-smoke\curation-projects'
$latestProjectId = $null
if (Test-Path -LiteralPath $projectRoot -PathType Container) {
    $latest = Get-ChildItem -LiteralPath $projectRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'project.json') -PathType Leaf } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($latest) { $latestProjectId = $latest.Name }
}
$query = "build=$shortSha&ts=$stamp"
if ($latestProjectId) { $query += "&project=$([Uri]::EscapeDataString($latestProjectId))" }
$url = "http://127.0.0.1:$port/curation?$query"
$ready = $false
foreach ($attempt in 1..40) {
    Start-Sleep -Milliseconds 250
    $process.Refresh()
    if ($process.HasExited) { break }
    try { if ((Invoke-RestMethod -Uri $health -TimeoutSec 2).status -eq 'ok') { $ready = $true; break } } catch {}
}
if (-not $ready) {
    $process.Refresh()
    $processState = if ($process.HasExited) { "exited with code $($process.ExitCode)" } else { 'still running' }
    Write-Output "Acceptance server process: PID $($process.Id) - $processState"
    if (Test-Path -LiteralPath $serverStdout -PathType Leaf) {
        Write-Output '----- SERVER STDOUT -----'
        Get-Content -LiteralPath $serverStdout -ErrorAction SilentlyContinue | Write-Output
    }
    if (Test-Path -LiteralPath $serverStderr -PathType Leaf) {
        Write-Output '----- SERVER STDERR -----'
        Get-Content -LiteralPath $serverStderr -ErrorAction SilentlyContinue | Write-Output
    }
    if (-not $process.HasExited) { Stop-Process -Id $process.Id -ErrorAction SilentlyContinue }
    throw "Acceptance server failed health check: $health"
}
$response = Invoke-WebRequest -Uri $url -UseBasicParsing -Headers @{'Cache-Control'='no-cache'}
if (-not $response.Content.Contains($marker)) { Stop-Process -Id $process.Id -ErrorAction SilentlyContinue; throw "Build marker verification failed. Expected: $marker" }
$requiredUiMarkers = @('id="projectsV2"','id="tiktokLoginV2"','id="instagramLoginV2"','id="beatActionsV2"','id="webNewsVideosV2"')
$missingUiMarkers = @($requiredUiMarkers | Where-Object { -not $response.Content.Contains($_) })
if ($missingUiMarkers.Count -gt 0) {
    Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
    throw "UI V2 verification failed. Missing markers: $($missingUiMarkers -join ', ')"
}
$record = @{pid=$process.Id;port=$port;url=$url;project_id=$latestProjectId;branch=$actualBranch;sha=$fullSha;short_sha=$shortSha;build_marker=$marker;browser_profile_root=$browserProfileRoot;module_path=$importPath;stdout_log=$serverStdout;stderr_log=$serverStderr;started_at=(Get-Date).ToString('o')}
$record | ConvertTo-Json | Set-Content -LiteralPath $recordPath -Encoding utf8
$record | Format-List
Write-Output "OPEN MANUALLY: $url"

$opened = $false
try {
    $browser = Start-Process $url -PassThru -ErrorAction Stop
    Start-Sleep -Milliseconds 750
    if ($browser.HasExited -and $browser.ExitCode -ne 0) { throw "Default browser exited with code $($browser.ExitCode)" }
    $opened = $true
} catch { Write-Warning "Default browser failed: $($_.Exception.Message)" }
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
