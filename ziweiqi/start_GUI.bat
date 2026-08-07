@echo off
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8:replace"
set "PYTHONUNBUFFERED=1"
set "PYTHONPATH=%~dp0;%~dp0core"
start "" "pythonw.exe" "gui.pyw"
