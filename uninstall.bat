@echo off
echo ================================================
echo  CPU Power Control -- Uninstaller
echo ================================================
echo.

:: Must be admin to remove kernel service
net session >nul 2>&1
if not %errorLevel% == 0 (
    echo Requesting Administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Step 1 -- Kill running instance
echo [1/5] Stopping running instance...
taskkill /f /im python.exe /fi "WINDOWTITLE eq CPU Power Control" >nul 2>&1
taskkill /f /fi "IMAGENAME eq python.exe" >nul 2>&1
echo       Done.

:: Step 2 -- Stop and remove WinRing0 kernel service
echo [2/5] Removing WinRing0 kernel driver service...
sc stop WinRing0_1_2_0 >nul 2>&1
sc delete WinRing0_1_2_0 >nul 2>&1
sc stop WinRing0x64_1_2_0 >nul 2>&1
sc delete WinRing0x64_1_2_0 >nul 2>&1
echo       Done.

:: Step 3 -- Restore default Turbo Boost (re-enable)
echo [3/5] Restoring default Turbo Boost (re-enabling)...
powercfg /setacvalueindex SCHEME_CURRENT SUB_PROCESSOR PERFBOOSTMODE 2 >nul 2>&1
powercfg /setdcvalueindex SCHEME_CURRENT SUB_PROCESSOR PERFBOOSTMODE 2 >nul 2>&1
powercfg /setactive SCHEME_CURRENT >nul 2>&1
echo       Done.

:: Step 4 -- Remove startup shortcut if it exists
echo [4/5] Removing startup entry (if any)...
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
if exist "%STARTUP%\launch.bat.lnk" del /f "%STARTUP%\launch.bat.lnk" >nul 2>&1
if exist "%STARTUP%\cpu_tray.lnk"   del /f "%STARTUP%\cpu_tray.lnk"   >nul 2>&1
echo       Done.

:: Step 5 -- Uninstall Python packages
echo [5/5] Uninstalling Python packages (pystray, Pillow, psutil)...
pip uninstall pystray Pillow psutil -y >nul 2>&1
echo       Done.

echo.
echo ================================================
echo  Uninstall complete.
echo  You can now safely delete this folder.
echo ================================================
echo.
pause
