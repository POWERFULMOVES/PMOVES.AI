@echo off
setlocal enabledelayedexpansion

rem ----------------------------------------------------------------
rem
rem  IMPORTANT: Put this file in your ...\ComfyUI_windows_portable\ComfyUI\
rem  directory and run it from there.
rem ----------------------------------------------------------------

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
call :get_node "rgthree-comfy"               "https://github.com/rgthree/rgthree-comfy"
call :get_node "VibeVoice-ComfyUI"           "https://github.com/Enemyx-net/VibeVoice-ComfyUI"
call :get_node "TTS-Audio-Suite"             "https://github.com/diodiogod/TTS-Audio-Suite"


popd

:: ── DONE ────────────────────────────────────────────────────
echo(
echo -------------------------------------------------------------
echo   Vibevoice and RVC nodes are now installed/updated.
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