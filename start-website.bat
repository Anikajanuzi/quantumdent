@echo off
cd /d "%~dp0"
title Quantum Dental website
set PY=python
where py >nul 2>nul
if %errorlevel%==0 set PY=py
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install it from python.org and tick "Add Python to PATH".
  pause
  exit /b 1
)
echo Installing time-zone data (first run only)...
%PY% -m pip install --quiet --disable-pip-version-check tzdata
%PY% tools\setup_env.py
echo.
echo Starting the website. Keep this window open. Close it to stop the website.
echo Website:          http://127.0.0.1:8000
echo Staff dashboard:  http://127.0.0.1:8000/admin/   (password is in admin-password.txt)
echo.
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8000"
%PY% server.py
pause
