@echo off
rem pmoves-mini - Windows shim for the PMOVES Mini CLI
rem Repo root is baked in at install time by pmoves/tools/install_tools.py
rem (re-run install-tools after moving the repo).
setlocal
set "REPO_ROOT=__PMOVES_REPO_ROOT__"
set "PYTHONPATH=%REPO_ROOT%;%PYTHONPATH%"
if defined PMOVES_PYTHON set "PY=%PMOVES_PYTHON%" & goto run
if exist "%REPO_ROOT%\pmoves\.venv-pmoves\Scripts\python.exe" set "PY=%REPO_ROOT%\pmoves\.venv-pmoves\Scripts\python.exe" & goto run
set "PY=python"
:run
"%PY%" "%REPO_ROOT%\pmoves\tools\mini_cli.py" %*
exit /b %ERRORLEVEL%
