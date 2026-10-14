@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 设置开机（登录 Windows 后）自动启动价格监控...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup') + '\pricewatch.lnk'); $s.TargetPath = '%~dp0start.bat'; $s.WorkingDirectory = '%~dp0'; $s.WindowStyle = 7; $s.Save()" || goto fail
echo 完成。下次登录 Windows 时会自动启动（窗口会最小化在任务栏）。
echo.
choice /c YN /m "要同时把电脑设置成「插着电源时不睡眠」吗？（睡眠时监控会停止）"
if errorlevel 2 goto done
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
echo 已设置为插电时不睡眠。
:done
echo.
pause
exit /b 0
:fail
echo 设置失败。
pause
exit /b 1
