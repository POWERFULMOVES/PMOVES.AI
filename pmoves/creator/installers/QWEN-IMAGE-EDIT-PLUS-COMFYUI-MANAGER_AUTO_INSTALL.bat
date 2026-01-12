@echo off
setlocal enabledelayedexpansion

rem -------------------------------------------------------------
rem  ComfyUI + QWEN IMAGE EDIT PLUS one-click installer      by Aitrepreneur
rem -------------------------------------------------------------

:: ✎  Version bump zone
set "COMFY_VER=v0.3.6"
set "SEVEN_VER=22.01"
set "GIT_VER=2.45.0.windows.1"
:: --------------------------------------------------------------

:: ---------- MODEL CHOICE ----------
:CHOOSE_MODEL
echo(
echo Which QWEN IMAGE Edit PLUS quantization?
echo 1) Q4_K_S  – GPUs ^< 12 GB
echo 2) Q5_K_S  – GPUs 12-16 GB
echo 3) Q8_0    – Best quality, GPUs 24 GB+
set /p "MODEL_CHOICE=Enter 1, 2 or 3: "
if "!MODEL_CHOICE!"=="1" (set "MODEL_VERSION=Q4_K_S") ^
else if "!MODEL_CHOICE!"=="2" (set "MODEL_VERSION=Q5_K_S") ^
else if "!MODEL_CHOICE!"=="3" (set "MODEL_VERSION=Q8_0") ^
else (echo Invalid choice.&timeout /t 2 >nul&goto CHOOSE_MODEL)

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

call :clone https://github.com/crystian/ComfyUI-Crystools.git
if exist ComfyUI-Crystools\requirements.txt "%PY%" -m pip install -r ComfyUI-Crystools\requirements.txt

call :clone https://github.com/ClownsharkBatwing/RES4LYF
if exist RES4LYF\requirements.txt "%PY%" -m pip install -r RES4LYF\requirements.txt

call :clone https://github.com/Fannovel16/comfyui_controlnet_aux
if exist comfyui_controlnet_aux\requirements.txt "%PY%" -m pip install -r comfyui_controlnet_aux\requirements.txt



popd

echo(
echo -------- Downloading QWEN IMAGE model files --------
pushd ComfyUI\models

:: --- Text Encoders ---
call :grab text_encoders\Qwen2.5-VL-7B-Instruct-mmproj-BF16.gguf ^
     "%HF%/Qwen2.5-VL-7B-Instruct-mmproj-BF16.gguf?download=true"
call :grab text_encoders\Qwen2.5-VL-7B-Instruct-UD-Q4_K_S.gguf ^
     "%HF%/Qwen2.5-VL-7B-Instruct-UD-Q4_K_S.gguf?download=true"	 
  
:: --- VAE ---
call :grab vae\qwen_image_vae.safetensors ^
     "%HF%/qwen_image_vae.safetensors?download=true"	 
	 
:: --- UNets ---
call :grab unet\Qwen-Image-Edit-2509-!MODEL_VERSION!.gguf ^
     "%HF%/Qwen-Image-Edit-2509-!MODEL_VERSION!.gguf?download=true"

:: --- LoRAs ---
call :grab loras\Qwen-Image-Edit-Lightning-8steps-V1.0.safetensors ^
     "%HF%/Qwen-Image-Edit-Lightning-8steps-V1.0.safetensors?download=true"
call :grab loras\Qwen-Image-Edit-Lightning-4steps-V1.0.safetensors ^
     "%HF%/Qwen-Image-Edit-Lightning-4steps-V1.0.safetensors?download=true"

:: --- Upscalers ---
for %%F in (4x-ClearRealityV1.pth RealESRGAN_x4plus_anime_6B.pth) do (
    call :grab upscale_models\%%F "%HF%/%%F?download=true"
)

popd & popd

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