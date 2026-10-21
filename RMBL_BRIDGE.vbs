Option Explicit
Dim shell, fso, root, pythonw, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = fso.BuildPath(root, ".venv\Scripts\pythonw.exe")
If Not fso.FileExists(pythonw) Then pythonw = fso.BuildPath(fso.GetParentFolderName(root), "editorial-intelligence-worktree\.venv\Scripts\pythonw.exe")
If Not fso.FileExists(pythonw) Then
  MsgBox "Runtime RMBL B ROLL non trovato. Esegui INSTALL_RMBL_B_ROLL.cmd.", vbCritical, "RMBL B ROLL"
  WScript.Quit 1
End If
command = """" & pythonw & """ """ & fso.BuildPath(root, "tools\resolve_bridge\standalone_bridge.py") & """"
shell.Run command, 0, False
