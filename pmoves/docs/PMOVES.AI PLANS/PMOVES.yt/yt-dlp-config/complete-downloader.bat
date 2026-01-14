@echo off
:: Complete Media Downloader for Windows
:: Downloads video, audio, metadata, transcripts, and all media files

setlocal enabledelayedexpansion

:: Configuration
set CONFIG_DIR=C:\Users\russe\yt-dlp-config
set LOG_FILE=%CONFIG_DIR%\complete-downloads.log
set ERROR_LOG=%CONFIG_DIR%\download-errors.log
set DEFAULT_OUTPUT=E:\Downloads\yt-dlp\complete

:: Create directories
if not exist "%DEFAULT_OUTPUT%" mkdir "%DEFAULT_OUTPUT%"
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"

:: Logging functions
goto :main

:log_info
echo [%date% %time%] INFO: %~1 >> "%LOG_FILE%"
echo [%date% %time%] INFO: %~1
goto :eof

:log_error
echo [%date% %time%] ERROR: %~1 >> "%ERROR_LOG%"
echo [%date% %time%] ERROR: %~1
goto :eof

:show_usage
echo.
echo Complete Media Downloader - Downloads video, audio, metadata, transcripts
echo.
echo Usage: %~nx0 [URL] [QUALITY] [OPTIONS]
echo.
echo Arguments:
echo   URL       : Video/playlist/channel URL
echo   QUALITY   : Video quality (4k, 1080, 720, best)
echo   OPTIONS   : Additional options
echo.
echo Examples:
echo   %~nx0 "https://youtube.com/watch?v=VIDEO_ID" 1080
echo   %~nx0 "https://youtube.com/playlist?list=PLAYLIST_ID" 720
echo   %~nx0 "https://youtube.com/c/CHANNELNAME/videos" best
echo.
pause
exit /b 1

:main
:: Parse arguments
set URL=%~1
set QUALITY=%~2
if "%QUALITY%"=="" set QUALITY=best
set EXTRA_OPTS=%~3

:: Validate input
if "%URL%"=="" goto :show_usage

call :log_info "Starting complete download: %URL%"
call :log_info "Quality setting: %QUALITY%"

:: Determine format selector based on quality
if "%QUALITY%"=="4k" (
    set VIDEO_FORMAT=bestvideo[height^<=2160][ext=mp4]+bestaudio[ext=m4a]/best[height^<=2160]
) else if "%QUALITY%"=="1080" (
    set VIDEO_FORMAT=bestvideo[height^<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height^<=1080]
) else if "%QUALITY%"=="720" (
    set VIDEO_FORMAT=bestvideo[height^<=720][ext=mp4]+bestaudio[ext=m4a]/best[height^<=720]
) else (
    set VIDEO_FORMAT=bestvideo+bestaudio/best
)

:: Phase 1: Combined video + audio
call :log_info "Phase 1: Downloading combined video + audio"
yt-dlp --config-location "%CONFIG_DIR%\complete-config.txt" --format "%VIDEO_FORMAT%" --merge-output-format "mp4" --output "combined:%%(title)s [%%(id)s].%%(ext)s" %EXTRA_OPTS% "%URL%"
if !errorlevel! neq 0 call :log_error "Failed to download combined video"

:: Phase 2: Separate video stream
call :log_info "Phase 2: Downloading separate video stream"
yt-dlp --config-location "%CONFIG_DIR%\complete-config.txt" --format "bestvideo" --output "video:%%(title)s [%%(id)s].video.%%(ext)s" %EXTRA_OPTS% "%URL%"
if !errorlevel! neq 0 call :log_error "Failed to download separate video"

:: Phase 3: Separate audio streams (MP3 and FLAC)
call :log_info "Phase 3: Downloading separate audio streams"
yt-dlp --config-location "%CONFIG_DIR%\complete-config.txt" --extract-audio --audio-format "mp3" --audio-quality "0" --output "audio:%%(title)s [%%(id)s].audio.%%(ext)s" %EXTRA_OPTS% "%URL%"
if !errorlevel! neq 0 call :log_error "Failed to extract MP3 audio"

yt-dlp --config-location "%CONFIG_DIR%\complete-config.txt" --extract-audio --audio-format "flac" --audio-quality "0" --output "audio:%%(title)s [%%(id)s].audio.%%(ext)s" %EXTRA_OPTS% "%URL%"
if !errorlevel! neq 0 call :log_error "Failed to extract FLAC audio"

:: Phase 4: Metadata and media files
call :log_info "Phase 4: Downloading metadata and media files"
yt-dlp --config-location "%CONFIG_DIR%\complete-config.txt" --write-info-json --write-description --write-annotations --write-comments --write-thumbnail --write-all-thumbnails --skip-download %EXTRA_OPTS% "%URL%"
if !errorlevel! neq 0 call :log_error "Failed to download metadata"

:: Phase 5: Transcripts and subtitles
call :log_info "Phase 5: Downloading transcripts and subtitles"
yt-dlp --config-location "%CONFIG_DIR%\complete-config.txt" --sub-langs "all,live_chat" --write-subs --write-auto-subs --convert-subs "srt" --convert-subs "vtt" --convert-subs "ass" --skip-download %EXTRA_OPTS% "%URL%"
if !errorlevel! neq 0 call :log_error "Failed to download transcripts"

call :log_info "Complete download finished for: %URL%"
echo Download completed! Check: %DEFAULT_OUTPUT%
echo Logs: %LOG_FILE%

echo.
echo === Download Summary ===
echo Video files: Combined + Separate
echo Audio files: MP3 + FLAC
echo Metadata: JSON, description, comments, annotations
echo Media: All thumbnails
echo Transcripts: All available subtitle formats
echo ========================

pause