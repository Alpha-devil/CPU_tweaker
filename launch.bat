@echo off
:: Runs cpu_tray.py as Administrator silently
net session >nul 2>&1
if %errorLevel% == 0 (
    python cpu_tray.py
) else (
    powershell -Command "Start-Process python -ArgumentList 'cpu_tray.py' -Verb RunAs -WindowStyle Hidden"
)
