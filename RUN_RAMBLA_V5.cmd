@echo off
cd /d "%~dp0"
"%~dp0..\editorial-intelligence-worktree\.venv\Scripts\python.exe" "%~dp0launch_local_v5.py"
if errorlevel 1 pause
