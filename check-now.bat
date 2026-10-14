@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo Checking all prices once (no notifications)...
echo.
".venv\Scripts\pricewatch.exe" check --no-notify
echo.
pause
