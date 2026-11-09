@echo off
cd /d "%~dp0"
title Quantum Dental - turn on emails
set PY=python
where py >nul 2>nul
if %errorlevel%==0 set PY=py
%PY% tools\use_formsubmit.py
pause
