@echo off
cd /d "%~dp0"
echo Registering pricewatch to start automatically when you log in to Windows...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup') + '\pricewatch.lnk'); $s.TargetPath = '%~dp0start.bat'; $s.WorkingDirectory = '%~dp0'; $s.WindowStyle = 7; $s.Save()" || goto fail
echo OK. It will start (minimized) the next time you log in.
echo.
choice /c YN /m "Also stop this PC from sleeping while plugged in? (monitoring stops during sleep)"
if errorlevel 2 goto done
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
echo OK. Sleep is disabled while plugged in.
:done
echo.
pause
exit /b 0
:fail
echo FAILED.
pause
exit /b 1
