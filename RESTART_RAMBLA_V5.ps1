$ErrorActionPreference = 'Stop'
# Run explicitly after closing only RAMBLA's TikTok/Instagram windows.
# Normal launcher invocations intentionally reuse the connected server.
$ramblaRuntime = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\editorial-intelligence-worktree\.venv\Scripts\python.exe'))
$ramblaServers = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object {
    $_.ExecutablePath -eq $ramblaRuntime -and
    $_.CommandLine -match 'backend\.app\.curation_server:app' -and
    $_.CommandLine -match '--host\s+127\.0\.0\.1' -and
    $_.CommandLine -match '--port\s+881[0-9](?:\s|$)'
}
foreach ($ramblaServer in $ramblaServers) {
    Stop-Process -Id $ramblaServer.ProcessId
    Wait-Process -Id $ramblaServer.ProcessId -Timeout 10 -ErrorAction SilentlyContinue
}
& (Join-Path $PSScriptRoot 'RUN_RAMBLA_V5.cmd')
