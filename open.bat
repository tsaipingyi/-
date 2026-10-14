@echo off
cd /d "%~dp0"
set "URL=http://127.0.0.1:8000/"
if exist "data\url.txt" set /p URL=<"data\url.txt"
start "" "%URL%"
