@echo off
setlocal enabledelayedexpansion

rem -------------------------------------------------------------
rem  ComfyUI + Z-IMAGE TURBO one-click installer      by Aitrepreneur
rem -------------------------------------------------------------

:: Version bump zone
set "COMFY_VER=v0.3.76"

:: ---------- MODEL CHOICE ----------
:CHOOSE_MODEL
echo(
echo Which Z IMAGE TURBO quantization?
echo 1) Q5_K_S  - GPUs ^< 8 GB VRAM RECOMMENDED
echo 2) Q6_K    - GPUs 8-12 GB
echo 3) Q8_0    - Best quality, GPUs 12-16 GB and more
set /p "MODEL_CHOICE=Enter 1, 2 or 3: "
if "!MODEL_CHOICE!"=="1" (set "MODEL_VERSION=Q5_K_S") ^
else if "!MODEL_CHOICE!"=="2" (set "MODEL_VERSION=Q6_K") ^
else if "!MODEL_CHOICE!"=="3" (set "MODEL_VERSION=Q8_0") ^
else (
    echo Invalid choice.
    timeout /t 2 >nul
    goto CHOOSE_MODEL
)

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

call :clone https://github.com/city96/ComfyUI-GGUF
if exist ComfyUI-GGUF\requirements.txt "%PY%" -m pip install -r ComfyUI-GGUF\requirements.txt

call :clone https://github.com/rgthree/rgthree-comfy
if exist rgthree-comfy\requirements.txt "%PY%" -m pip install -r rgthree-comfy\requirements.txt

call :clone https://github.com/yolain/ComfyUI-Easy-Use
if exist ComfyUI-Easy-Use\requirements.txt "%PY%" -m pip install -r ComfyUI-Easy-Use\requirements.txt

call :clone https://github.com/kijai/ComfyUI-KJNodes
if exist ComfyUI-KJNodes\requirements.txt "%PY%" -m pip install -r ComfyUI-KJNodes\requirements.txt

call :clone https://github.com/ssitu/ComfyUI_UltimateSDUpscale
if exist ComfyUI_UltimateSDUpscale\requirements.txt "%PY%" -m pip install -r ComfyUI_UltimateSDUpscale\requirements.txt

call :clone https://github.com/cubiq/ComfyUI_essentials
if exist ComfyUI_essentials\requirements.txt "%PY%" -m pip install -r ComfyUI_essentials\requirements.txt

call :clone https://github.com/wallish77/wlsh_nodes
if exist wlsh_nodes\requirements.txt "%PY%" -m pip install -r wlsh_nodes\requirements.txt

call :clone https://github.com/vrgamegirl19/comfyui-vrgamedevgirl
if exist comfyui-vrgamedevgirl\requirements.txt "%PY%" -m pip install -r comfyui-vrgamedevgirl\requirements.txt

call :clone https://github.com/ClownsharkBatwing/RES4LYF
if exist RES4LYF\requirements.txt "%PY%" -m pip install -r RES4LYF\requirements.txt

call :clone https://github.com/Jonseed/ComfyUI-Detail-Daemon
if exist ComfyUI-Detail-Daemon\requirements.txt "%PY%" -m pip install -r ComfyUI-Detail-Daemon\requirements.txt

call :clone https://github.com/ChangeTheConstants/SeedVarianceEnhancer
if exist SeedVarianceEnhancer\requirements.txt "%PY%" -m pip install -r SeedVarianceEnhancer\requirements.txt

call :clone https://github.com/Fannovel16/comfyui_controlnet_aux
if exist comfyui_controlnet_aux\requirements.txt "%PY%" -m pip install -r comfyui_controlnet_aux\requirements.txt


popd

echo(
echo -------- Downloading Z-IMAGE TURBO model files --------
pushd ComfyUI\models

:: --- Text Encoders ---
call :grab text_encoders\Qwen3-4B-UD-Q6_K_XL.gguf ^
     "%HF%/Qwen3-4B-UD-Q6_K_XL.gguf?download=true"
  
:: --- VAE ---
call :grab vae\ae.safetensors ^
     "%HF%/ae.safetensors?download=true"
	 
:: --- MODEL PATCHES ---
call :grab model_patches\Z-Image-Turbo-Fun-Controlnet-Union-fp8-e5m2.safetensors ^
     "%HF%/Z-Image-Turbo-Fun-Controlnet-Union-fp8-e5m2.safetensors?download=true"	 
	 
:: --- UNets ---
call :grab unet\z_image_turbo-!MODEL_VERSION!.gguf ^
     "%HF%/z_image_turbo-!MODEL_VERSION!.gguf?download=true"

:: --- Upscalers ---
for %%F in (4x-ClearRealityV1.pth RealESRGAN_x4plus_anime_6B.pth) do (
    call :grab upscale_models\%%F "%HF%/%%F?download=true"
)

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
