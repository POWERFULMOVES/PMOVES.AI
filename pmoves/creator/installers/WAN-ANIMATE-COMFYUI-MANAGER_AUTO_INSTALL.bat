@echo off
setlocal EnableExtensions DisableDelayedExpansion
title WAN Animate 2.2 — ComfyUI One-Click (Windows)
chcp 65001 >nul
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PYTHONNOUSERSITE=1"
set "PYTHONUTF8=1"

rem -------------------------------------------------------------
rem  ComfyUI + WAN Animate 2.2 one-click installer    by K
rem -------------------------------------------------------------

:: Versions
set "COMFY_VER=v0.3.65"
set "SEVEN_VER=22.01"
set "GIT_VER=2.45.0.windows.1"

:: URLs
set "HF=https://huggingface.co/Aitrepreneur/FLX/resolve/main"
set "COMFY_RELEASE=https://github.com/comfyanonymous/ComfyUI/releases/download/%COMFY_VER%/ComfyUI_windows_portable_nvidia.7z"

echo(
echo -------- Checking prerequisites --------
call :ensure_7zip || exit /b 1
call :ensure_git  || exit /b 1

echo(
echo -------- Downloading ComfyUI %COMFY_VER% --------
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

call :clone https://github.com/kijai/ComfyUI-WanVideoWrapper
if exist ComfyUI-WanVideoWrapper\requirements.txt "%PY%" -m pip install -r ComfyUI-WanVideoWrapper\requirements.txt

call :clone https://github.com/rgthree/rgthree-comfy
if exist rgthree-comfy\requirements.txt "%PY%" -m pip install -r rgthree-comfy\requirements.txt

call :clone https://github.com/kijai/ComfyUI-KJNodes
if exist ComfyUI-KJNodes\requirements.txt "%PY%" -m pip install -r ComfyUI-KJNodes\requirements.txt

call :clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite
if exist ComfyUI-VideoHelperSuite\requirements.txt "%PY%" -m pip install -r ComfyUI-VideoHelperSuite\requirements.txt

call :clone https://github.com/kijai/ComfyUI-segment-anything-2
if exist ComfyUI-segment-anything-2\requirements.txt "%PY%" -m pip install -r ComfyUI-segment-anything-2\requirements.txt

call :clone https://github.com/9nate-drake/Comfyui-SecNodes
if exist Comfyui-SecNodes\requirements.txt "%PY%" -m pip install -r Comfyui-SecNodes\requirements.txt

call :clone https://github.com/kijai/ComfyUI-WanAnimatePreprocess
if exist ComfyUI-WanAnimatePreprocess\requirements.txt "%PY%" -m pip install -r ComfyUI-WanAnimatePreprocess\requirements.txt

popd

echo(
echo -------- Downloading WAN Animate 2.2 models --------
pushd ComfyUI\models

:: clip_vision
call :grab clip_vision\clip_vision_h.safetensors ^
  "%HF%/clip_vision_h.safetensors?download=true"

:: detection
call :grab detection\vitpose_h_wholebody_data.bin ^
  "%HF%/vitpose_h_wholebody_data.bin?download=true"
call :grab detection\vitpose_h_wholebody_model.onnx ^
  "%HF%/vitpose_h_wholebody_model.onnx?download=true"
call :grab detection\vitpose-l-wholebody.onnx ^
  "%HF%/vitpose-l-wholebody.onnx?download=true"
call :grab detection\yolov10m.onnx ^
  "%HF%/yolov10m.onnx?download=true"

:: diffusion_models
call :grab diffusion_models\Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2.safetensors ^
  "%HF%/Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2.safetensors?download=true"

:: loras
call :grab loras\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors ^
  "%HF%/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors?download=true"
call :grab loras\WanAnimate_relight_lora_fp16.safetensors ^
  "%HF%/WanAnimate_relight_lora_fp16.safetensors?download=true"

:: sams
call :grab sams\SeC-4B-fp16.safetensors ^
  "%HF%/SeC-4B-fp16.safetensors?download=true"

:: text_encoders
call :grab text_encoders\umt5-xxl-enc-bf16.safetensors ^
  "%HF%/umt5-xxl-enc-bf16.safetensors?download=true"

:: vae
call :grab vae\Wan2_1_VAE_bf16.safetensors ^
  "%HF%/Wan2_1_VAE_bf16.safetensors?download=true"

popd

echo(
echo -------- Python packages: pip, Triton, SageAttention --------
pushd "%ROOT%\ComfyUI_windows_portable"

:: upgrade pip
"%PY%" -m pip install -U pip

:: Triton for Windows, compatible with Torch 2.8
"%PY%" -m pip install "triton-windows<3.5"

:: FAST hf transfer
"%PY%" -m pip install hf_transfer

:: SageAttention wheel for Torch 2.8 and CUDA 12.8
"%PY%" -m pip install ^
  https://github.com/woct0rdho/SageAttention/releases/download/v2.2.0-windows.post3/sageattention-2.2.0+cu128torch2.8.0.post3-cp39-abi3-win_amd64.whl

echo(
echo -------- Extra Python include libs for Triton --------
set "URL=https://github.com/woct0rdho/triton-windows/releases/download/v3.0.0-windows.post1/python_3.13.2_include_libs.zip"
set "ZIP_FILE=python_libs.zip"
set "DEST_FOLDER=%CD%\python_embeded"

echo   • downloading include libs zip
curl -L "%URL%" -o "%ZIP_FILE%"

echo   • extracting into python_embeded
"%SEVEN_ZIP_PATH%" x "%ZIP_FILE%" -aoa -o"%DEST_FOLDER%" >nul
del "%ZIP_FILE%"

popd
popd

echo(
echo -------------------------------------------------------------
echo      Install complete. Launching ComfyUI now
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
echo 7-Zip not found. Downloading...
curl -L -o 7z-installer.exe https://www.7-zip.org/a/7z%SEVEN_VER%-x64.exe --ssl-no-revoke
start /wait 7z-installer.exe /S
del 7z-installer.exe
for %%I in (7z.exe) do set "SEVEN_ZIP_PATH=%%~$PATH:I"
if defined SEVEN_ZIP_PATH (exit /b 0) else (
    echo 7-Zip install failed. Install it manually then rerun this script.
    pause & exit /b 1
)

:ensure_git
git --version >nul 2>&1 && goto :eof
echo Git not found. Downloading silent installer...
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
    echo   • %~nx1 already present. Skipping
)
goto :eof
