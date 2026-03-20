@echo off
setlocal enabledelayedexpansion

rem -------------------------------------------------------------
rem  ComfyUI + LTX-2 one-click installer      by Aitrepreneur
rem -------------------------------------------------------------

:: ✎  Version bump zone
set "COMFY_VER=v0.9.2"
set "SEVEN_VER=22.01"
set "GIT_VER=2.45.0.windows.1"
:: --------------------------------------------------------------

:: ---------- MODEL CHOICE ----------
:CHOOSE_MODEL
echo(
echo Which LTX-2 quantization?
echo 1) Q4_K_S  GPUs less than 12 GB VRAM RECOMMENDED
echo 2) Q5_K_S  GPUs 12-16 GB
echo 3) Q8_0    Best quality, GPUs 24 GB and more
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

call :clone https://github.com/ClownsharkBatwing/RES4LYF
if exist RES4LYF\requirements.txt "%PY%" -m pip install -r RES4LYF\requirements.txt

call :clone https://github.com/theUpsider/ComfyUI-Logic
if exist ComfyUI-Logic\requirements.txt "%PY%" -m pip install -r ComfyUI-Logic\requirements.txt

call :clone https://github.com/Fannovel16/comfyui_controlnet_aux
if exist comfyui_controlnet_aux\requirements.txt "%PY%" -m pip install -r comfyui_controlnet_aux\requirements.txt

call :clone https://github.com/Lightricks/ComfyUI-LTXVideo
if exist ComfyUI-LTXVideo\requirements.txt "%PY%" -m pip install -r ComfyUI-LTXVideo\requirements.txt

call :clone https://github.com/pythongosssss/ComfyUI-Custom-Scripts
if exist ComfyUI-Custom-Scripts\requirements.txt "%PY%" -m pip install -r ComfyUI-Custom-Scripts\requirements.txt

call :clone https://github.com/crystian/ComfyUI-Crystools
if exist ComfyUI-Crystools\requirements.txt "%PY%" -m pip install -r ComfyUI-Crystools\requirements.txt

call :clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite
if exist ComfyUI-VideoHelperSuite\requirements.txt "%PY%" -m pip install -r ComfyUI-VideoHelperSuite\requirements.txt

call :clone https://github.com/Derfuu/Derfuu_ComfyUI_ModdedNodes
if exist Derfuu_ComfyUI_ModdedNodes\requirements.txt "%PY%" -m pip install -r Derfuu_ComfyUI_ModdedNodes\requirements.txt

call :clone https://github.com/kijai/ComfyUI-MelBandRoFormer
if exist ComfyUI-MelBandRoFormer\requirements.txt "%PY%" -m pip install -r ComfyUI-MelBandRoFormer\requirements.txt

call :clone https://github.com/M1kep/ComfyLiterals
if exist ComfyLiterals\requirements.txt "%PY%" -m pip install -r ComfyLiterals\requirements.txt

call :clone https://github.com/YaserJaradeh/comfyui-yaser-nodes
if exist comfyui-yaser-nodes\requirements.txt "%PY%" -m pip install -r comfyui-yaser-nodes\requirements.txt

call :clone https://github.com/olduvai-jp/ComfyUI-S3-IO
if exist ComfyUI-S3-IO\requirements.txt "%PY%" -m pip install -r ComfyUI-S3-IO\requirements.txt


popd

echo(
echo -------- Downloading model files --------
pushd ComfyUI\models

:: --- Text Encoders ---
call :grab text_encoders\ltx-2-19b-embeddings_connector_dev_bf16.safetensors ^
     "%HF%/ltx-2-19b-embeddings_connector_dev_bf16.safetensors?download=true"

call :grab text_encoders\gemma-3-12b-it-IQ4_XS.gguf ^
     "%HF%/gemma-3-12b-it-IQ4_XS.gguf?download=true"


:: --- VAE ---
call :grab vae\LTX2_audio_vae_bf16.safetensors ^
     "%HF%/LTX2_audio_vae_bf16.safetensors?download=true"

call :grab vae\LTX2_video_vae_bf16.safetensors ^
     "%HF%/LTX2_video_vae_bf16.safetensors?download=true"


:: --- UNet ---
call :grab unet\ltx-2-19b-dev-!MODEL_VERSION!.gguf ^
     "%HF%/ltx-2-19b-dev-!MODEL_VERSION!.gguf?download=true"


:: --- Latent Upscale Models ---
call :grab latent_upscale_models\ltx-2-spatial-upscaler-x2-1.0.safetensors ^
     "%HF%/ltx-2-spatial-upscaler-x2-1.0.safetensors?download=true"


:: --- Diffusion Models ---
call :grab diffusion_models\MelBandRoformer_fp32.safetensors ^
     "%HF%/MelBandRoformer_fp32.safetensors?download=true"


:: --- LoRAs ---
for %%F in (
    ltx-2-19b-distilled-lora-384.safetensors
    ltx-2-19b-ic-lora-detailer.safetensors
    ltx-2-19b-ic-lora-depth-control.safetensors
    ltx-2-19b-ic-lora-pose-control.safetensors
) do (
    call :grab loras\%%F "%HF%/%%F?download=true"
)

popd & popd

echo(
echo -------- Downloading LTX-2 launchers --------
pushd "%ROOT%\ComfyUI_windows_portable"
call :grab run_nvidia_gpu-LTX2-8GB.bat  "%HF%/run_nvidia_gpu-LTX2-8GB.bat?download=true"
call :grab run_nvidia_gpu-LTX2-12GB.bat "%HF%/run_nvidia_gpu-LTX2-12GB.bat?download=true"
call :grab run_nvidia_gpu-LTX2-16GB.bat "%HF%/run_nvidia_gpu-LTX2-16GB.bat?download=true"

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