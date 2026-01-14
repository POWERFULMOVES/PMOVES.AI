@echo off
setlocal enabledelayedexpansion

:: Check for administrative privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Please run this script as an administrator.
    pause
    exit
)

:: Variables
set FFMPEG_URL=https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
set FFMPEG_DIR=%USERPROFILE%\Documents\ffmpeg

:: Ensure the directory exists
if not exist "%FFMPEG_DIR%" mkdir "%FFMPEG_DIR%"

:: Download ffmpeg
echo Downloading ffmpeg...
curl -L %FFMPEG_URL% -o "%FFMPEG_DIR%\ffmpeg.zip" --ssl-no-revoke
if errorlevel 1 (
    echo Failed to download ffmpeg. Please check your internet connection and URL.
    goto end_script
)

:: Extract ffmpeg
echo Extracting ffmpeg...
powershell -command "& {Expand-Archive -Path '%FFMPEG_DIR%\ffmpeg.zip' -DestinationPath '%FFMPEG_DIR%' -Force}"
if errorlevel 1 (
    echo Failed to extract ffmpeg. Please check the zip file and destination path.
    goto end_script
)

:: Rename the extracted folder
echo Renaming the extracted folder...
for /d %%A in ("%FFMPEG_DIR%\ffmpeg-*") do (
    set "EXTRACTED_FOLDER=%%A"
)
if defined EXTRACTED_FOLDER (
    ren "!EXTRACTED_FOLDER!" ffmpeg_folder
) else (
    echo No extracted folder found matching the expected pattern.
    goto end_script
)

:: Set the path to the bin directory
set FFMPEG_BIN=%FFMPEG_DIR%\ffmpeg_folder\bin

:: Print found path for debugging
echo Found ffmpeg binary path: %FFMPEG_BIN%

:: Check if PATH already contains the ffmpeg binary path
echo Checking if PATH needs update...
reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" | findstr /C:"%FFMPEG_BIN%" > nul
if errorlevel 1 (
    :: Update the system PATH using PowerShell
    echo Updating system PATH...
    powershell -command "[Environment]::SetEnvironmentVariable('PATH', [Environment]::GetEnvironmentVariable('PATH', [EnvironmentVariableTarget]::Machine) + ';%FFMPEG_BIN%', [EnvironmentVariableTarget]::Machine)"
    if errorlevel 0 (
        echo PATH updated successfully.
    ) else (
        echo Failed to update PATH.
    )
) else (
    echo PATH already contains ffmpeg binary path.
)

:end_script
pause
endlocal
