@echo off
cd /d "%~dp0"
echo ============================================
echo   pricewatch - SETUP
echo ============================================
echo.

set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=python"
if not defined PY goto nopython

echo [1/3] Creating environment...
if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv || goto fail

echo [2/3] Installing packages (first time takes a few minutes)...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
".venv\Scripts\python.exe" -m pip install -e . || goto fail

echo [3/3] Preparing settings...
if not exist ".env" copy ".env.example" ".env" >nul
if not exist "data" mkdir data

echo.
echo ============================================
echo   SETUP OK
echo   Next: double-click start.bat, then open.bat
echo ============================================
echo.
pause
exit /b 0

:nopython
echo Python 3.10+ was not found.
echo Install it from https://www.python.org/downloads/windows/
echo and CHECK "Add python.exe to PATH" in the installer. Then run setup.bat again.
echo.
pause
exit /b 1

:fail
echo.
echo SETUP FAILED. Please send a screenshot of this window to Claude.
pause
exit /b 1
