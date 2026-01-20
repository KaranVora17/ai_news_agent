@echo off
REM Change to project directory
cd /d "%~dp0"
REM Optional short delay to allow network to come up (adjust seconds)
timeout /t 10 /nobreak >nul

REM Call the real Python (absolute path)
"C:\Program Files\Python312\python.exe" daily_launch.py

exit /b %ERRORLEVEL%

