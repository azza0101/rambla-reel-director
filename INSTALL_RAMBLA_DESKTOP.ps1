$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$launcher = Join-Path $root 'RAMBLA_REEL_DIRECTOR.vbs'
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'RAMBLA Reel Director.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $env:WINDIR 'System32\wscript.exe'
$shortcut.Arguments = '"' + $launcher + '"'
$shortcut.WorkingDirectory = $root
$shortcut.Description = 'RAMBLA Reel Director · Desktop API · GPU Free'
$shortcut.Save()
Write-Host "Collegamento creato: $shortcutPath"
