@echo off
setlocal

echo ===============================================
echo   Voice Conversion WebUI Installer
echo ===============================================
echo.
echo Select your GPU type:
echo   [1] NVIDIA GPU
echo   [2] AMD / Intel GPU
echo.

set /p gpu_choice="Enter 1 or 2: "

if "%gpu_choice%"=="1" (
    echo You selected NVIDIA GPU
    set "RVC_URL=https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/RVC1006Nvidia.7z"
) else if "%gpu_choice%"=="2" (
    echo You selected AMD/Intel GPU
    set "RVC_URL=https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/RVC1006AMD_Intel.7z"
) else (
    echo Invalid choice. Defaulting to NVIDIA.
    set "RVC_URL=https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/RVC1006Nvidia.7z"
)

REM ========================================================
REM Ensure 7-Zip is installed
REM ========================================================
if not exist "%ProgramFiles%\7-Zip\7z.exe" (
    echo 7zip not found, installing...
    curl -L -o 7zip_installer.exe https://www.7-zip.org/a/7z2201-x64.exe
    start /wait "" "7zip_installer.exe" /S
    del "7zip_installer.exe"
)

REM ========================================================
REM Download the selected package
REM ========================================================
echo Downloading package...
curl -L -o RVC1006.7z %RVC_URL%

REM ========================================================
REM Extract the archive
REM ========================================================
"%ProgramFiles%\7-Zip\7z.exe" x "RVC1006.7z" -y

REM Navigate into the extracted folder
cd RVC1006*

REM Run the go-web.bat file
call go-web.bat

endlocal
