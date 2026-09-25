$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repoRoot ".env.local"

Write-Host ""
Write-Host "APP REEL - Pexels API setup"
Write-Host "Paste the PEXELS_API_KEY. Characters will stay hidden."
$secure = Read-Host "PEXELS_API_KEY" -AsSecureString

$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $pexelsKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}

if ([string]::IsNullOrWhiteSpace($pexelsKey)) {
    throw "PEXELS_API_KEY is empty"
}

$lines = @()
if (Test-Path -LiteralPath $envFile) {
    $lines = @(
        Get-Content -LiteralPath $envFile |
        Where-Object { $_ -notmatch '^\s*PEXELS_API_KEY\s*=' }
    )
}

$lines += "PEXELS_API_KEY=$pexelsKey"
[IO.File]::WriteAllLines(
    $envFile,
    $lines,
    [Text.UTF8Encoding]::new($false)
)

$pexelsKey = $null
Write-Host ""
Write-Host "Pexels configured locally in:"
Write-Host $envFile
Write-Host "The key was not printed and is not committed to Git."
