@echo off
chcp 65001 >nul
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\pricewatch.lnk" >nul 2>nul
echo 已取消开机自动启动。
pause
