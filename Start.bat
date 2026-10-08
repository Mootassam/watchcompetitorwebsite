@echo off
title RivalRadar
cd /d "%~dp0"
echo Starting RivalRadar...
python server.py
if errorlevel 1 (
  echo.
  echo Could not start. Make sure Python 3 is installed, then run:
  echo     pip install -r requirements.txt
  pause
)
