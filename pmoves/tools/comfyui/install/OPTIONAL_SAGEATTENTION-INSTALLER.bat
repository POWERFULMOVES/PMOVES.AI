@echo off
setlocal enabledelayedexpansion

rem -------------------------------------------------------------
rem  Optional SageAttention installer V1               by Aitrepreneur
rem
rem  Supports compatible RTX 30, RTX 40 and RTX 50 series setups.
rem  Run this AFTER the MiniMax H3 main installer.
rem -------------------------------------------------------------

set "PORTABLE=%CD%"
set "PY=%PORTABLE%\python_embeded\python.exe"
set "UPSTREAM=%PORTABLE%\comfyui_triton_sageattention_v0.8.10.py"
set "UPSTREAM_URL=https://raw.githubusercontent.com/DazzleML/comfyui-triton-and-sageattention-installer/v0.8.10/comfyui_triton_sageattention.py"
set "NORMAL_RUN=%PORTABLE%\run_nvidia_gpu.bat"
set "NORMAL_BACKUP=%PORTABLE%\run_nvidia_gpu_AITREPRENEUR_BACKUP.bat"
set "SAGE_RUN=%PORTABLE%\run_nvidia_gpu_SAGEATTENTION.bat"

echo(
echo -------- Checking ComfyUI portable --------
if not exist "%PY%" (
    echo This installer must be placed directly inside your ComfyUI_windows_portable folder.
    pause
    exit /b 1
)

if not exist "%PORTABLE%\ComfyUI\main.py" (
    echo ComfyUI main.py was not found.
    pause
    exit /b 1
)

echo(
echo -------- Detecting GPU, PyTorch and CUDA --------
"%PY%" -s -c "import torch; print('PyTorch:',torch.__version__); print('CUDA:',torch.version.cuda); print('GPU:',torch.cuda.get_device_name(0)); print('Capability:',torch.cuda.get_device_capability(0))"
if errorlevel 1 (
    echo PyTorch or CUDA is not working.
    pause
    exit /b 1
)

echo(
echo -------- Downloading the pinned SageAttention installer --------
curl -L -o "%UPSTREAM%" "%UPSTREAM_URL%" --ssl-no-revoke
if errorlevel 1 (
    echo SageAttention installer download failed.
    pause
    exit /b 1
)

rem Preserve the normal launcher. The upstream installer creates its own
rem SageAttention launcher using the best compatible Triton/SageAttention wheel.
if exist "%NORMAL_RUN%" copy /y "%NORMAL_RUN%" "%NORMAL_BACKUP%" >nul

echo(
echo -------- Installing the compatible Triton and SageAttention build --------
"%PY%" -s "%UPSTREAM%" --install --base-path "%PORTABLE%" --python portable --sage-version auto --non-interactive
if errorlevel 1 (
    echo SageAttention installation failed.
    if exist "%NORMAL_BACKUP%" copy /y "%NORMAL_BACKUP%" "%NORMAL_RUN%" >nul
    pause
    exit /b 1
)

rem The maintained installer writes its SageAttention command to
rem run_nvidia_gpu.bat. Keep it as a separate launcher and restore the normal one.
if exist "%NORMAL_RUN%" copy /y "%NORMAL_RUN%" "%SAGE_RUN%" >nul
if exist "%NORMAL_BACKUP%" (
    copy /y "%NORMAL_BACKUP%" "%NORMAL_RUN%" >nul
    del /q "%NORMAL_BACKUP%" >nul 2>&1
)

if not exist "%SAGE_RUN%" (
    echo SageAttention installed, but its launcher was not created.
    pause
    exit /b 1
)

echo(
echo -------- Cleaning temporary installer files --------
del /q "%UPSTREAM%" >nul 2>&1
del /q "%PORTABLE%\python_*_include_libs.zip" >nul 2>&1
del /q "%PORTABLE%\comfyui_install.log" >nul 2>&1

echo(
echo -------------------------------------------------------------
echo  SageAttention installation complete!
echo -------------------------------------------------------------
echo(
echo Normal launcher:
echo   ComfyUI_windows_portable\run_nvidia_gpu.bat
echo(
echo SageAttention launcher:
echo   ComfyUI_windows_portable\run_nvidia_gpu_SAGEATTENTION.bat
echo(
pause
exit /b
