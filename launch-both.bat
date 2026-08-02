@echo off
setlocal

set "panelPython=%~dp0seedsigner\.venv\Scripts\pythonw.exe"
set "panelScript=%~dp0control_panel.py"

if not exist "%panelPython%" (
    echo Missing Python environment: %panelPython%
    pause
    exit /b 1
)

if not exist "%panelScript%" (
    echo Missing control panel: %panelScript%
    pause
    exit /b 1
)

start "" "%panelPython%" "%panelScript%"
exit /b 0
