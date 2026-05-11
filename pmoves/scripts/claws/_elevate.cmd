@echo off
:: _elevate.cmd — generic UAC-elevation wrapper for PMOVES claw scripts on Windows.
::
:: USAGE: _elevate.cmd <ps1-filename> [args-to-forward...]
::   <ps1-filename> must be a PowerShell script in the SAME folder as this .cmd.
::
:: BEHAVIOR:
::   1. Builds a small wrapper script in %TEMP% that runs the target .ps1 and
::      Tee-Objects all output to %TEMP%\pmoves-<stem>.log.
::   2. Re-launches powershell.exe with -Verb RunAs (UAC popup).
::   3. The elevated window stays open until the user presses Enter, so they
::      can read the result before it closes.
::
:: This file is invoked by the per-task wrappers (enable-ssh-elevated.cmd,
:: harden-ssh-elevated.cmd, etc.). Not intended to be double-clicked directly.

setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
set "TARGET=%~1"

if "%TARGET%"=="" (
    echo USAGE: _elevate.cmd ^<script.ps1^> [args...]
    pause
    exit /b 1
)

if not exist "%SCRIPT_DIR%%TARGET%" (
    echo ERROR: Cannot find %SCRIPT_DIR%%TARGET%
    echo This .cmd must live in the same folder as the target script.
    pause
    exit /b 1
)

for %%I in ("%TARGET%") do set "STEM=%%~nI"
set "LOG=%TEMP%\pmoves-%STEM%.log"

:: Collect remaining args (everything after the first) verbatim.
shift
set "FWD="
:loop
if "%~1"=="" goto args_done
set "FWD=!FWD! %1"
shift
goto loop
:args_done

:: Write an elevated wrapper script to %TEMP%. Using -File avoids the
:: nested-quote escaping problems of -Command across cmd → powershell.
set "WRAP=%TEMP%\pmoves-elevate-%STEM%.ps1"
> "%WRAP%" echo $ErrorActionPreference = 'Continue'
>> "%WRAP%" echo $target = "%SCRIPT_DIR%%TARGET%"
>> "%WRAP%" echo $log = "%LOG%"
>> "%WRAP%" echo $argString = '!FWD:'=''!'.Trim()
>> "%WRAP%" echo if ($argString) { $cmd = "& `"$target`" $argString" } else { $cmd = "& `"$target`"" }
>> "%WRAP%" echo Invoke-Expression $cmd ^*^>^&1 ^| Tee-Object -FilePath $log
>> "%WRAP%" echo Write-Host ''
>> "%WRAP%" echo Write-Host '=== Done. Press Enter to close this window. ===' -ForegroundColor Green
>> "%WRAP%" echo $null = Read-Host

echo.
echo PMOVES claw — about to ask Windows for permission to make admin changes.
echo Script: %TARGET%
echo Log:    %LOG%
echo.
echo When the popup appears, click "Yes".
echo The black window that opens will say "Done" when finished.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoExit','-NoProfile','-ExecutionPolicy','Bypass','-File','%WRAP%'"

del "%WRAP%" 2>nul
echo.
echo Done. Output saved to %LOG%
endlocal
