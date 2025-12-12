@echo off
title SillyTavern 1-Click Installer
echo.
echo Checking for Git...

:: Check if Git exists
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Git not found. Installing Git...
    winget install -e --id Git.Git
    if %errorlevel% neq 0 (
        echo.
        echo Failed to install Git. Please install it manually then rerun this installer.
        pause
        exit /b
    )
    echo Git installed successfully.
) else (
    echo Git is already installed.
)

echo.
echo Cloning SillyTavern Launcher...

:: Clone repo
git clone https://github.com/SillyTavern/SillyTavern-Launcher.git
if %errorlevel% neq 0 (
    echo.
    echo Failed to clone repository. Maybe the folder already exists?
    echo Please delete the existing "SillyTavern-Launcher" folder or move this script elsewhere.
    pause
    exit /b
)

cd SillyTavern-Launcher

echo.
echo Starting official installer...
start installer.bat

echo.
echo Done. The installer window should now be open.
pause
