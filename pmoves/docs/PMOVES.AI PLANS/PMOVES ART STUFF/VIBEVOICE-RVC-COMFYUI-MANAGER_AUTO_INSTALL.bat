@echo off
setlocal enabledelayedexpansion

rem -------------------------------------------------------------
rem  ComfyUI + VibeVoice + RVC nodes installer      by Aitrepreneur
rem -------------------------------------------------------------

:: ✎  Version bump zone
set "COMFY_VER=v0.3.59"
set "SEVEN_VER=22.01"
set "GIT_VER=2.45.0.windows.1"
:: --------------------------------------------------------------

:: ---------- CONSTANTS ----------
set "HF=https://huggingface.co/Aitrepreneur/FLX/resolve/main"
set "COMFY_RELEASE=https://github.com/comfyanonymous/ComfyUI/releases/download/%COMFY_VER%/ComfyUI_windows_portable_nvidia.7z"

echo(
echo -------- Checking prerequisites --------
call :ensure_7zip || exit /b 1
call :ensure_git  || exit /b 1

echo(
echo -------- Downloading ComfyUI --------
curl -L -o ComfyUI.7z "%COMFY_RELEASE%" --ssl-no-revoke
if errorlevel 1 (echo Download failed.&pause&exit /b 1)

echo -------- Extracting ComfyUI --------
"%SEVEN_ZIP_PATH%" x ComfyUI.7z -aoa -o"%CD%" >nul
del ComfyUI.7z
if not exist "ComfyUI_windows_portable" (
    echo Extraction failed.&pause&exit /b 1
)

set "ROOT=%CD%"
pushd "ComfyUI_windows_portable"

rem Upstream uses “python_embeded”
set "PY=%CD%\python_embeded\python.exe"

echo(
echo -------- Installing custom nodes --------
pushd ComfyUI\custom_nodes

call :clone https://github.com/ltdrdata/ComfyUI-Manager.git
if exist ComfyUI-Manager\requirements.txt "%PY%" -m pip install -r ComfyUI-Manager\requirements.txt

call :clone https://github.com/rgthree/rgthree-comfy
if exist rgthree-comfy\requirements.txt "%PY%" -m pip install -r rgthree-comfy\requirements.txt

call :clone https://github.com/Enemyx-net/VibeVoice-ComfyUI
if exist VibeVoice-ComfyUI\requirements.txt "%PY%" -m pip install -r VibeVoice-ComfyUI\requirements.txt

call :clone https://github.com/diodiogod/TTS-Audio-Suite
if exist TTS-Audio-Suite\requirements.txt "%PY%" -m pip install -r TTS-Audio-Suite\requirements.txt

popd

echo(
echo -------------------------------------------------------------
echo      Install complete – launching ComfyUI now!
echo -------------------------------------------------------------
pushd "%ROOT%\ComfyUI_windows_portable"
call run_nvidia_gpu.bat
popd
echo(
pause
exit /b


:: ================= helper routines =================

:ensure_7zip
for %%I in (7z.exe) do set "SEVEN_ZIP_PATH=%%~$PATH:I"
if defined SEVEN_ZIP_PATH exit /b 0
if exist "%ProgramFiles%\7-Zip\7z.exe" (
    set "SEVEN_ZIP_PATH=%ProgramFiles%\7-Zip\7z.exe"
    exit /b 0
) else if exist "%ProgramFiles(x86)%\7-Zip\7z.exe" (
    set "SEVEN_ZIP_PATH=%ProgramFiles(x86)%\7-Zip\7z.exe"
    exit /b 0
)
echo 7-Zip not found – downloading...
curl -L -o 7z-installer.exe https://www.7-zip.org/a/7z%SEVEN_VER%-x64.exe --ssl-no-revoke
start /wait 7z-installer.exe /S
del 7z-installer.exe
for %%I in (7z.exe) do set "SEVEN_ZIP_PATH=%%~$PATH:I"
if defined SEVEN_ZIP_PATH (exit /b 0) else (
    echo 7-Zip install failed – install it manually then rerun this script.
    pause & exit /b 1
)

:ensure_git
git --version >nul 2>&1 && goto :eof
echo Git not found – downloading silent installer...
curl -L -o git-setup.exe ^
 "https://github.com/git-for-windows/git/releases/download/v%GIT_VER%/Git-%GIT_VER%-64-bit.exe" --ssl-no-revoke
start /wait "" git-setup.exe /VERYSILENT
del git-setup.exe
git --version >nul 2>&1 || (
    echo Git install failed. Please install manually.
    exit /b 1
)
goto :eof

:clone
git clone %* >nul 2>&1
if errorlevel 1 echo   [!] Clone failed: %~1
goto :eof

:grab
if not exist "%~dp1" mkdir "%~dp1"
if not exist "%~1" (
    echo   • downloading %~nx1
    curl -L -o "%~1" "%~2" --ssl-no-revoke
    if errorlevel 1 echo     [!] Download failed: %~nx1
) else (
    echo   • %~nx1 already present – skipping
)
goto :eof