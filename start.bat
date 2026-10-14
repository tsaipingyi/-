@echo off
cd /d "%~dp0"
title pricewatch (do not close this window)
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

if not exist ".venv\Scripts\pricewatch.exe" (
  echo Not installed yet. Please double-click setup.bat first.
  pause
  exit /b 1
)
if not exist "data" mkdir data

echo ============================================
echo   pricewatch is RUNNING
echo   - Open the screen: double-click open.bat
echo   - Log file: data\server.log
echo   - Closing this window STOPS monitoring.
echo ============================================
echo.

:loop
".venv\Scripts\pricewatch.exe" serve >> "data\server.log" 2>&1
echo.
echo [%date% %time%] pricewatch STOPPED. Last lines of data\server.log:
echo --------------------------------------------
powershell -NoProfile -Command "Get-Content -Encoding UTF8 -Tail 15 'data\server.log'"
echo --------------------------------------------
echo Restarting in 10 seconds... (send a screenshot of this window to Claude)
timeout /t 10 /nobreak >nul
goto loop
