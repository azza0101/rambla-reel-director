Option Explicit
Dim shell, fso, root, pythonw, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = fso.BuildPath(fso.GetParentFolderName(root), "editorial-intelligence-worktree\.venv\Scripts\pythonw.exe")
If Not fso.FileExists(pythonw) Then
  MsgBox "Runtime RAMBLA non trovato: " & pythonw, vbCritical, "RAMBLA Reel Director"
  WScript.Quit 1
End If
command = """" & pythonw & """ """ & fso.BuildPath(root, "launch_local_v5.py") & """ start"
shell.Run command, 0, False
