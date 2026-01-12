@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
title Triton + SageAttention auto-installer

rem -------------------------------------------------------------
rem  Run this from:
rem     ...\ComfyUI_windows_portable\python_embeded\
rem  Detect Torch and CUDA, then install matching Triton and SageAttention
rem -------------------------------------------------------------

set "PY=%CD%\python.exe"

if not exist "%PY%" (
  echo [ERROR] No python.exe found here. Make sure you are running this from:
  echo   ...\ComfyUI_windows_portable\python_embeded\
  pause & exit /b 1
)

echo === Detecting Torch and CUDA ===
set "TMPVER=%TEMP%\torch_cuda_detect_%RANDOM%.txt"
"%PY%" -c "import sys; import torch; print(torch.__version__); print(getattr(torch.version,'cuda',None) or 'unknown')" > "%TMPVER%" 2>nul

if errorlevel 1 (
  echo [ERROR] Could not import torch. Launch ComfyUI once or install torch in this python.
  if exist "%TMPVER%" del "%TMPVER%" >nul 2>&1
  pause & exit /b 1
)

set "TORCH_VER="
set "CUDA_VER="

for /f "usebackq delims=" %%A in ("%TMPVER%") do (
  if not defined TORCH_VER (
    set "TORCH_VER=%%A"
  ) else if not defined CUDA_VER (
    set "CUDA_VER=%%A"
  )
)
del "%TMPVER%" >nul 2>&1

if not defined TORCH_VER (
  echo [ERROR] Torch version not detected.
  pause & exit /b 1
)

if not defined CUDA_VER set "CUDA_VER=unknown"

echo Torch version: %TORCH_VER%
echo CUDA version : %CUDA_VER%

rem -------------------------------------------------------------
rem  Decide CUDA short tag (CUSHORT)
rem  1) Prefer the build tag in torch.__version__ like +cu129
rem  2) Fallback to parsing torch.version.cuda
rem  Map cu129 to cu128 on purpose
rem -------------------------------------------------------------
set "CUSHORT="
set "TORCH_TAG="

for /f "tokens=2 delims=+ " %%Z in ("%TORCH_VER%") do set "TORCH_TAG=%%Z"
if defined TORCH_TAG (
  if /i "%TORCH_TAG%"=="cpu" set "TORCH_TAG="
  if /i "%TORCH_TAG%"=="cu130" set "CUSHORT=cu130"
  if /i "%TORCH_TAG%"=="cu129" set "CUSHORT=cu128"
  if /i "%TORCH_TAG%"=="cu128" set "CUSHORT=cu128"
  if /i "%TORCH_TAG%"=="cu126" set "CUSHORT=cu126"
  if /i "%TORCH_TAG%"=="cu124" set "CUSHORT=cu124"
)

if not defined CUSHORT (
  if /i "%CUDA_VER%"=="unknown" (
    echo [WARN] CUDA not detected from runtime. Will default later.
  ) else (
    for /f "tokens=1,2 delims=." %%C in ("%CUDA_VER%") do (
      set "CUA=%%C"
      set "CUB=%%D"
    )
    if "%CUA%"=="13" set "CUSHORT=cu130"
    if "%CUA%"=="12" (
      if "%CUB%"=="9" (
        set "CUSHORT=cu128"
        echo [INFO] Mapping CUDA 12.9 to cu128 wheels for compatibility.
      ) else (
        if "%CUB%"=="8" set "CUSHORT=cu128"
        if "%CUB%"=="6" set "CUSHORT=cu126"
        if "%CUB%"=="4" set "CUSHORT=cu124"
      )
    )
  )
)

echo CUDA short tag: %CUSHORT%

rem -------------------------------------------------------------
rem  Parse Torch major.minor for decisions
rem -------------------------------------------------------------
set "TMAJOR="
set "TMINOR="
for /f "tokens=1,2 delims=." %%M in ("%TORCH_VER%") do (
  set "TMAJOR=%%M"
  set "TMINOR=%%N"
)
set "TMINORNUM="
for /f "tokens=1 delims=." %%X in ("%TMINOR%") do set "TMINORNUM=%%X"

echo.
echo === Upgrading pip ===
"%PY%" -m pip install -U pip

echo.
echo === Installing Triton ===
set "TRITON_SPEC=triton-windows<3.5"
if "%TMAJOR%"=="2" (
  if defined TMINORNUM if %TMINORNUM% GEQ 9 set "TRITON_SPEC=triton-windows<3.6"
)
"%PY%" -m pip install --no-cache-dir --upgrade "%TRITON_SPEC%"

echo.
echo === Picking SageAttention wheel ===
set "SAGE_URL="

rem Torch 2.9+ use post4 universal wheels (prefer cu130, else cu128)
if "%TMAJOR%"=="2" if defined TMINORNUM if %TMINORNUM% GEQ 9 (
  if "%CUSHORT%"=="cu130" set "SAGE_URL=https://github.com/woct0rdho/SageAttention/releases/download/v2.2.0-windows.post4/sageattention-2.2.0+cu130torch2.9.0andhigher.post4-cp39-abi3-win_amd64.whl"
  if not defined SAGE_URL if "%CUSHORT%"=="cu128" set "SAGE_URL=https://github.com/woct0rdho/SageAttention/releases/download/v2.2.0-windows.post4/sageattention-2.2.0+cu128torch2.9.0andhigher.post4-cp39-abi3-win_amd64.whl"
)

rem Fallback exact combos for Torch 2.5–2.9 (post3 wheels)
if not defined SAGE_URL if "%TMAJOR%"=="2" (
  if "%TMINOR%"=="9" (
    if "%CUSHORT%"=="cu130" set "SAGE_URL=https://github.com/woct0rdho/SageAttention/releases/download/v2.2.0-windows.post3/sageattention-2.2.0+cu130torch2.9.0.post3-cp39-abi3-win_amd64.whl"
    if "%CUSHORT%"=="cu128" set "SAGE_URL=https://github.com/woct0rdho/SageAttention/releases/download/v2.2.0-windows.post3/sageattention-2.2.0+cu128torch2.9.0.post3-cp39-abi3-win_amd64.whl"
  )
  if "%TMINOR%"=="8" (
    if "%CUSHORT%"=="cu128" set "SAGE_URL=https://github.com/woct0rdho/SageAttention/releases/download/v2.2.0-windows.post3/sageattention-2.2.0+cu128torch2.8.0.post3-cp39-abi3-win_amd64.whl"
  )
  if "%TMINOR%"=="7" (
    if "%CUSHORT%"=="cu128" set "SAGE_URL=https://github.com/woct0rdho/SageAttention/releases/download/v2.2.0-windows.post3/sageattention-2.2.0+cu128torch2.7.1.post3-cp39-abi3-win_amd64.whl"
  )
  if "%TMINOR%"=="6" (
    if "%CUSHORT%"=="cu126" set "SAGE_URL=https://github.com/woct0rdho/SageAttention/releases/download/v2.2.0-windows.post3/sageattention-2.2.0+cu126torch2.6.0.post3-cp39-abi3-win_amd64.whl"
  )
  if "%TMINOR%"=="5" (
    if "%CUSHORT%"=="cu124" set "SAGE_URL=https://github.com/woct0rdho/SageAttention/releases/download/v2.2.0-windows.post3/sageattention-2.2.0+cu124torch2.5.1.post3-cp39-abi3-win_amd64.whl"
  )
)

rem If still nothing for 2.9+, default to cu128 post4
if not defined SAGE_URL if "%TMAJOR%"=="2" if defined TMINORNUM if %TMINORNUM% GEQ 9 (
  echo [WARN] CUDA not matched. Defaulting to cu128 post4 for Torch 2.9+
  set "SAGE_URL=https://github.com/woct0rdho/SageAttention/releases/download/v2.2.0-windows.post4/sageattention-2.2.0+cu128torch2.9.0andhigher.post4-cp39-abi3-win_amd64.whl"
)

rem Final attempt: try installing one of the post4 wheels directly, stop at first success
if not defined SAGE_URL (
  for %%W in (
    https://github.com/woct0rdho/SageAttention/releases/download/v2.2.0-windows.post4/sageattention-2.2.0+cu130torch2.9.0andhigher.post4-cp39-abi3-win_amd64.whl
    https://github.com/woct0rdho/SageAttention/releases/download/v2.2.0-windows.post4/sageattention-2.2.0+cu128torch2.9.0andhigher.post4-cp39-abi3-win_amd64.whl
  ) do (
    echo Trying wheel:
    echo   %%W
    "%PY%" -m pip install --no-cache-dir "%%W" && (
      set "SAGE_URL=%%W"
      goto :SAGE_DONE
    )
  )
)

if defined SAGE_URL (
  echo Installing SageAttention:
  echo   %SAGE_URL%
  "%PY%" -m pip install --no-cache-dir "%SAGE_URL%" || set "SAGE_URL="
)

:SAGE_DONE
if not defined SAGE_URL (
  echo [WARN] Wheel not selected or failed. Trying source fallback...
  "%PY%" -m pip install --no-build-isolation --prefer-binary "sageattention==1.0.6" ^
    || "%PY%" -m pip install --no-build-isolation "git+https://github.com/woct0rdho/SageAttention.git" ^
    || (echo [ERROR] SageAttention source install failed. & pause & exit /b 1)
)

echo.
echo === Optional Python 3.13 include/libs for Triton ===
set "ZIP_URL=https://github.com/woct0rdho/triton-windows/releases/download/v3.0.0-windows.post1/python_3.13.2_include_libs.zip"
set "ZIP_FILE=python_3.13_libs.zip"

if not exist "%CD%\include" (
  echo Downloading python include/libs...
  curl -L -o "%ZIP_FILE%" "%ZIP_URL%"
  tar -xf "%ZIP_FILE%" -C "%CD%" 2>nul
  if errorlevel 1 powershell -NoP -C "Expand-Archive -Force '%ZIP_FILE%' '%CD%'"
  del "%ZIP_FILE%"
) else (
  echo Includes already present. Skipping
)

echo.
echo === Verifying imports ===
"%PY%" -c "import triton, sageattention; print('OK')" 1>nul 2>nul
if errorlevel 1 (
  echo [ERROR] Post-install import failed. Share the error lines above.
  pause & exit /b 1
)

echo.
echo -------------------------------------------------------------
echo Triton and SageAttention installation finished. All good.
echo -------------------------------------------------------------
pause
exit /b
