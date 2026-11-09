@echo off
cd /d "%~dp0"
title Quantum Dental - email setup
set PY=python
where py >/dev/null 2>nul
if %errorlevel%==0 set PY=py
%PY% tools\setup_email.py
echo.
pause
