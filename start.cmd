@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" %*
if errorlevel 1 (
    echo.
    echo Meme Helper не был запущен.
    echo Исправьте указанную выше ошибку и повторите запуск.
    pause
)
