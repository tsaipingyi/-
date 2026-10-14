@echo off
chcp 65001 >nul
cd /d "%~dp0"
title pricewatch 价格监控（关闭此窗口即停止）
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

if not exist ".venv\Scripts\pricewatch.exe" (
  echo 还没有安装，请先双击 setup.bat
  pause
  exit /b 1
)
if not exist "data" mkdir data

echo 价格监控已启动，会按 .env 里的间隔自动检查价格。
echo   画面：双击 open.bat，或在浏览器打开 http://127.0.0.1:8000
echo   日志：data\server.log
echo   关闭这个窗口就会停止监控。
echo.

:loop
".venv\Scripts\pricewatch.exe" serve >> "data\server.log" 2>&1
echo %date% %time% 程序停止了，10 秒后自动重新启动...（详情见 data\server.log）
timeout /t 10 /nobreak >nul
goto loop
