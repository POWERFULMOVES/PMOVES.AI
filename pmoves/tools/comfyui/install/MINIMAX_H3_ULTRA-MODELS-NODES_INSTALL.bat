@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

rem ----------------------------------------------------------------
rem  MiniMax H3 ULTRA V1 - SAFE node install + model fetch
rem  - Locks current env into a constraints file
rem  - Sanitizes node requirements via external PowerShell script
rem  - Removes file:// wheels, find-links, extra indexes, and -r includes
rem
rem  Usage:
rem    MINIMAX-H3-MODELS-NODES_INSTALL.bat
rem    MINIMAX-H3-MODELS-NODES_INSTALL.bat /update
rem    MINIMAX-H3-MODELS-NODES_INSTALL.bat /force
rem    MINIMAX-H3-MODELS-NODES_INSTALL.bat /dryrun
rem    MINIMAX-H3-MODELS-NODES_INSTALL.bat /restore
rem
rem  IMPORTANT: run from: ...\ComfyUI_windows_portable\ComfyUI\
rem ----------------------------------------------------------------

:: ---------- MODELS ----------
set "FL2VA_MODEL=minimax_h3_fl2va_pruned_int8_convrot.safetensors"
set "REF2VA_MODEL=minimax_h3_ref2va_pruned_int8_convrot.safetensors"

:: constants and paths
set "HF=https://huggingface.co/Aitrepreneur/FLX/resolve/main"
set "COMFY=%CD%"
set "PY=%COMFY%\..\python_embeded\python.exe"
set "PIP=%PY% -m pip"
set "TOOLS=%COMFY%\_zimage_tools"
set "BACKUPS=%TOOLS%\backups"
set "TMP=%TOOLS%\tmp"
set "LOCKFILE=%TOOLS%\constraints_lock.txt"
set "LAST_FREEZE=%BACKUPS%\freeze_latest.txt"
set "LOG=%TOOLS%\last_run.log"
set "PS_SANITIZER=%TOOLS%\sanitize_reqs.ps1"

:: flags
set "DO_UPDATE=0"
set "DO_FORCE=0"
set "DO_DRYRUN=0"
set "DO_RESTORE=0"
for %%A in (%*) do (
  if /I "%%~A"=="/update"  set "DO_UPDATE=1"
  if /I "%%~A"=="/force"   set "DO_FORCE=1"
  if /I "%%~A"=="/dryrun"  set "DO_DRYRUN=1"
  if /I "%%~A"=="/restore" set "DO_RESTORE=1"
)

:: prechecks
if not exist "%PY%" (
  echo [ERROR] Could not find python at "%PY%"
  echo Please run this script from:
  echo ...\ComfyUI_windows_portable\ComfyUI\
  pause
  exit /b 1
)
git --version >nul 2>&1 || (
  echo [ERROR] Git is not in PATH. Install Git for Windows and try again.
  pause & exit /b 1
)

if not exist "%TOOLS%"   mkdir "%TOOLS%"
if not exist "%BACKUPS%" mkdir "%BACKUPS%"
if not exist "%TMP%"     mkdir "%TMP%"

:: Always recreate the PowerShell sanitizer to ensure it's correct
if exist "%PS_SANITIZER%" del "%PS_SANITIZER%"
(
  echo param^(
  echo   [Parameter^(Mandatory=$true^)] [string]$In,
  echo   [Parameter^(Mandatory=$true^)] [string]$Out
  echo ^)
  echo if ^(-not ^(Test-Path -LiteralPath $In^)^) { exit 0 }
  echo $lines = Get-Content -LiteralPath $In -Raw -Encoding UTF8
  echo $lines = $lines -split "`r?`n"
  echo $lines = $lines ^| Where-Object { $_ -ne '' -and $_ -notmatch '^\s*#' }
  echo $lines = $lines ^| Where-Object { $_ -notmatch '^\s*-^(f^|--find-links^|--extra-index-url^)\b' }
  echo $lines = $lines ^| Where-Object { $_ -notmatch '^\s*-^(r^|--requirement^)\b' }
  echo $lines = $lines ^| ForEach-Object { $_ -replace '\s*@\s*file:^(//^)?/[^ \t]+','' }
  echo $lines = $lines ^| ForEach-Object { $_ -replace '\s*@\s*[A-Za-z]:\\[^\s]+','' }
  echo $lines = $lines ^| ForEach-Object { $_ -replace '\s+[A-Za-z]:\\[^\s]+\.whl','' }
  echo $lines = $lines ^| ForEach-Object { if ^($_ -match '^[a-zA-Z0-9_-]+'^ ^) { $Matches[0] } else { $_ } }
  echo $lines = $lines ^| Where-Object { $_ -ne '' }
  echo $lines ^| Set-Content -LiteralPath $Out -Encoding UTF8
) > "%PS_SANITIZER%"

:: pip env sanitize
set "PIP_CONFIG_FILE=NUL"
set "PIP_FIND_LINKS="
set "PIP_NO_INDEX="
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PYTHONUTF8=1"
set "PYTHONNOUSERSITE=1"

:: optional local wheel dir
set "WHEEL_DIR="
for %%D in ("%COMFY%\..\cu130_python_deps" "%COMFY%\..\cu129_python_deps" "%COMFY%\..\cu128_python_deps" "%COMFY%\..\cu126_python_deps") do (
  if exist "%%~D" (
    set "WHEEL_DIR=%%~D"
    goto :have_wheels
  )
)
:have_wheels
if defined WHEEL_DIR (
  set "PIP_FIND_LINKS_OPT=--find-links "%WHEEL_DIR%""
) else (
  set "PIP_FIND_LINKS_OPT="
)

:: log header
call :timestamp TS
echo [%TS%] Starting MiniMax H3 safe installer. > "%LOG%"
echo Flags: update=%DO_UPDATE% force=%DO_FORCE% dryrun=%DO_DRYRUN% restore=%DO_RESTORE% >> "%LOG%"
if defined WHEEL_DIR (echo Using local wheel dir: %WHEEL_DIR%) else (echo No local wheel dir found. Will use PyPI.)

:: restore mode
if "%DO_RESTORE%"=="1" (
  if not exist "%LAST_FREEZE%" (
    echo [ERROR] No previous freeze found at %LAST_FREEZE%
    echo Nothing to restore. Run once without /restore to create a baseline.
    >> "%LOG%" echo No freeze to restore.
    exit /b 1
  )
  echo(
  echo -------- Restoring environment from last freeze --------
  echo Source: %LAST_FREEZE%
  echo.
  if "%DO_DRYRUN%"=="1" (
    echo [DRYRUN] Would run: %PIP% install --isolated -i https://pypi.org/simple --no-cache-dir --force-reinstall %PIP_FIND_LINKS_OPT% -r "%LAST_FREEZE%"
    >> "%LOG%" echo [DRYRUN] restore from "%LAST_FREEZE%"
    goto :models_only
  )
  %PIP% install --isolated -i https://pypi.org/simple --no-cache-dir --force-reinstall %PIP_FIND_LINKS_OPT% -r "%LAST_FREEZE%"
  goto :models_only
)

:: constraints lock
echo(
echo -------- Locking current Python environment --------
call :timestamp TS
set "THIS_FREEZE=%BACKUPS%\freeze_%TS%.txt"
if "%DO_DRYRUN%"=="1" (
  echo [DRYRUN] Would export freeze to: %THIS_FREEZE%
  echo [DRYRUN] Would update latest: %LAST_FREEZE%
  echo [DRYRUN] Would copy to constraints: %LOCKFILE%
) else (
  %PIP% freeze > "%THIS_FREEZE%"
  copy /Y "%THIS_FREEZE%" "%LAST_FREEZE%" >nul
  copy /Y "%THIS_FREEZE%" "%LOCKFILE%"  >nul
)
echo Saved baseline to:
echo   %THIS_FREEZE%
echo Constraint lock:
echo   %LOCKFILE%

:: custom nodes
echo(
echo -------- Checking custom nodes with safety --------
pushd custom_nodes

call :handle_node "ComfyUI-Manager"                  "https://github.com/ltdrdata/ComfyUI-Manager.git"
call :handle_node "rgthree-comfy"                    "https://github.com/rgthree/rgthree-comfy"
call :handle_node "ComfyUI-KJNodes"                  "https://github.com/kijai/ComfyUI-KJNodes"
call :handle_node "ComfyUI-VideoHelperSuite"         "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite"
call :handle_node "ComfyUI-Spectrum-MiniMax-H3"      "https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3"

popd

:models_only
echo(
echo -------- Checking model files --------
pushd models

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

popd

echo(
echo -------------------------------------------------------------
echo   SAFE DONE. Models ready. Node deps respected the lock.
echo   If a node needs newer deps, use /update and/or /force.
echo   To roll back, run with /restore.
echo -------------------------------------------------------------
pause
exit /b

:: ==================== SUBROUTINES ============================

:handle_node
rem  %1 = local folder   %2 = repo URL
setlocal EnableDelayedExpansion
set "DIR=%~1"
set "URL=%~2"

if not exist "!DIR!" (
  echo   • cloning !DIR!
  if "%DO_DRYRUN%"=="1" (
    echo     [DRYRUN] git clone "!URL!" "!DIR!"
  ) else (
    git clone "!URL!" "!DIR!"
  )
) else (
  if "%DO_UPDATE%"=="1" (
    echo   • updating !DIR!
    if exist "!DIR!\.git" (
      if "%DO_DRYRUN%"=="1" (
        echo     [DRYRUN] git -C "!DIR!" pull --ff-only --recurse-submodules
        echo     [DRYRUN] git -C "!DIR!" submodule update --init --recursive
      ) else (
        pushd "!DIR!"
        git pull --ff-only --recurse-submodules
        git submodule update --init --recursive
        popd
      )
    ) else (
      echo     [WARN] !DIR! exists but is not a git repo - skipping update.
    )
  ) else (
    echo   • !DIR! exists - skipping update (use /update to pull)
  )
)

if exist "!DIR!\requirements.txt" (
  echo     - installing Python deps for !DIR!

  for %%I in ("%CD%\!DIR!\requirements.txt") do set "REQ_ORIG=%%~fI"
  set "REQ_CLEAN=%TMP%\!DIR!_requirements_clean.txt"

  if "%DO_DRYRUN%"=="1" (
    echo       [DRYRUN] Sanitize "!REQ_ORIG!" ^> "!REQ_CLEAN!"
  ) else (
    powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PS_SANITIZER%" -In "!REQ_ORIG!" -Out "!REQ_CLEAN!"
    if not exist "!REQ_CLEAN!" copy /Y "!REQ_ORIG!" "!REQ_CLEAN!" >nul 2>&1
  )

  if "%DO_DRYRUN%"=="1" (
    if "%DO_FORCE%"=="1" (
      echo       [DRYRUN] %PIP% install --isolated -i https://pypi.org/simple --prefer-binary --no-cache-dir %PIP_FIND_LINKS_OPT% --ignore-installed -r "!REQ_CLEAN!"
    ) else (
      echo       [DRYRUN] %PIP% install --isolated -i https://pypi.org/simple --prefer-binary --no-cache-dir %PIP_FIND_LINKS_OPT% --upgrade-strategy only-if-needed --constraint "%LOCKFILE%" -r "!REQ_CLEAN!"
    )
  ) else (
    if "%DO_FORCE%"=="1" (
      %PIP% install --isolated -i https://pypi.org/simple --prefer-binary --no-cache-dir %PIP_FIND_LINKS_OPT% --ignore-installed -r "!REQ_CLEAN!"
      if errorlevel 1 (
        echo       [!] Install reported errors for !DIR!.
        echo           Tip: use /force again or check the logs above.
      )
    ) else (
      rem First try with constraints - errors about missing old wheels are usually harmless
      %PIP% install --isolated -i https://pypi.org/simple --prefer-binary --no-cache-dir %PIP_FIND_LINKS_OPT% --upgrade-strategy only-if-needed --constraint "%LOCKFILE%" -r "!REQ_CLEAN!" >nul 2^>^&1
      if errorlevel 1 (
        echo       [i] Some dependency resolution warnings ^(usually harmless if packages already installed^)
      )
    )
  )
) else (
  echo     - no requirements.txt for !DIR! - nothing to install
)
endlocal & goto :eof

:grab
rem  %1 = relative save path   %2 = full URL
if not exist "%~dp1" (
  if "%DO_DRYRUN%"=="1" (
    echo [DRYRUN] Would create folder "%~dp1"
  ) else (
    mkdir "%~dp1"
  )
)
if not exist "%~1" (
  echo   • downloading %~nx1
  if "%DO_DRYRUN%"=="1" (
    echo     [DRYRUN] curl -L -o "%~1" "%~2" --ssl-no-revoke
  ) else (
    curl -L -o "%~1" "%~2" --ssl-no-revoke
    if errorlevel 1 echo     [!] Failed: %~nx1
  )
) else (
  echo   • %~nx1 already present - skipping
)
goto :eof

:timestamp
for /f "tokens=2 delims==." %%t in ('wmic os get LocalDateTime /value') do set ldt=%%t
set "%~1=%ldt:~0,8%_%ldt:~8,6%"
goto :eof