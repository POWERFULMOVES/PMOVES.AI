# Quick Start Script - Complete Media Collection
# Run this to initialize everything

@echo off
echo ========================================
echo YouTube Complete Media Collection Setup
echo ========================================
echo.

set CONFIG_DIR=C:\Users\russe\yt-dlp-config
set PYTHON_SCRIPT=%CONFIG_DIR%\tracker.py

echo [1/5] Creating directories...
if not exist "E:\Downloads\yt-dlp\complete" mkdir "E:\Downloads\yt-dlp\complete"
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"

echo [2/5] Installing Python for tracker...
winget install --id Python.Python.3.11 --source winget --accept-package-agreements --accept-source-agreements

echo [3/5] Setting up Premium authentication...
call "%CONFIG_DIR%\setup-premium.bat"

echo [4/5] Testing complete download...
echo Testing with a short video...
call "%CONFIG_DIR%\complete-downloader.bat" "https://www.youtube.com/watch?v=dQw4w9WgXcQ" 720 --simulate

echo [5/5] Setting up PowerShell module...
echo Adding to PowerShell profile...
powershell -Command "if (!(Test-Path $PROFILE)) { New-Item -Path $PROFILE -Type File -Force }; Add-Content -Path $PROFILE -Value 'Import-Module \"C:\Users\russe\yt-dlp-config\yt-dlp-complete.psm1\"'"

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next Steps:
echo 1. Restart PowerShell to load the module
echo 2. Test with: Invoke-CompleteDownload -Url "URL" -Quality 1080
echo 3. Add channels: Add-TrackedChannel "Channel URL"
echo 4. Start tracking: Start-TrackerDaemon
echo.
echo Documentation: %CONFIG_DIR%\COMPLETE-README.md
echo.

pause