@echo off
REM ============================================================
REM PMOVES.AI Submodule Initialization Script (Windows)
REM Ageless Beauty Practice Workstation (Elder-Melchor)
REM ============================================================

set REPO_ROOT=%~dp0\..\..\..
cd %REPO_ROOT%

echo ========================================
echo Ageless Beauty Submodule Initialization
echo ========================================
echo.

echo [1/4] Initializing Health + Wealth submodules...
git submodule update --init Pmoves-Health-wger
git submodule update --init PMOVES-Wealth
echo [OK] Health + Wealth initialized
echo.

echo [2/4] Initializing Workflow + UI + Data submodules...
git submodule update --init PMOVES-n8n
git submodule update --init PMOVES-MAI-UI
git submodule update --init PMOVES-supabase
echo [OK] Workflow + UI + Data initialized
echo.

echo [3/4] Initializing Media + Voice + Geometry submodules...
git submodule update --init Pmoves-Jellyfin-AI-Media-Stack
git submodule update --init PMOVES-Pinokio-Ultimate-TTS-Studio
git submodule update --init Pmoves-hyperdimensions
git submodule update --init PMOVES-ToKenism-Multi
echo [OK] Media + Voice + Geometry initialized
echo.

echo [4/4] Initializing Security submodules...
git submodule update --init Pmoves-cipher
git submodule update --init pmoves-cipher-mcp
echo [OK] Security initialized
echo.

echo ========================================
echo Ageless Beauty submodules ready!
echo ========================================
echo.
echo Next steps:
echo   1. Configure Pmoves-Health-wger for HIPAA mode
echo   2. Set up PMOVES-Wealth for medical billing (CPT codes)
echo   3. Import PMOVES-n8n workflows for practice BPM3
echo   4. Deploy PMOVES-MAI-UI to Hostinger VPS
echo   5. Configure PMOVES-supabase for patient data
echo.
pause
