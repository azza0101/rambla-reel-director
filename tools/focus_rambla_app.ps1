param(
  [Parameter(Mandatory=$true)][string]$Url,
  [Parameter(Mandatory=$true)][string]$BrowserPath,
  [Parameter(Mandatory=$true)][string]$UserDataDir,
  [Parameter(Mandatory=$true)][string]$ProfileDirectory
)
$ErrorActionPreference = 'Stop'
$mutex = New-Object Threading.Mutex($false, 'Local\RAMBLA_BROLL_APP_LAUNCH')
try {
  $acquired = $false
  try { $acquired = $mutex.WaitOne(30000) }
  catch [Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'Another RAMBLA launch is still running; no additional window was opened.' }
  Add-Type @'
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Text;
using System.Runtime.InteropServices;
public static class RamblaWindow {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc p, IntPtr l);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint processId);
  [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr h, int n);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  public const uint WM_CLOSE=0x0010;
  public static bool IsRamblaTitle(string title) {
    // ASCII source is intentional: Windows PowerShell 5 reads BOM-less scripts as ANSI.
    return String.Equals(title.Trim(), "RMBL B ROLL", StringComparison.OrdinalIgnoreCase) || String.Equals(title.Trim(), "RAMBLA \u00b7 B-ROLL", StringComparison.OrdinalIgnoreCase);
  }
  public static IntPtr[] FindAll(string expectedProcess) {
    var found=new List<IntPtr>();
    EnumWindows((h,l)=>{ if(!IsWindowVisible(h)) return true; var s=new StringBuilder(512); GetWindowText(h,s,512); if(!IsRamblaTitle(s.ToString())) return true; uint pid; GetWindowThreadProcessId(h,out pid); try { if(!String.Equals(Process.GetProcessById((int)pid).ProcessName,expectedProcess,StringComparison.OrdinalIgnoreCase)) return true; } catch { return true; } found.Add(h);return true;},IntPtr.Zero);
    return found.ToArray();
  }
  public static void Close(IntPtr h) { PostMessage(h,WM_CLOSE,IntPtr.Zero,IntPtr.Zero); }
}
'@ -ErrorAction SilentlyContinue
  $expectedProcess=[IO.Path]::GetFileNameWithoutExtension($BrowserPath)
  $origin=([Uri]$Url).GetLeftPart([UriPartial]::Authority)
  $originPath=Join-Path $UserDataDir 'rambla-window-origin.txt'
  $savedOrigin=if(Test-Path $originPath){(Get-Content -LiteralPath $originPath -Raw).Trim()}else{''}
  $windows=@([RamblaWindow]::FindAll($expectedProcess))
  if($savedOrigin -and $savedOrigin -ne $origin) {
    foreach($old in $windows){[RamblaWindow]::Close($old)}
    Start-Sleep -Milliseconds 500
    $windows=@()
  }
  if($windows.Count -gt 1) {
    for($i=1;$i -lt $windows.Count;$i++){[RamblaWindow]::Close($windows[$i])}
  }
  if($windows.Count -gt 0) {
    $window=$windows[0]
    [void][RamblaWindow]::ShowWindowAsync($window,9)
    [void][RamblaWindow]::SetForegroundWindow($window)
    Set-Content -LiteralPath $originPath -Value $origin -NoNewline
    exit 0
  }
  $arguments=@("--user-data-dir=`"$UserDataDir`"","--profile-directory=`"$ProfileDirectory`"","--app=`"$Url`"","--start-maximized","--no-first-run")
  Start-Process -FilePath $BrowserPath -ArgumentList $arguments | Out-Null
  for($i=0;$i -lt 100;$i++){
    Start-Sleep -Milliseconds 100
    $windows=@([RamblaWindow]::FindAll($expectedProcess))
    if($windows.Count -gt 0){break}
  }
  if($windows.Count -gt 1){for($i=1;$i -lt $windows.Count;$i++){[RamblaWindow]::Close($windows[$i])}}
  Set-Content -LiteralPath $originPath -Value $origin -NoNewline
} finally {
  if ($acquired) { try { $mutex.ReleaseMutex() } catch {} }
  $mutex.Dispose()
}
