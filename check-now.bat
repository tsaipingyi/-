@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo 现在检查一次所有商品的价格（不发送通知）...
echo.
".venv\Scripts\pricewatch.exe" check --no-notify
echo.
pause
