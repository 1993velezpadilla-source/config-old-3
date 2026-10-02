@echo off
setlocal
cd /d "%~dp0\..\.."
echo.
echo ========================================
echo   HAYUYA STUDIO - LAN MODE
echo ========================================
echo.
echo Opening local Studio in your default browser...
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8787"
echo.
echo On your phone, use one of the LAN URLs printed below.
echo Phone and this PC must be on the same trusted Wi-Fi/LAN.
echo.
python tools\hayuya3d\studio_server.py --lan --port 8787
pause
