@echo off
rem hermes-pmoves - Windows shim; delegates to the canonical bash script
rem Repo root is baked in at install time by pmoves/tools/install_tools.py.
rem bash resolution: on many fleet nodes System32\bash.exe (the WSL stub)
rem shadows Git Bash on PATH, so probe the standard Git for Windows location
rem first and only fall back to PATH bash.
rem pushd so the bash script's `git rev-parse --show-toplevel` resolves the repo
rem even when the shim is invoked from outside it.
setlocal
set "REPO_ROOT=__PMOVES_REPO_ROOT__"
set "BASH="
if exist "%ProgramFiles%\Git\bin\bash.exe" set "BASH=%ProgramFiles%\Git\bin\bash.exe"
if not defined BASH if exist "%ProgramFiles(x86)%\Git\bin\bash.exe" set "BASH=%ProgramFiles(x86)%\Git\bin\bash.exe"
if not defined BASH set "BASH=bash"
pushd "%REPO_ROOT%"
"%BASH%" pmoves/scripts/hermes-pmoves %*
set "EC=%ERRORLEVEL%"
popd
exit /b %EC%
