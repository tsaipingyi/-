@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   价格监控 pricewatch 安装
echo ============================================
echo.

set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=python"
if not defined PY goto nopython

echo [1/3] 创建运行环境...
if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv || goto fail

echo [2/3] 安装需要的组件（第一次需要几分钟）...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
".venv\Scripts\python.exe" -m pip install -e . || goto fail

echo [3/3] 准备设置文件...
if not exist ".env" copy ".env.example" ".env" >nul
if not exist "data" mkdir data

echo.
echo 安装完成！
echo   下一步：双击 start.bat 启动，然后双击 open.bat 打开画面。
echo   通知、密码等设置在 .env 文件里（用记事本打开即可）。
echo.
pause
exit /b 0

:nopython
echo 没有找到 Python 3.10 以上的版本。
echo 请从 https://www.python.org/downloads/windows/ 下载安装，
echo 安装时一定要勾选 "Add python.exe to PATH"，装好后再双击本文件。
echo.
pause
exit /b 1

:fail
echo.
echo 安装失败。请把上面的错误信息截图发给 Claude。
pause
exit /b 1
