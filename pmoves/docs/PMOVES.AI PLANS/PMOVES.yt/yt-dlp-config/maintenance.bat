# yt-dlp Update and Maintenance Script
# Run this periodically to keep everything up to date

@echo off
setlocal enabledelayedexpansion

echo ========================================
echo yt-dlp Maintenance Script
echo ========================================
echo.

set CONFIG_DIR=C:\Users\russe\yt-dlp-config

echo [1/4] Updating yt-dlp...
yt-dlp --update
if !errorlevel! equ 0 (
    echo    yt-dlp updated successfully!
) else (
    echo    yt-dlp update failed or already up to date
)
echo.

echo [2/4] Cleaning old log files...
if exist "%CONFIG_DIR%\download.log" (
    findstr /C:"Failed to download" "%CONFIG_DIR%\download.log" > "%CONFIG_DIR%\failed-downloads.txt" 2>nul
    echo    Failed downloads extracted to failed-downloads.txt
)
echo.

echo [3/4] Checking configuration...
if not exist "%CONFIG_DIR%\config.txt" (
    echo    WARNING: config.txt not found in %CONFIG_DIR%
) else (
    echo    Configuration file exists
)
echo.

echo [4/4] Testing installation...
yt-dlp --version
echo.

echo ========================================
echo Maintenance completed!
echo ========================================
pause