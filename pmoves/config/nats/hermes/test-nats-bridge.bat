@echo off
REM NATS Bridge Test for Elder-Melchor (Windows)
REM Run: test-nats-bridge.bat

echo === PMOVES NATS Bridge Test: Elder-Melchor ===
echo Node: elder-melchor
echo Time: %date% %time%
echo.

REM Check NATS connectivity
python -c "import socket; s=socket.create_connection(('pmoves-nats',4222),5); s.close(); print('OK: pmoves-nats:4222')" 2>nul
if errorlevel 1 (
    echo Trying Tailscale fallback...
    python -c "import socket; s=socket.create_connection(('100.82.62.45',4222),5); s.close(); print('OK: 100.82.62.45:4222')" 2>nul
    if errorlevel 1 (
        echo FAILED: NATS not reachable
        exit /b 1
    )
)

echo.
echo Connectivity OK. Run test-nats-bridge.py for full simulation.
pause
