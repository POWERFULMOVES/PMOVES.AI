@echo off
setlocal enabledelayedexpansion

rem -------------------------------------------------------------
rem  ComfyUI + MiniMax H3 one-click installer V1       by Aitrepreneur
rem -------------------------------------------------------------

:: Version bump zone
set "COMFY_VER=v0.30.0"

:: ---------- MODEL ----------
set "FL2VA_MODEL=minimax_h3_fl2va_pruned_int8_convrot.safetensors"
set "REF2VA_MODEL=minimax_h3_ref2va_pruned_int8_convrot.safetensors"

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
if errorlevel 1 (
    echo Download failed.
    pause
    exit /b 1
)

echo -------- Extracting ComfyUI --------
"%SEVEN_ZIP_PATH%" x ComfyUI.7z -aoa -o"%CD%" >nul
del ComfyUI.7z
if not exist "ComfyUI_windows_portable" (
    echo Extraction failed.
    pause
    exit /b 1
)

set "ROOT=%CD%"
pushd "ComfyUI_windows_portable"

rem Upstream uses "python_embeded"
set "PY=%CD%\python_embeded\python.exe"

echo(
echo -------- Installing custom nodes --------
pushd ComfyUI\custom_nodes

call :clone https://github.com/ltdrdata/ComfyUI-Manager.git
if exist ComfyUI-Manager\requirements.txt "%PY%" -m pip install -r ComfyUI-Manager\requirements.txt

call :clone https://github.com/rgthree/rgthree-comfy
if exist rgthree-comfy\requirements.txt "%PY%" -m pip install -r rgthree-comfy\requirements.txt

call :clone https://github.com/kijai/ComfyUI-KJNodes
if exist ComfyUI-KJNodes\requirements.txt "%PY%" -m pip install -r ComfyUI-KJNodes\requirements.txt

call :clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite
if exist ComfyUI-VideoHelperSuite\requirements.txt "%PY%" -m pip install -r ComfyUI-VideoHelperSuite\requirements.txt

call :clone https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3
if exist ComfyUI-Spectrum-MiniMax-H3\requirements.txt "%PY%" -m pip install -r ComfyUI-Spectrum-MiniMax-H3\requirements.txt

popd

echo(
echo -------- Downloading MiniMax H3 model files --------
pushd ComfyUI\models

:: --- Text Encoder ---
call :grab text_encoders\qwen3vl_32b_minimax_h3_int8_convrot.safetensors ^
     "%HF%/qwen3vl_32b_minimax_h3_int8_convrot.safetensors?download=true"
	 
:: --- LORAS ---
	 
call :grab loras\minimax_h3_turbo_4step_ckpt500_comfyui_pruned.safetensors ^
     "%HF%/minimax_h3_turbo_4step_ckpt500_comfyui_pruned.safetensors?download=true"	 

:: --- VAE ---
call :grab vae\minimax_h3_audio_vae_fp32.safetensors ^
     "%HF%/minimax_h3_audio_vae_fp32.safetensors?download=true"

call :grab vae\minimax_h3_video_vae_fp16.safetensors ^
     "%HF%/minimax_h3_video_vae_fp16.safetensors?download=true"

:: --- Diffusion models ---
call :grab diffusion_models\!FL2VA_MODEL! ^
     "%HF%/!FL2VA_MODEL!?download=true"

call :grab diffusion_models\!REF2VA_MODEL! ^
     "%HF%/!REF2VA_MODEL!?download=true"

popd & popd

echo(
echo -------------------------------------------------------------
echo      Install complete - launching ComfyUI now!
echo -------------------------------------------------------------
pushd "%ROOT%\ComfyUI_windows_portable"
call run_nvidia_gpu.bat
popd
echo(
pause
exit /b


:: ================= helper routines =================

:ensure_7zip
rem Try PATH first
set "SEVEN_ZIP_PATH="
for %%I in (7z.exe) do (
    if exist "%%~$PATH:I" (
        set "SEVEN_ZIP_PATH=%%~$PATH:I"
    )
)
if defined SEVEN_ZIP_PATH (
    exit /b 0
)

rem Try common install folders
if exist "%ProgramFiles%\7-Zip\7z.exe" (
    set "SEVEN_ZIP_PATH=%ProgramFiles%\7-Zip\7z.exe"
    exit /b 0
) else if exist "%ProgramFiles(x86)%\7-Zip\7z.exe" (
    set "SEVEN_ZIP_PATH=%ProgramFiles(x86)%\7-Zip\7z.exe"
    exit /b 0
)

echo 7-Zip not found. Trying to install with winget...

where winget >nul 2>&1
if errorlevel 1 (
    echo winget is not available on this system.
    echo Please install 7-Zip manually from:
    echo   https://www.7-zip.org/download.html
    pause
    exit /b 1
)

winget install -e --id 7zip.7zip --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo Failed to install 7-Zip via winget.
    echo Please install 7-Zip manually from:
    echo   https://www.7-zip.org/download.html
    pause
    exit /b 1
)

rem Try again to locate 7z.exe
set "SEVEN_ZIP_PATH="
for %%I in (7z.exe) do (
    if exist "%%~$PATH:I" (
        set "SEVEN_ZIP_PATH=%%~$PATH:I"
    )
)
if not defined SEVEN_ZIP_PATH (
    if exist "%ProgramFiles%\7-Zip\7z.exe" set "SEVEN_ZIP_PATH=%ProgramFiles%\7-Zip\7z.exe"
)
if not defined SEVEN_ZIP_PATH (
    if exist "%ProgramFiles(x86)%\7-Zip\7z.exe" set "SEVEN_ZIP_PATH=%ProgramFiles(x86)%\7-Zip\7z.exe"
)

if defined SEVEN_ZIP_PATH (
    exit /b 0
) else (
    echo 7-Zip seems installed but 7z.exe was not found.
    echo Please check your installation and rerun this script.
    pause
    exit /b 1
)

:ensure_git
echo Checking for Git...
git --version >nul 2>&1
if not errorlevel 1 (
    echo Git is already installed.
    exit /b 0
)

echo Git not found. Trying to install with winget...

where winget >nul 2>&1
if errorlevel 1 (
    echo winget is not available on this system.
    echo Please install Git manually from:
    echo   https://git-scm.com/download/win
    pause
    exit /b 1
)

winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo.
    echo Failed to install Git via winget.
    echo Please install Git manually from:
    echo   https://git-scm.com/download/win
    pause
    exit /b 1
)

echo Git installed successfully. Verifying...
git --version >nul 2>&1
if errorlevel 1 (
    echo Git is installed but not yet available in this terminal session.
    echo Close this window and run the installer again.
    pause
    exit /b 1
)

exit /b 0

:clone
git clone %* >nul 2>&1
if errorlevel 1 echo   [!] Clone failed: %~1
goto :eof

:grab
if not exist "%~dp1" mkdir "%~dp1"
if not exist "%~1" (
    echo   - downloading %~nx1
    curl -L -o "%~1" "%~2" --ssl-no-revoke
    if errorlevel 1 echo     [!] Download failed: %~nx1
) else (
    echo   - %~nx1 already present - skipping
)
goto :eof