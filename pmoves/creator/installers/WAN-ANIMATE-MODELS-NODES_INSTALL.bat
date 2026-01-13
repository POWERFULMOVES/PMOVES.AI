@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul

rem ----------------------------------------------------------------
rem  WAN Animate 2.2 ▸ download missing models + clone/update nodes
rem
rem  IMPORTANT: Run from: ...\ComfyUI_windows_portable\ComfyUI\
rem ----------------------------------------------------------------

:: ── CONSTANTS & PATHS ───────────────────────────────────────
set "HF=https://huggingface.co/Aitrepreneur/FLX/resolve/main"
set "COMFY=%CD%"
set "PY=%COMFY%\..\python_embeded\python.exe"

if not exist "%PY%" (
    echo [ERROR] Could not find python at "%PY%"
    echo Please run this script from:
    echo ...\ComfyUI_windows_portable\ComfyUI\
    pause
    exit /b 1
)

:: ── NEED GIT ────────────────────────────────────────────────
git --version >nul 2>&1 || (
    echo [ERROR] Git is not in PATH – install Git for Windows and try again.
    pause & exit /b 1
)

:: ── CLONE / UPDATE ONLY THE REQUESTED CUSTOM NODES ─────────
echo(
echo -------- Checking custom nodes --------
pushd custom_nodes

call :get_node "ComfyUI-Manager"               "https://github.com/ltdrdata/ComfyUI-Manager.git"
call :get_node "ComfyUI-WanVideoWrapper"       "https://github.com/kijai/ComfyUI-WanVideoWrapper"
call :get_node "rgthree-comfy"                 "https://github.com/rgthree/rgthree-comfy"
call :get_node "ComfyUI-KJNodes"               "https://github.com/kijai/ComfyUI-KJNodes"
call :get_node "ComfyUI-VideoHelperSuite"      "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite"
call :get_node "ComfyUI-segment-anything-2"    "https://github.com/kijai/ComfyUI-segment-anything-2"
call :get_node "Comfyui-SecNodes"              "https://github.com/9nate-drake/Comfyui-SecNodes"
call :get_node "ComfyUI-WanAnimatePreprocess"  "https://github.com/kijai/ComfyUI-WanAnimatePreprocess"

popd

:: ── DOWNLOAD ONLY THE WAN ANIMATE 2.2 FILES ─────
echo(
echo -------- Checking WAN Animate 2.2 model files --------
pushd models

:: clip_vision
call :grab "clip_vision\clip_vision_h.safetensors" ^
  "%HF%/clip_vision_h.safetensors?download=true"

:: detection
call :grab "detection\vitpose_h_wholebody_data.bin" ^
  "%HF%/vitpose_h_wholebody_data.bin?download=true"
call :grab "detection\vitpose_h_wholebody_model.onnx" ^
  "%HF%/vitpose_h_wholebody_model.onnx?download=true"
call :grab "detection\vitpose-l-wholebody.onnx" ^
  "%HF%/vitpose-l-wholebody.onnx?download=true"
call :grab "detection\yolov10m.onnx" ^
  "%HF%/yolov10m.onnx?download=true"

:: diffusion_models
call :grab "diffusion_models\Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2.safetensors" ^
  "%HF%/Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2.safetensors?download=true"

:: loras
call :grab "loras\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors" ^
  "%HF%/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors?download=true"
call :grab "loras\WanAnimate_relight_lora_fp16.safetensors" ^
  "%HF%/WanAnimate_relight_lora_fp16.safetensors?download=true"

:: sams
call :grab "sams\SeC-4B-fp16.safetensors" ^
  "%HF%/SeC-4B-fp16.safetensors?download=true"

:: text_encoders
call :grab "text_encoders\umt5-xxl-enc-bf16.safetensors" ^
  "%HF%/umt5-xxl-enc-bf16.safetensors?download=true"

:: vae
call :grab "vae\Wan2_1_VAE_bf16.safetensors" ^
  "%HF%/Wan2_1_VAE_bf16.safetensors?download=true"

popd

:: ── DONE ────────────────────────────────────────────────────
echo(
echo -------------------------------------------------------------
echo   WAN Animate 2.2 models and the requested nodes are ready.
echo -------------------------------------------------------------
pause
exit /b


:: ==================== SUBROUTINES ============================

:get_node
rem  %1 = local folder   %2 = repo URL   [%3 = optional clone flags]
set "DIR=%~1"
set "URL=%~2"
set "FLAGS=%~3"

if not exist "%DIR%" (
    echo   • cloning %DIR%
    git clone %FLAGS% "%URL%" "%DIR%"
) else (
    echo   • updating %DIR%
    if exist "%DIR%\.git" (
        pushd "%DIR%"
        git pull --ff-only --recurse-submodules
        git submodule update --init --recursive
        popd
    ) else (
        echo     [WARN] %DIR% exists but is not a git repo – skipping update.
    )
)

if exist "%DIR%\requirements.txt" (
    echo     – installing / upgrading Python deps for %DIR%
    "%PY%" -m pip install --upgrade -r "%DIR%\requirements.txt"
)
goto :eof


:grab
rem  %1 = relative save path   %2 = full URL
if not exist "%~dp1" mkdir "%~dp1"
if not exist "%~1" (
    echo   • downloading %~nx1
    curl -L -o "%~1" "%~2" --ssl-no-revoke
    if errorlevel 1 echo     [!] Failed: %~nx1
) else (
    echo   • %~nx1 already present – skipping
)
goto :eof
