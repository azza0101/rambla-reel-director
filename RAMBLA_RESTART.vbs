Option Explicit
Dim shell, fso, root, pythonw, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = fso.BuildPath(fso.GetParentFolderName(root), "editorial-intelligence-worktree\.venv\Scripts\pythonw.exe")
command = """" & pythonw & """ """ & fso.BuildPath(root, "launch_local_v5.py") & """ restart"
shell.Run command, 0, False
