@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

rem ============================================================================
rem  MiniMax-H3 (NVFP4) ▸ download models + clone aux nodes  [5090 / Blackwell]
rem
rem  H3 = audio+video generation (t2va / fl2va / ref2va). On Blackwell (RTX 5090)
rem  the NVFP4 (FP4) UNET builds HALVE the diffusion-model size vs INT8-ConvRot
rem  (10.86 GiB vs 20.94 GiB per UNET — a verified 48% cut). Peak VRAM is
rem  SEQUENTIAL residency (encoder ~26 GiB is unloaded before the UNET samples),
rem  not a sum — it fits 32 GB.  Total download ≈ 55.5 GB (63 GB with the
rem  optional prompt-enhancement tail).
rem
rem  The H3 nodes are NATIVE in the PMOVES-Creator fork
rem  (comfy_extras/nodes_minimax_h3.py) and load in stock ComfyUI — there is NO
rem  H3 custom node to clone. Loaders are dropdowns, so filenames are free (the
rem  files keep their real repo names; no renaming). Only the 3 workflow-support
rem  node packs below are cloned.
rem
rem  !! ENCODER IS AN ABLITERATED / UNCENSORED FINE-TUNE (Qwen3-VL-32B ultra-
rem  !! uncensored-heretic). No stock-Qwen3-VL H3 encoder exists. For UNFCU /
rem  !! client-facing work this is an EXPLICIT OPERATOR DECISION — see README.
rem
rem  RUNTIME-AGNOSTIC: set COMFY_ROOT to target a specific ComfyUI, else run from
rem  the ComfyUI root (needs models\ and custom_nodes\).
rem  Options (env):
rem    COMFY_ROOT     ComfyUI root (default: current dir)
rem    H3_PROFILE     NVFP4 (default, 8-12GB class) | NVFP4-HQ (16-24GB class)
rem    INSTALL_TAIL   1 to also fetch the optional 7.6 GB prompt-enhancement tail
rem ============================================================================

:: ── RESOLVE COMFY ROOT (parametric) ─────────────────────────────
if defined COMFY_ROOT (set "COMFY=%COMFY_ROOT%") else (set "COMFY=%CD%")
if not exist "%COMFY%\models" (
    echo [ERROR] "%COMFY%" is not a ComfyUI root ^(no models\ dir^). Set COMFY_ROOT or cd there.
    pause & exit /b 1
)
if not exist "%COMFY%\custom_nodes" (echo [ERROR] "%COMFY%" has no custom_nodes\ dir. & pause & exit /b 1)
echo [INFO] ComfyUI root: %COMFY%

if not defined H3_PROFILE set "H3_PROFILE=NVFP4"
if not defined INSTALL_TAIL set "INSTALL_TAIL=0"
echo [INFO] UNET profile: %H3_PROFILE%   optional tail: %INSTALL_TAIL%

:: ── PYTHON (ComfyUI portable) — used to bootstrap the hf CLI ─────
set "PY=%COMFY%\..\python_embeded\python.exe"
if not exist "%PY%" set "PY=python"

git --version >nul 2>&1 || (echo [ERROR] Git not in PATH – install Git for Windows. & pause & exit /b 1)
hf --version >nul 2>&1 || (
    echo [INFO] Installing huggingface_hub CLI + hf_transfer into the embedded python...
    "%PY%" -m pip install -U "huggingface_hub[cli]" hf_transfer
)
set "HF_HUB_ENABLE_HF_TRANSFER=1"
rem  For gated/rate-limited pulls authenticate once first:  hf auth login

:: ── VERIFIED SOURCES (hf_fs byte-exact, 2026-08-09 recon) ───────
set "REPO_QUANTS=DmitryDB/MiniMax-H3-ComfyUI-Quants"
set "REPO_ENCODER=OTMFLY/Qwen3-VL-32B-Ultra-Heretic-MiniMax-H3-ComfyUI-INT8-ConvRot"
set "ENC_MAIN=qwen3vl_32b_minimax_h3_ultra_uncensored_heretic_int8_convrot.safetensors"
set "ENC_TAIL=qwen3vl_32b_minimax_h3_generation_tail_50_63_int8_convrot.safetensors"

:: ── CLONE ONLY THE 3 WORKFLOW-SUPPORT NODE PACKS ────────────────
echo(
echo -------- Custom nodes ^(H3 nodes are native — not cloned^) --------
pushd "%COMFY%\custom_nodes"
call :get_node "rgthree-comfy"            "https://github.com/rgthree/rgthree-comfy"
call :get_node "ComfyUI-KJNodes"          "https://github.com/kijai/ComfyUI-KJNodes"
call :get_node "ComfyUI-VideoHelperSuite" "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite"
popd

:: ── DOWNLOAD MODELS via hf (real repo names; flattened into subdir) ─
echo(
echo -------- Downloading MiniMax-H3 models --------
call :hf "%REPO_QUANTS%"  "FL2VA/MiniMax-H3_FL2VA-%H3_PROFILE%.safetensors"  "models\diffusion_models"
call :hf "%REPO_QUANTS%"  "Ref2VA/MiniMax-H3_Ref2VA-%H3_PROFILE%.safetensors" "models\diffusion_models"
call :hf "%REPO_QUANTS%"  "vae/MiniMax-H3_VideoVAE-FP16.safetensors"          "models\vae"
call :hf "%REPO_QUANTS%"  "vae/MiniMax-H3_AudioVAE-FP32.safetensors"          "models\vae"
echo   [REQUIRED] conditioning encoder (layers 0-49, ~24.6 GiB)
call :hf "%REPO_ENCODER%" "%ENC_MAIN%" "models\text_encoders\MiniMax-H3"
if "%INSTALL_TAIL%"=="1" (
    echo   [OPTIONAL] prompt-enhancement tail (layers 50-63, ~7.1 GiB)
    call :hf "%REPO_ENCODER%" "%ENC_TAIL%" "models\text_encoders\MiniMax-H3"
) else (
    echo   [SKIP] optional tail ^(set INSTALL_TAIL=1 to fetch^)
)

echo(
echo -------------------------------------------------------------
echo   MiniMax-H3 models + support nodes ready.
echo   Encoder dir: models\text_encoders\MiniMax-H3  (CLIPLoader type: minimax)
echo -------------------------------------------------------------
pause
exit /b


:: ==================== SUBROUTINES ============================

:get_node
set "DIR=%~1"
set "URL=%~2"
if not exist "%DIR%" (echo   • cloning %DIR% & git clone "%URL%" "%DIR%") else (
    echo   • updating %DIR%
    if exist "%DIR%\.git" (pushd "%DIR%" & git pull --ff-only & popd) else (echo     [WARN] %DIR% not a git repo – skip)
)
if exist "%DIR%\requirements.txt" ("%PY%" -m pip install --upgrade -r "%DIR%\requirements.txt")
goto :eof

:hf
rem  %1 = repo id   %2 = repo-relative file (fwd slashes)   %3 = dest subdir (rel to COMFY)
set "H_REPO=%~1"
set "H_FILE=%~2"
set "H_DIR=%COMFY%\%~3"
set "H_WIN=%H_FILE:/=\%"
for %%A in ("%H_WIN%") do set "H_BASE=%%~nxA"
if exist "%H_DIR%\%H_BASE%" (echo   • %H_BASE% already present – skip & goto :eof)
if not exist "%H_DIR%" mkdir "%H_DIR%"
echo   • downloading %H_FILE%
hf download "%H_REPO%" "%H_FILE%" --local-dir "%H_DIR%"
if errorlevel 1 (echo     [!] Download failed: %H_FILE% & goto :eof)
rem  hf preserves the repo path — flatten the leaf up into H_DIR, drop empty subdir
if not "%H_WIN%"=="%H_BASE%" (
    if exist "%H_DIR%\%H_WIN%" (
        move /Y "%H_DIR%\%H_WIN%" "%H_DIR%\%H_BASE%" >nul
        for %%D in ("%H_WIN%") do rd "%H_DIR%\%%~pD" 2>nul
    )
)
goto :eof
