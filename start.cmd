@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\python.ps1" run.py %*
if errorlevel 1 pause
