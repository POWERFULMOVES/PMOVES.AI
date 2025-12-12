@echo off
setlocal ENABLEDELAYEDEXPANSION

title Chatterbox-TTS-Server 1-Click Installer

echo ==========================================
echo   Chatterbox-TTS-Server 1-Click Installer
echo ==========================================
echo.

REM ==============================
REM  CHOOSE INSTALLATION MODE FIRST
REM ==============================
echo Choose installation mode:
echo.
echo  1. CPU only   (works on any machine)
echo  2. NVIDIA GPU (recommended if you have an NVIDIA GPU)
echo.
set "MODE_CHOICE="
set /p MODE_CHOICE="Enter 1 or 2 [2]: "

if "%MODE_CHOICE%"=="1" (
    set "INSTALL_MODE=CPU"
) else (
    if "%MODE_CHOICE%"=="2" (
        set "INSTALL_MODE=GPU"
    ) else (
        if "%MODE_CHOICE%"=="" (
            set "INSTALL_MODE=GPU"
        ) else (
            echo Invalid choice, defaulting to NVIDIA GPU mode.
            set "INSTALL_MODE=GPU"
        )
    )
)

echo.
echo Selected mode: %INSTALL_MODE%
echo.

REM ==============================
REM  MOVE TO SCRIPT LOCATION
REM ==============================
REM Move to the folder where this script is located (SillyTavern folder)
cd /d "%~dp0"

REM Ensure plugins folder exists
if not exist "plugins" (
    echo plugins folder not found, creating it...
    mkdir "plugins"
)

REM Go into plugins
cd "plugins"

REM ==============================
REM  CLONE OR UPDATE REPO
REM ==============================
if exist "Chatterbox-TTS-Server\.git" (
    echo Chatterbox-TTS-Server already exists.
    echo Updating repository with latest changes...
    cd "Chatterbox-TTS-Server"
    git pull
    if errorlevel 1 (
        echo Failed to update repository with git pull.
        echo Please check your internet connection or git installation.
        goto END
    )
) else (
    echo Cloning Chatterbox-TTS-Server repository...
    git clone https://github.com/devnen/Chatterbox-TTS-Server.git
    if errorlevel 1 (
        echo Failed to clone the repository.
        echo Make sure git is installed and available in PATH.
        goto END
    )
    cd "Chatterbox-TTS-Server"
)

echo.
echo Repository is ready at:
echo %cd%
echo.

REM ==============================
REM  CHECK PYTHON
REM ==============================
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH.
    echo Please install Python 3 and try again.
    goto END
)

REM ==============================
REM  CREATE OR REUSE VENV
REM ==============================
if not exist "venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        goto END
    )
) else (
    echo Virtual environment already exists, reusing it.
)

set "VENV_PYTHON=%cd%\venv\Scripts\python.exe"

REM ==============================
REM  UPGRADE PIP
REM ==============================
echo.
echo Upgrading pip in the virtual environment...
"%VENV_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 (
    echo Failed to upgrade pip.
    goto END
)

REM ==============================
REM  INSTALL REQUIREMENTS BASED ON MODE
REM ==============================
if /I "%INSTALL_MODE%"=="CPU" (
    echo.
    echo Installing CPU only requirements from requirements.txt ...
    "%VENV_PYTHON%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Failed to install CPU requirements.
        goto END
    )
) else (
    echo.
    echo Installing NVIDIA GPU requirements from requirements-nvidia.txt ...
    "%VENV_PYTHON%" -m pip install -r requirements-nvidia.txt
    if errorlevel 1 (
        echo Failed to install NVIDIA requirements.
        goto END
    )
)

REM ==============================
REM  DOWNLOAD Start.bat LAUNCHER
REM ==============================
echo.
echo Downloading Start.bat launcher from Hugging Face...

powershell -NoLogo -NoProfile -Command ^
 "try { Invoke-WebRequest -Uri 'https://huggingface.co/Aitrepreneur/test/resolve/main/Start.bat?download=true' -OutFile 'Start.bat' -UseBasicParsing } catch { Write-Error $_; exit 1 }"

if errorlevel 1 (
    echo Failed to download Start.bat.
    echo You can manually download it from:
    echo https://huggingface.co/Aitrepreneur/test/resolve/main/Start.bat
    goto END
)

echo.
echo ==========================================
echo   Installation complete
echo ==========================================
echo Chatterbox-TTS-Server installed successfully in:
echo   %cd%
echo.
echo Mode installed: %INSTALL_MODE%
echo.
echo To start the server later:
echo  1. Go to this folder:
echo     %cd%
echo  2. Double click Start.bat
echo.

:END
echo.
pause
endlocal
