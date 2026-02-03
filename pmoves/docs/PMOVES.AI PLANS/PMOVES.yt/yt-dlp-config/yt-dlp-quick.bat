@echo off
:: yt-dlp Quick Download Script
:: Usage: yt-dlp-quick.bat [URL] [options]

setlocal enabledelayedexpansion

:: Set up paths
set CONFIG_DIR=C:\Users\russe\yt-dlp-config
set DEFAULT_OUTPUT=E:\Downloads\yt-dlp

:: Create output directory if it doesn't exist
if not exist "%DEFAULT_OUTPUT%" mkdir "%DEFAULT_OUTPUT%"

:: Check if URL provided
if "%~1"=="" (
    echo.
    echo yt-dlp Quick Download Script
    echo.
    echo Usage: yt-dlp-quick.bat [URL] [options]
    echo.
    echo Quick presets:
    echo   music       - Download best audio as MP3
    echo   video       - Download best video (1080p max)
    echo   playlist    - Download entire playlist
    echo.
    echo Examples:
    echo   yt-dlp-quick.bat https://youtube.com/watch?v=VIDEO_ID music
    echo   yt-dlp-quick.bat https://youtube.com/playlist?list=PLAYLIST_ID playlist
    echo.
    pause
    exit /b 1
)

set URL=%~1
set PRESET=%~2

:: Load different presets based on argument
if "%PRESET%"=="music" (
    echo Downloading as audio MP3...
    yt-dlp --config-location "%CONFIG_DIR%\config.txt" -x --audio-format mp3 --embed-thumbnail --add-metadata "%URL%"
) else if "%PRESET%"=="video" (
    echo Downloading as video (1080p max)...
    yt-dlp --config-location "%CONFIG_DIR%\config.txt" -f "best[height<=1080]+bestaudio/best" --merge-output-format mp4 "%URL%"
) else if "%PRESET%"=="playlist" (
    echo Downloading entire playlist...
    yt-dlp --config-location "%CONFIG_DIR%\config.txt" --yes-playlist "%URL%"
) else (
    echo Downloading with default settings...
    yt-dlp --config-location "%CONFIG_DIR%\config.txt" "%URL%"
)

echo.
echo Download completed!
pause