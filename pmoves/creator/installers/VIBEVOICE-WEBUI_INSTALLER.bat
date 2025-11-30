@echo off
title VibeVoiceTTS 1-Click Installer

echo ================================================
echo          VibeVoiceTTS 1-Click Installer
echo ================================================
echo.
echo Requirements:
echo   - Windows 10/11 64-bit
echo   - NVIDIA GPU (CUDA 12.8 support)
echo   - Git installed
echo   - Python 3.10 installed
echo.
echo.
pause

REM --- Clone repo ---
if not exist VibeVoiceTTS (
    git clone https://github.com/SUP3RMASS1VE/VibeVoiceTTS.git
)

cd VibeVoiceTTS

REM --- Create venv ---
python -m venv .venv
call .venv\Scripts\activate

REM --- Install deps ---
pip install uv
uv pip install torch==2.7.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
uv pip install triton-windows
uv pip install https://github.com/petermg/flash_attn_windows/releases/download/01/flash_attn-2.7.4.post1+cu128.torch270-cp310-cp310-win_amd64.whl
uv pip install -e .

REM --- Download launcher ---
echo.
echo Downloading VibeVoice Launcher...
curl -L -o LAUNCHER_VibeVoice.bat "https://huggingface.co/Aitrepreneur/FLX/resolve/main/LAUNCHER_VibeVoice.bat?download=true"

echo.
echo ================================================
echo Install complete! Starting VibeVoiceTTS WebUI...
echo ================================================
echo.

python demo\gradio_demo.py

pause
