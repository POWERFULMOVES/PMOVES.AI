@echo off
setlocal enabledelayedexpansion

rem ----------------------------------------------------------------
rem  QWEN IMAGE EDIT PLUS  ▸  download missing models + clone / update nodes
rem
rem  IMPORTANT: Put this file in your ...\ComfyUI_windows_portable\ComfyUI\
rem  directory and run it from there.
rem ----------------------------------------------------------------

:: ── CHOOSE QUANTIZATION ─────────────────────────────────────
:CHOOSE_MODEL
echo(
echo Which QWEN IMAGE EDIT PLUS quantization do you need?
echo 1) Q4_K_S   – GPUs under 12 GB
echo 2) Q5_K_S   – GPUs 12-16 GB
echo 3) Q8_0     – Best quality, GPUs 24 GB+
set /p "MODEL_CHOICE=Enter 1, 2 or 3: "
if "!MODEL_CHOICE!"=="1" (set "MODEL_VERSION=Q4_K_S") ^
else if "!MODEL_CHOICE!"=="2" (set "MODEL_VERSION=Q5_K_S") ^
else if "!MODEL_CHOICE!"=="3" (set "MODEL_VERSION=Q8_0") ^
else (echo Invalid;&timeout /t 2 >nul&goto CHOOSE_MODEL)

:: ── CONSTANTS & PATHS ───────────────────────────────────────
set "HF=https://huggingface.co/Aitrepreneur/FLX/resolve/main"
set "COMFY=%CD%"
set "PY=%COMFY%\..\python_embeded\python.exe"

if not exist "%PY%" (
    echo [ERROR] Could not find python at "%PY%"
    echo Please make sure you are running this script from the correct directory:
    echo ...\ComfyUI_windows_portable\ComfyUI\
    pause
    exit /b 1
)

:: ── NEED GIT ────────────────────────────────────────────────
git --version >nul 2>&1 || (
    echo [ERROR] Git is not in PATH – install Git for Windows and try again.
    pause & exit /b 1
)

:: ── CLONE / UPDATE CUSTOM NODES ─────────────────────────────
echo(
echo -------- Checking custom nodes --------
pushd custom_nodes

call :get_node "ComfyUI-Manager"             "https://github.com/ltdrdata/ComfyUI-Manager.git"
call :get_node "ComfyUI-GGUF"                "https://github.com/city96/ComfyUI-GGUF"
call :get_node "rgthree-comfy"               "https://github.com/rgthree/rgthree-comfy"
call :get_node "ComfyUI-Easy-Use"            "https://github.com/yolain/ComfyUI-Easy-Use"
call :get_node "ComfyUI-KJNodes"             "https://github.com/kijai/ComfyUI-KJNodes"
call :get_node "ComfyUI_UltimateSDUpscale"   "https://github.com/ssitu/ComfyUI_UltimateSDUpscale"
call :get_node "ComfyUI_essentials"          "https://github.com/cubiq/ComfyUI_essentials"
call :get_node "wlsh_nodes"                  "https://github.com/wallish77/wlsh_nodes"
call :get_node "comfyui-vrgamedevgirl"       "https://github.com/vrgamegirl19/comfyui-vrgamedevgirl"
call :get_node "RES4LYF"                     "https://github.com/ClownsharkBatwing/RES4LYF"
call :get_node "ComfyUI-Crystools"           "https://github.com/crystian/ComfyUI-Crystools"
call :get_node "comfyui_controlnet_aux"      "https://github.com/Fannovel16/comfyui_controlnet_aux"

popd

:: ── DOWNLOAD MODELS IF MISSING ─────────────────────────────
echo(
echo -------- Checking QWEN IMAGE model files --------
pushd models

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

popd

:: ── DONE ────────────────────────────────────────────────────
echo(
echo -------------------------------------------------------------
echo   All QWEN IMAGE EDIT models and nodes are now installed/updated.
echo -------------------------------------------------------------
pause
exit /b



:: ==============================================================

::  SUBROUTINE ▸ get_node
::  Clone when absent, otherwise pull; always (re)install requirements
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



::  SUBROUTINE ▸ grab
::  Download file only if missing
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