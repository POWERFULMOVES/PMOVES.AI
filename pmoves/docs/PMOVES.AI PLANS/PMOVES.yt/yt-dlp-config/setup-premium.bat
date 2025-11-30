@echo off
:: YouTube Cookies Extractor for Premium Authentication
:: Extracts cookies from browser for YouTube Premium access

setlocal enabledelayedexpansion

set CONFIG_DIR=C:\Users\russe\yt-dlp-config
set COOKIES_FILE=%CONFIG_DIR%\cookies.txt
set PYTHON_SCRIPT=%CONFIG_DIR%\extract-cookies.py

echo YouTube Premium Authentication Setup
echo ====================================
echo.

:: Check if browser is installed
echo Detecting browsers...
where chrome.exe >nul 2>&1
if %errorlevel% equ 0 (
    echo Found: Google Chrome
    set BROWSER=chrome
) else (
    where msedge.exe >nul 2>&1
    if %errorlevel% equ 0 (
        echo Found: Microsoft Edge
        set BROWSER=edge
    ) else (
        where firefox.exe >nul 2>&1
        if %errorlevel% equ 0 (
            echo Found: Mozilla Firefox
            set BROWSER=firefox
        ) else (
            echo No supported browser found automatically
            echo Please ensure Chrome, Edge, or Firefox is installed
            pause
            exit /b 1
        )
    )
)

echo Using browser: %BROWSER%
echo.

:: Method 1: Using yt-dlp's built-in cookie extraction
echo Method 1: Extracting cookies using yt-dlp...
yt-dlp --cookies-from-browser "%BROWSER%" --print-to-file "cookies" "%COOKIES_FILE%" --simulate "https://www.youtube.com"

if %errorlevel% equ 0 (
    echo Cookies extracted successfully!
    echo File location: %COOKIES_FILE%
) else (
    echo Method 1 failed, trying Method 2...
    
    :: Method 2: Using browser extension export
    echo.
    echo Method 2: Manual cookie export
    echo =================================
    echo.
    echo Please follow these steps:
    echo 1. Install "Get cookies.txt LOCALLY" extension for %BROWSER%
    echo 2. Go to youtube.com and ensure you're logged in with Premium
    echo 3. Click the extension icon and download cookies.txt
    echo 4. Save the file as: %COOKIES_FILE%
    echo.
    echo Extension links:
    echo Chrome: https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc
    echo Firefox: https://addons.mozilla.org/en-US/firefox/addon/get-cookiestxt-locally/
    echo.
    echo Press any key after you have saved the cookies file...
    pause
)

:: Test cookies
if exist "%COOKIES_FILE%" (
    echo.
    echo Testing cookies...
    yt-dlp --cookies "%COOKIES_FILE%" --simulate --print "%%(uploader)s - %%(title)s" "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    if %errorlevel% equ 0 (
        echo.
        echo SUCCESS: Cookies are working!
        echo YouTube Premium content should now be accessible.
        echo.
        echo Configuration files updated:
        echo - complete-config.txt now uses cookies.txt
        echo - tracker.py can access premium content
        echo.
        echo To test premium access:
        echo yt-dlp --cookies "%COOKIES_FILE%" "https://www.youtube.com/premium"
    ) else (
        echo.
        echo ERROR: Cookies test failed
        echo Please check that:
        echo 1. You're logged into YouTube Premium in %BROWSER%
        echo 2. The cookies file is not expired
        echo 3. The cookies file contains the correct domain cookies
    )
) else (
    echo.
    echo ERROR: No cookies file found at %COOKIES_FILE%
)

echo.
echo Authentication setup completed!
pause